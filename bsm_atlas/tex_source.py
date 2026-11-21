"""Conservative, in-memory arXiv TeX preparation, without interpreting TeX.

Only literal local dependencies are followed. Unsupported/missing dependencies
raise ValueError rather than returning an apparently complete paper. Nothing in
an archive is executed, extracted, or resolved against the host filesystem.
"""
import gzip
import io
import json
import posixpath
import re
import tarfile

CLEANER_VERSION = 2
MAX_MEMBERS = 1024
MAX_EXPANDED = 50_000_000
_BINARY = {'.pdf', '.eps', '.ps', '.png', '.jpg', '.jpeg', '.gif', '.webp',
           '.dvi', '.ttf', '.otf', '.woff', '.zip', '.gz', '.bz2', '.xz',
           '.tar', '.mp4', '.mp3', '.avi', '.root'}
_DEFINITION = {'newcommand', 'renewcommand', 'providecommand',
               'DeclareRobustCommand', 'DeclareMathOperator', 'newenvironment',
               'renewenvironment', 'provideenvironment', 'def', 'gdef', 'edef',
               'xdef'}
_DRAWING = {'tikzpicture', 'picture', 'pspicture', 'pspicture*', 'feynman',
            'fmffile', 'fmfgraph', 'fmfgraph*', 'feynartspicture', 'axopicture',
            'asy', 'pgfpicture'}
_VERBATIM = {'verbatim', 'verbatim*', 'lstlisting', 'minted', 'Verbatim'}
_BIBLIOGRAPHY = {'thebibliography', 'references', 'references*', 'biblist',
                 'mcitethebibliography'}
_LIBRARY = {'.sty', '.cls', '.clo', '.def'}
# These standard inputs supply graphics/typesetting, never paper sections.
_EXTERNAL_LAYOUT = {'epsf', 'epsfig', 'psfig', 'boxedeps', 'psbox', 'pictex',
                    'prepictex', 'postpictex', 'rotate', 'rotating', 'color'}
_COMMAND = re.compile(r'\\([A-Za-z@]+|.)', re.DOTALL)
_ENVIRONMENT = re.compile(r'\\(begin|end)\s*\{\s*([A-Za-z*@-]+)\s*\}')
_MAIN = re.compile(r'\\(?:documentclass|documentstyle)\b|\\begin\s*\{document\}|\\bye\b')


def _skip_space(text, offset):
    while offset < len(text) and text[offset].isspace():
        offset += 1
    return offset


def _group(text, offset, left='{', right='}'):
    """Read a balanced group, respecting escaped braces; return body and end."""
    offset = _skip_space(text, offset)
    if offset >= len(text) or text[offset] != left:
        raise ValueError('Missing literal TeX argument')
    start, depth, cursor = offset + 1, 1, offset + 1
    while cursor < len(text):
        char = text[cursor]
        if char == '\\':
            cursor += 2
            continue
        if char == left:
            depth += 1
        elif char == right:
            depth -= 1
            if not depth:
                return text[start:cursor], cursor + 1
        cursor += 1
    raise ValueError('Unbalanced TeX argument')


def _argument(text, offset, bare=False):
    offset = _skip_space(text, offset)
    if offset < len(text) and text[offset] == '{':
        return _group(text, offset)
    if bare:
        match = re.match(r'[^\s{}]+', text[offset:])
        if match:
            return match.group(), offset + len(match.group())
    raise ValueError('Missing literal TeX input argument')


def _optional_arguments(text, offset):
    offset = _skip_space(text, offset)
    if offset < len(text) and text[offset] == '*':
        offset = _skip_space(text, offset + 1)
    while offset < len(text) and text[offset] == '[':
        _, offset = _group(text, offset, '[', ']')
        offset = _skip_space(text, offset)
    return offset


def _environment_end(text, offset, name):
    """Find matching end with a stack, not a greedy cross-environment regex."""
    stack = [name]
    for match in _ENVIRONMENT.finditer(text, offset):
        action, current = match.groups()
        if action == 'begin':
            stack.append(current)
        elif stack and current == stack[-1]:
            stack.pop()
            if not stack:
                return match.end()
        else:
            raise ValueError('Unbalanced TeX environment while removing ' + name)
    raise ValueError('Unterminated TeX environment: ' + name)


def _strip_comments(text):
    """Preserve escaped percent signs and literal verbatim content."""
    parts, cursor = [], 0
    while cursor < len(text):
        char = text[cursor]
        if char == '%':
            end = text.find('\n', cursor)
            if end < 0:
                break
            cursor = end
        elif char == '\\':
            match = _COMMAND.match(text, cursor)
            if not match:
                parts.append(char)
                cursor += 1
                continue
            command, end = match.group(1), match.end()
            if command == 'verb':
                if end < len(text) and text[end] == '*':
                    end += 1
                if end >= len(text) or text[end].isspace():
                    raise ValueError('Malformed TeX verbatim command')
                closing = text.find(text[end], end + 1)
                if closing < 0:
                    raise ValueError('Unterminated TeX verbatim command')
                end = closing + 1
            elif command == 'begin':
                name, opening_end = _group(text, end)
                if name in _VERBATIM:
                    closing = re.search(r'\\end\s*\{' + re.escape(name) + r'\}',
                                        text[opening_end:])
                    if not closing:
                        raise ValueError('Unterminated TeX verbatim environment')
                    end = opening_end + closing.end()
            parts.append(text[cursor:end])
            cursor = end
        else:
            end = cursor + 1
            while end < len(text) and text[end] not in '%\\':
                end += 1
            parts.append(text[cursor:end])
            cursor = end
    return ''.join(parts)


def _definition_end(text, offset, command):
    """Do not treat commands inside a macro definition as executed includes."""
    offset = _skip_space(text, offset)
    if offset < len(text) and text[offset] == '*':
        offset = _skip_space(text, offset + 1)
    if command in {'def', 'gdef', 'edef', 'xdef'}:
        match = _COMMAND.match(text, offset)
        if not match:
            raise ValueError('Unsupported TeX macro definition')
        offset = match.end()
        while offset < len(text) and text[offset] != '{':
            offset += 1
        _, end = _group(text, offset)
        return end
    if offset < len(text) and text[offset] == '{':
        _, offset = _group(text, offset)
    else:
        match = _COMMAND.match(text, offset)
        if not match:
            raise ValueError('Unsupported TeX macro definition')
        offset = match.end()
    offset = _optional_arguments(text, offset)
    _, end = _group(text, offset)
    if command.endswith('environment'):
        _, end = _group(text, end)
    return end


def _literal_conditional(text, offset, truth):
    """Select a literal iftrue/iffalse branch without executing any macros.

    Conditional tokens in skipped TeX are still balanced by TeX itself. Unknown
    if-prefixed conditionals are therefore treated as nested; ambiguous or
    unbalanced material is rejected rather than guessed.
    """
    level, alternate = 1, None
    for match in _COMMAND.finditer(text, offset):
        command = match.group(1)
        if command.startswith('if') and command not in {'ifthenelse', 'ifstrequal', 'ifstrempty'}:
            level += 1
        elif command == 'fi':
            level -= 1
            if level == 0:
                first_end = alternate[0] if alternate else match.start()
                if truth:
                    return text[offset:first_end], match.end()
                return (text[alternate[1]:match.start()] if alternate else ''), match.end()
        elif command == 'else' and level == 1:
            if alternate:
                raise ValueError('Ambiguous literal TeX conditional: multiple else branches')
            alternate = (match.start(), match.end())
    raise ValueError('Unterminated literal TeX conditional')


def _normal_name(name):
    if not name or '\x00' in name or '\n' in name or '\r' in name:
        raise ValueError('Unsupported source filename')
    # A virtual namespace only. Even ../../ paths never touch the filesystem.
    return posixpath.normpath(name.replace('\\', '/'))


def _decode(content):
    if b'\x00' in content:
        return None
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        # Older arXiv submissions commonly contain Latin-1 TeX source.
        return content.decode('latin-1')


def _archive_sources(content):
    sources, total = {}, 0
    try:
        archive = tarfile.open(fileobj=io.BytesIO(content), mode='r:*')
    except tarfile.ReadError:
        if content.startswith(b'\x1f\x8b'):
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as compressed:
                content = compressed.read(MAX_EXPANDED + 1)
        if len(content) > MAX_EXPANDED:
            raise ValueError('Source exceeds the expansion bound')
        decoded = _decode(content)
        if decoded is None:
            raise ValueError('Source is not usable full TeX text')
        return {'main.tex': decoded}
    with archive:
        for count, member in enumerate(archive, 1):
            total += max(0, member.size)
            if count > MAX_MEMBERS or total > MAX_EXPANDED:
                raise ValueError('Source archive exceeds the expansion bound')
            if not member.isfile() or posixpath.splitext(member.name)[1].lower() in _BINARY:
                continue
            with archive.extractfile(member) as handle:
                body = handle.read(MAX_EXPANDED + 1)
            if len(body) != member.size or len(body) > MAX_EXPANDED:
                raise ValueError('Source member exceeds the expansion bound')
            decoded = _decode(body)
            if decoded is None:
                continue
            name = _normal_name(member.name)
            if name in sources:
                raise ValueError('Duplicate normalized source filename: ' + name)
            sources[name] = decoded
    return sources


class _Cleaner:
    def __init__(self, sources):
        self.sources = {name: text.replace('\r\n', '\n').replace('\r', '\n')
                        for name, text in sources.items()}
        self.text_cache = {}
        self.libraries = []
        self.included, self.omissions = [], []
        self.main = None
        self.main_selection = 'unique_literal_root'
        self.work_bytes = 0
        self.document_ended = False

    def text(self, name):
        if name not in self.text_cache:
            self.text_cache[name] = _strip_comments(self.sources[name])
        return self.text_cache[name]

    @staticmethod
    def external_layout(target):
        return posixpath.basename(target).lower().removesuffix('.tex').removesuffix('.sty') in _EXTERNAL_LAYOUT

    def library(self, name, stack=()):
        """Retain local formatting definitions as text, without interpreting them.

        Package internals use catcodes, active characters and host-distribution
        conditionals. They are not document-level includes. Preserve their bytes
        and any literal local helper files so notation definitions remain visible.
        Missing paper-specific helpers still fail; standard distribution files do
        not have to be bundled in an arXiv submission.
        """
        if name in stack:
            raise ValueError('Cyclic TeX library dependency: ' + name)
        if name in self.libraries:
            return ''
        self.libraries.append(name)
        if name not in self.included:
            self.included.append(name)
        text = self.sources[name]
        self.work_bytes += len(text.encode('utf-8'))
        if self.work_bytes > MAX_EXPANDED:
            raise ValueError('Repeated TeX dependency expansion exceeds the supported bound')
        parts = ['\nLOCAL TEX DEFINITIONS (unexecuted): ' + name + '\n', text,
                 '\nEND LOCAL TEX DEFINITIONS: ' + name + '\n']
        # Literal local inputs in library code may themselves contain notation
        # or tables. Retain those files too, but never expand dynamic filenames.
        for match in re.finditer(r'\\(?:input|include)\s*(?:\{([^{}\\#]+)\}|([^\s{}\\#]+))', text):
            target = match.group(1) or match.group(2)
            dependency = self.resolve(name, target, '.tex', required=False)
            if dependency:
                parts.append(self.library(dependency, stack + (name,)))
            elif posixpath.splitext(target)[1].lower() not in _LIBRARY and not self.external_layout(target):
                # Package distribution internals conventionally use @/jobname
                # macros; a literal scientific .tex helper is different.
                if posixpath.splitext(target)[1].lower() == '.tex':
                    raise ValueError('Missing TeX dependency in ' + name + ': ' + target)
        return ''.join(parts)

    def resolve(self, current, target, suffix=None, required=True):
        if not target.strip() or any(char in target for char in '\\{}#$^~|'):
            raise ValueError('Dynamic or unsupported TeX dependency in ' + current + ': ' + target)
        target = target.strip()
        names = [target]
        if suffix and not posixpath.splitext(target)[1]:
            names = [target + suffix, target]
        directories = [posixpath.dirname(current)]
        if self.main is not None:
            directories.append(posixpath.dirname(self.main))
        directories.append('')
        found = []
        for directory in directories:
            for name in names:
                candidate = _normal_name(posixpath.join(directory, name))
                if candidate in self.sources and candidate not in found:
                    found.append(candidate)
        if len(found) > 1:
            raise ValueError('Ambiguous local TeX dependency in ' + current + ': ' + target)
        if not found:
            if required:
                raise ValueError('Missing TeX dependency in ' + current + ': ' + target)
            return None
        return found[0]

    def marker(self, description):
        self.omissions.append(description)
        return '\n[OMITTED: ' + description + ']\n'

    def process(self, name, stack=(), probe=False):
        if name in stack:
            raise ValueError('Cyclic TeX dependency: ' + ' -> '.join(stack + (name,)))
        if len(stack) > 100:
            raise ValueError('TeX dependency depth exceeds the supported bound')
        if name not in self.included:
            self.included.append(name)
        text, parts, cursor = self.text(name), [], 0
        self.work_bytes += len(text.encode('utf-8'))
        if self.work_bytes > MAX_EXPANDED:
            raise ValueError('Repeated TeX dependency expansion exceeds the supported bound')
        while cursor < len(text):
            if self.document_ended:
                break
            start = text.find('\\', cursor)
            if start < 0:
                parts.append(text[cursor:])
                break
            parts.append(text[cursor:start])
            match = _COMMAND.match(text, start)
            if not match:
                parts.append(text[start:])
                break
            command, end = match.group(1), match.end()
            if command in {'iftrue', 'iffalse'}:
                active, end = _literal_conditional(text, end, command == 'iftrue')
                parts.append(self.marker('inactive literal conditional branch'))
                # Continue scanning the selected branch, including its includes.
                # Prefix has already been emitted; inactive text is never parsed.
                text = text[:start] + active + text[end:]
                cursor = start
                continue
            elif command in _DEFINITION:
                end = _definition_end(text, end, command)
                if re.search(r'\\(?:input|include|subfile|import|subimport|inputfrom|'
                             r'InputIfFileExists|IfFileExists)\b', text[start:end]):
                    raise ValueError('Unsupported macro-mediated TeX dependency in ' + name)
                parts.append(text[start:end])
            elif command in {'input', 'include', 'subfile'}:
                target, end = _argument(text, end, bare=command == 'input')
                if posixpath.splitext(target)[1].lower() in {'.bbl', '.bib'}:
                    parts.append(self.marker('bibliography input ' + target))
                else:
                    dependency = self.resolve(name, target, '.tex', required=False)
                    if dependency is None and self.external_layout(target):
                        parts.append(self.marker('external graphics/typesetting input ' + target))
                    else:
                        if dependency is None:
                            raise ValueError('Missing TeX dependency in ' + name + ': ' + target)
                        child = (self.library(dependency) if posixpath.splitext(dependency)[1].lower() in _LIBRARY
                                 else self.process(dependency, stack + (name,), probe=probe))
                        parts.append('\nSOURCE FILE: ' + dependency + '\n' + child + '\n')
            elif command in {'InputIfFileExists', 'IfFileExists'}:
                target, end = _argument(text, end)
                yes, end = _group(text, end)
                no, end = _group(text, end)
                dependency = self.resolve(name, target, '.tex', required=False)
                if dependency is None and not no.strip() and not self.external_layout(target):
                    raise ValueError('Missing optional TeX dependency without fallback in ' + name + ': ' + target)
                if dependency is None and posixpath.splitext(target)[1].lower() in _LIBRARY:
                    raise ValueError('Unknown host-distribution file-existence branch: ' + target)
                active = yes if dependency else no
                if dependency and command == 'InputIfFileExists':
                    # Re-enter the ordinary include path once, after true code.
                    active += '\n\\input{' + target + '}'
                parts.append(self.marker('literal file-existence branch: ' + target))
                text = text[:start] + active + text[end:]
                cursor = start
                continue
            elif command in {'includeonly', 'import', 'subimport', 'inputfrom',
                             'subinputfrom', 'includefrom', 'subincludefrom',
                             'verbatiminput', 'lstinputlisting', 'InputIfFileExists',
                             'IfFileExists', '@input', '@input@', '@iinput',
                             '@@input', 'scantokens', 'openin', 'read', 'readline'}:
                raise ValueError('Unsupported TeX dependency command: \\' + command)
            elif command in {'usepackage', 'RequirePackage', 'documentclass',
                             'documentstyle', 'LoadClass', 'LoadClassWithOptions'}:
                argument_start = _optional_arguments(text, end)
                targets, end = _argument(text, argument_start)
                parts.append(text[start:end])
                for target in targets.split(','):
                    suffix = '.sty' if command in {'usepackage', 'RequirePackage', 'documentstyle'} else '.cls'
                    dependency = self.resolve(name, target, suffix, required=False)
                    if dependency:
                        child = self.library(dependency)
                        parts.append('\nSOURCE FILE: ' + dependency + '\n' + child + '\n')
            elif command == 'begin':
                environment, opening_end = _group(text, end)
                if environment in _DRAWING or environment in _BIBLIOGRAPHY:
                    end = _environment_end(text, opening_end, environment)
                    parts.append(self.marker('bibliography' if environment in _BIBLIOGRAPHY
                                             else 'figure drawing ' + environment))
                elif environment in _VERBATIM:
                    closing = re.search(r'\\end\s*\{' + re.escape(environment) + r'\}',
                                        text[opening_end:])
                    if not closing:
                        raise ValueError('Unterminated TeX verbatim environment')
                    end = opening_end + closing.end()
                    parts.append(text[start:end])
                else:
                    end = opening_end
                    parts.append(text[start:end])
            elif command == 'verb':
                if end < len(text) and text[end] == '*':
                    end += 1
                if end >= len(text) or text[end].isspace():
                    raise ValueError('Malformed TeX verbatim command')
                closing = text.find(text[end], end + 1)
                if closing < 0:
                    raise ValueError('Unterminated TeX verbatim command')
                end = closing + 1
                parts.append(text[start:end])
            elif command in {'includegraphics', 'epsfig', 'psfig', 'epsfbox',
                             'epsffile', 'includepdf'}:
                target, end = _argument(text, _optional_arguments(text, end),
                                        bare=command == 'epsffile')
                parts.append(self.marker('graphic ' + target))
            elif command in {'bibliography', 'bibliographystyle', 'addbibresource'}:
                target, end = _argument(text, _optional_arguments(text, end))
                parts.append(self.marker('bibliography ' + target))
            elif command == 'printbibliography':
                end = _optional_arguments(text, end)
                parts.append(self.marker('bibliography'))
            elif command in {'bibitem', 'entry'}:
                raise ValueError('Bibliography entry outside a recognized bibliography environment')
            elif command == 'end':
                environment, end = _group(text, end)
                parts.append(text[start:end])
                if environment.strip() == 'document':
                    self.document_ended = True
                    break
            elif command == 'bye':
                parts.append(text[start:end])
                self.document_ended = True
                break
            elif command == 'endinput':
                break
            else:
                parts.append(text[start:end])
            cursor = end
        return ''.join(parts)

    def choose_main(self):
        candidates = [name for name, text in self.sources.items()
                      if posixpath.splitext(name)[1].lower() not in _LIBRARY | {'.bib', '.bbl', '.dtx', '.ins'}
                      and _MAIN.search(self.text(name))]
        if not candidates:
            raise ValueError('Response is not usable full TeX source: no main document')
        # Included title/subfile documents may contain their own document marker.
        # A main is independent only if no other main reaches it by literal input.
        dependencies = set()
        failures, outputs = {}, {}
        for candidate in candidates:
            self.main, self.included, self.omissions, self.libraries = candidate, [], [], []
            self.work_bytes, self.document_ended = 0, False
            try:
                outputs[candidate] = self.process(candidate, probe=True)
                dependencies.update(name for name in self.included if name != candidate)
            except ValueError as error:
                failures[candidate] = error
                dependencies.update(name for name in self.included if name != candidate)
        roots = [name for name in candidates if name not in dependencies]
        preferred = []
        for metadata_name, body in self.sources.items():
            if posixpath.basename(metadata_name).lower() != '00readme.json':
                continue
            try:
                metadata = json.loads(body)
                for row in metadata.get('sources', []):
                    if row.get('usage') == 'toplevel':
                        path = _normal_name(posixpath.join(posixpath.dirname(metadata_name), row['filename']))
                        preferred.append(path)
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                raise ValueError('Malformed arXiv top-level source metadata') from error
        if preferred:
            if len(set(preferred)) != 1 or preferred[0] not in candidates:
                raise ValueError('Ambiguous or missing arXiv top-level TeX source')
            roots = [preferred[0]]
            self.main_selection = 'arxiv_toplevel_metadata'
        elif len(roots) > 1 and all(name in outputs for name in roots) and len({outputs[name] for name in roots}) == 1:
            # Two independent filenames with exactly equal prepared content are
            # duplicates, not alternative physics drafts. No name heuristic.
            roots = [sorted(roots)[0]]
            self.main_selection = 'identical_prepared_roots'
        if len(roots) != 1:
            raise ValueError('Ambiguous independent main TeX documents: ' + ', '.join(roots or candidates))
        main = roots[0]
        if main in failures:
            raise failures[main]
        self.main, self.included, self.omissions, self.libraries = main, [], [], []
        self.work_bytes, self.document_ended = 0, False
        return main


def _prepare(sources):
    if len(sources) > MAX_MEMBERS or sum(len(value.encode('utf-8')) for value in sources.values()) > MAX_EXPANDED:
        raise ValueError('Source text exceeds the expansion bound')
    cleaner = _Cleaner(sources)
    main = cleaner.choose_main()
    cleaned = 'SOURCE FILE: ' + main + '\n' + cleaner.process(main)
    cleaned = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', cleaned).strip() + '\n'
    raw = ''.join('\nSOURCE FILE: ' + name + '\n' + text + '\n'
                  for name, text in sources.items())
    return cleaned, raw, {'cleaner_version': CLEANER_VERSION, 'main_file': main, 'main_selection': cleaner.main_selection,
                          'included_files': cleaner.included,
                          'unexecuted_library_files': cleaner.libraries,
                          'omissions': cleaner.omissions,
                          'raw_characters': len(raw), 'cleaned_characters': len(cleaned)}


def prepare_tex(content):
    """Return cleaned text, text-only source cache, and preparation provenance."""
    if not isinstance(content, bytes):
        raise TypeError('TeX source must be bytes')
    return _prepare(_archive_sources(content))


def prepare_cached_tex(text):
    """Prepare old SOURCE FILE concatenations without re-downloading a paper."""
    if not isinstance(text, str):
        raise TypeError('Cached TeX source must be text')
    if len(text.encode('utf-8')) > MAX_EXPANDED:
        raise ValueError('Cached source exceeds the expansion bound')
    headers = list(re.finditer(r'^SOURCE FILE: ([^\r\n]+)\r?\n', text, re.MULTILINE))
    if not headers:
        return _prepare({'main.tex': text})
    if text[:headers[0].start()].strip():
        raise ValueError('Unexpected text before cached source file markers')
    sources = {}
    for index, header in enumerate(headers):
        name = _normal_name(header.group(1))
        if name in sources:
            raise ValueError('Duplicate cached source filename: ' + name)
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        sources[name] = text[header.end():end]
    return _prepare(sources)


def clean_tex(content):
    return prepare_tex(content)[0]


def clean_cached_tex(text):
    return prepare_cached_tex(text)[0]
