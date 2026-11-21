"""Static TeX source assembly, profile 3; profile 2 remains reproducible.

No TeX engine, shell, host include lookup or network is used. Literal includes
and finite, literal-argument include wrappers are assembled in memory. General
mathematical macros remain source text. Missing scientific inputs fail closed.
"""
import json
import posixpath
import re
from . import tex_source as base

CLEANER_VERSION = 3
_XPARSE = {'NewDocumentCommand', 'RenewDocumentCommand', 'ProvideDocumentCommand',
           'DeclareDocumentCommand'}
_DEFS = base._DEFINITION | _XPARSE | {'let'}
_IMPORTS = {'import','subimport','inputfrom','subinputfrom','includefrom','subincludefrom'}
_DEPS = re.compile(r'\\(?:input|include|subfile|import|subimport|inputfrom|subinputfrom|InputIfFileExists|IfFileExists|openin|read|scantokens)\b')
_BIB = base._BIBLIOGRAPHY | {'mcbibliography', 'thebibliography*', 'biblio'}
_FORMAT_INPUTS = base._EXTERNAL_LAYOUT | {'feynman','axodraw','harvmac','phyzzx',
                                          'hyperbasics','tcilatex','amssym','amssymb'}
_BACKUP = re.compile(r'(?:\.(?:bak|sav|old|orig|backup)|~|_)$', re.I)


def _space(text, offset):
    while True:
        offset = base._skip_space(text, offset)
        match = base._COMMAND.match(text, offset)
        if match and match.group(1) == 'expandafter':
            offset = match.end()
        else:
            return offset


def _plain_comments(text):
    parts=[];cursor=0
    while cursor<len(text):
        if text[cursor]=='%':
            end=text.find('\n',cursor)
            if end<0:break
            cursor=end;continue
        match=base._COMMAND.match(text,cursor)
        if match:parts.append(match.group());cursor=match.end()
        else:parts.append(text[cursor]);cursor+=1
    return ''.join(parts)


def _group(text,offset,left='{',right='}'):
    offset=base._skip_space(text,offset)
    if offset>=len(text) or text[offset]!=left:raise ValueError('Missing literal TeX argument')
    start=offset+1;cursor=start;depth=1
    while cursor<len(text):
        if text[cursor]=='\\':cursor+=2;continue
        if text[cursor]=='%':
            end=text.find('\n',cursor)
            if end<0:break
            cursor=end;continue
        if text[cursor]==left:depth+=1
        elif text[cursor]==right:
            depth-=1
            if depth==0:return text[start:cursor],cursor+1
        cursor+=1
    raise ValueError('Unbalanced TeX argument')


def _token(text, offset):
    offset = _space(text, offset)
    if offset >= len(text):
        raise ValueError('Missing TeX token')
    if text[offset] == '{':
        body, end = _group(text, offset)
        return body, end
    match = base._COMMAND.match(text, offset)
    if match:
        return match.group(), match.end()
    return text[offset], offset + 1


def _definition(text, end, command):
    """Read the lexical bounds of a definition, including one-token bodies."""
    offset = _space(text, end)
    if offset < len(text) and text[offset] == '*':
        offset = _space(text, offset + 1)
    target, offset = _token(text, offset)
    target = target.strip()
    if not (command.endswith('environment') and re.fullmatch(r'[A-Za-z0-9@*_.:-]+',target)) and not re.fullmatch(r'\\(?:[A-Za-z@]+|.)|[^\s{}]', target):
        raise ValueError('Unsupported macro definition target')
    if command == 'let':
        offset = _space(text, offset)
        if offset < len(text) and text[offset] == '=':
            offset += 1
        body, finish = _token(text, offset)
        return target, [], body, finish, True
    if command in {'def','gdef','edef','xdef'}:
        start = offset
        while offset < len(text) and text[offset] != '{':
            offset += 1
        parameters = re.sub(r'\s+', '', _plain_comments(text[start:offset]))
        body, finish = _group(text, offset)
        indices = [int(x) for x in re.findall(r'(?<!#)#([1-9])', parameters)]
        n = max(indices, default=0)
        simple = parameters == ''.join('#'+str(i) for i in range(1,n+1))
        return target, ['m']*n, _plain_comments(body), finish, simple
    if command in _XPARSE:
        spec, offset = _group(text, _space(text, offset))
        compact = re.sub(r'\s+', '', spec)
        kinds = list(compact)
        simple = all(c in 'mo' for c in kinds)
        body, finish = _token(text, offset)
        return target, kinds, _plain_comments(body), finish, simple
    offset = _space(text, offset)
    kinds = []
    if offset < len(text) and text[offset] == '[':
        count, offset = _group(text, offset, '[', ']')
        if not count.isdigit() or not 0 <= int(count) <= 9:
            raise ValueError('Nonliteral macro argument count')
        kinds = ['m']*int(count)
        offset = _space(text, offset)
        if offset < len(text) and text[offset] == '[':
            default, offset = _group(text, offset, '[', ']')
            if not kinds:
                raise ValueError('Optional macro default without an argument')
            kinds[0] = ('optional',default)
    body, finish = _token(text, offset)
    if command.endswith('environment'):
        tail, finish = _token(text, finish)
        body += '\n' + tail
    return target, kinds, _plain_comments(body), finish, True


def _comments(text):
    """Strip comments, but do not mistake commands inside definitions for I/O."""
    out, cursor = [], 0
    while cursor < len(text):
        if text[cursor] == '%':
            end = text.find('\n', cursor)
            if end < 0:
                break
            cursor = end
            continue
        match = base._COMMAND.match(text, cursor)
        if not match:
            out.append(text[cursor]);cursor += 1;continue
        command, end = match.group(1), match.end()
        if command in _DEFS:
            try:
                _,_,_,end,_ = _definition(text,end,command)
            except ValueError:
                # Parsing the actual definition will still fail during assembly;
                # comments can contain unmatched braces, so strip them first.
                pass
        elif command == 'verb':
            if end < len(text) and text[end] == '*': end += 1
            if end < len(text) and not text[end].isspace():
                closing = text.find(text[end],end+1)
                if closing < 0: raise ValueError('Unterminated TeX verbatim command')
                end = closing+1
        elif command == 'begin':
            try: name, opening = base._group(text,end)
            except ValueError: name,opening = '',end
            if name in base._VERBATIM:
                closing = re.search(r'\\end\s*\{'+re.escape(name)+r'\}',text[opening:])
                if not closing: raise ValueError('Unterminated TeX verbatim environment')
                end = opening+closing.end()
        out.append(text[cursor:end]);cursor=end
    return ''.join(out)


class Cleaner(base._Cleaner):
    def __init__(self, sources):
        super().__init__(sources)
        self.expansions = 0
        self.excluded_roots = []
        self.notes = []
        self.macros = {}
        self.include_only = None
        self.file_stack = []
        self.dependent_environments = set()
        self.conditional_depth = 0

    def text(self, name):
        if name not in self.text_cache:
            self.text_cache[name] = _comments(self.sources[name])
        return self.text_cache[name]

    @staticmethod
    def external_layout(target):
        name = posixpath.basename(target).lower()
        for suffix in ('.tex','.sty','.def'):
            if name.endswith(suffix): name=name[:-len(suffix)]
        return name in _FORMAT_INPUTS

    def resolve(self,current,target,suffix=None,required=True):
        # TeX also appends .tex to names such as wishlist.main. Prefer an exact
        # supplied name; keep the same virtual local-only namespace as profile 2.
        if suffix=='.tex':
            result=super().resolve(current,target,None,required=False)
            if result is None and not target.lower().endswith('.tex'):
                result=super().resolve(current,target+'.tex',None,required=False)
            if result is None and required:
                raise ValueError('Missing TeX dependency in '+current+': '+target)
            return result
        return super().resolve(current,target,suffix,required)

    def library(self,name,stack=()):
        text=super().library(name,stack)
        scan=_comments(text)
        cursor=0
        # Register only file-loading definitions. Conflicting conditional
        # definitions are withheld rather than assigning an arbitrary branch.
        while cursor<len(scan):
            match=base._COMMAND.search(scan,cursor)
            if not match:break
            cursor=match.end();command=match.group(1)
            if command not in _DEFS:continue
            try:target,kinds,body,end,simple=_definition(scan,cursor,command)
            except ValueError:continue
            cursor=end
            if not _DEPS.search(body):continue
            value={'kinds':kinds,'body':body,'simple':simple,'command':command}
            old=self.macros.get(target)
            if old and old!=value:value['ambiguous']=True
            self.macros[target]=value
        return text

    def _arguments(self,text,end,kinds):
        args=[]
        for kind in kinds:
            end=_space(text,end)
            if kind=='o' or isinstance(kind,tuple):
                if end<len(text) and text[end]=='[':
                    arg,end=base._group(text,end,'[',']')
                else:arg=kind[1] if isinstance(kind,tuple) else r'\NoValue'
            else:arg,end=_token(text,end)
            args.append(arg)
        return args,end

    def _filename(self,target):
        for _ in range(20):
            changed=False
            def expand(match):
                nonlocal changed
                key=match.group()
                if key==r'\jobname':
                    changed=True;return posixpath.splitext(posixpath.basename(self.main))[0]
                macro=self.macros.get(key)
                if macro and macro.get('ambiguous'):
                    raise ValueError('Conditional filename macro has unresolved branch: '+key)
                if macro and not macro['kinds'] and not _DEPS.search(macro['body']):
                    changed=True;return macro['body']
                return key
            result=base._COMMAND.sub(expand,target)
            if len(result)>4096:raise ValueError('Expanded TeX filename exceeds bound')
            if not changed:return result
            target=result
        raise ValueError('Filename macro expansion exceeds bound')

    def _child(self,name,target,stack):
        target=self._filename(target)
        if posixpath.splitext(target)[1].lower() in {'.bib','.bbl'}:
            return self.marker('bibliography input '+target)
        dependency=self.resolve(name,target,'.tex',required=False)
        if dependency is None:
            if self.external_layout(target):
                self.notes.append('Unavailable standard formatting input: '+target)
                return self.marker('external graphics/typesetting input '+target)
            raise ValueError('Missing TeX dependency in '+name+': '+target)
        if posixpath.splitext(dependency)[1].lower() in base._LIBRARY:
            child=self.library(dependency)
        else: child=self.process(dependency,stack+(name,))
        return '\nSOURCE FILE: '+dependency+'\n'+child+'\n'

    def process(self,name,stack=(),probe=False):
        if name in stack:raise ValueError('Cyclic TeX dependency: '+' -> '.join(stack+(name,)))
        if len(stack)>100:raise ValueError('TeX dependency depth exceeds the supported bound')
        if name not in self.included:self.included.append(name)
        text=self.text(name);parts=[];cursor=0
        self.work_bytes+=len(text.encode())
        if self.work_bytes>base.MAX_EXPANDED:raise ValueError('Repeated TeX dependency expansion exceeds the supported bound')
        while cursor<len(text) and not self.document_ended:
            start=text.find('\\',cursor)
            if start<0:parts.append(text[cursor:]);break
            parts.append(text[cursor:start]);match=base._COMMAND.match(text,start)
            if not match:parts.append(text[start:]);break
            original=match.group(1);command=original;end=match.end()
            seen=set()
            while '\\'+command in self.macros:
                macro=self.macros['\\'+command]
                if macro.get('ambiguous'):
                    if _DEPS.search(macro['body']):raise ValueError('Conditional include alias has unresolved branch: '+command)
                    break
                single=re.fullmatch(r'\\([A-Za-z@]+|.)',macro['body'].strip())
                if macro['kinds'] or not single:break
                if command in seen:raise ValueError('Cyclic TeX command alias')
                seen.add(command);command=single.group(1)
            if command in _DEFS:
                target,kinds,body,end,simple=_definition(text,end,command)
                if command.endswith('environment'):
                    if _DEPS.search(body):self.dependent_environments.add(target)
                else:self.macros[target]={'kinds':kinds,'body':body,'simple':simple,'command':command,'ambiguous':bool(self.conditional_depth)}
                parts.append(text[start:end])
            elif '\\'+original in self.macros and (_DEPS.search(self.macros['\\'+original]['body']) or re.search(r'\\(?:begin|end)\s*\{document\}|\\bye\b',self.macros['\\'+original]['body'])):
                macro=self.macros['\\'+original]
                if macro.get('ambiguous'):raise ValueError('Conditional include macro has conflicting definitions: '+original)
                if not macro['simple']:raise ValueError('Unsupported delimited include macro: '+original)
                args,end=self._arguments(text,end,macro['kinds'])
                body=macro['body']
                for i,arg in reversed(list(enumerate(args,1))):body=body.replace('#'+str(i),arg)
                if re.search(r'#[1-9]',body):raise ValueError('Unresolved include macro parameter')
                self.expansions+=1
                self.work_bytes+=len(body.encode())
                if self.expansions>10000 or self.work_bytes>base.MAX_EXPANDED:raise ValueError('Literal macro expansion exceeds the supported bound')
                parts.append('\n[EXPANDED LITERAL INCLUDE MACRO: '+original+']\n')
                text=text[:start]+body+text[end:];cursor=start;continue
            elif command in {'iftrue','iffalse'}:
                active,end=base._literal_conditional(text,end,command=='iftrue')
                parts.append(self.marker('inactive literal conditional branch'))
                text=text[:start]+active+text[end:];cursor=start;continue
            elif command in {'ifthenelse','ifstrequal','ifstrempty','IfValueTF','IfValueT','IfNoValueTF','IfBooleanTF'}:
                count = 4 if command=='ifstrequal' else 2 if command=='IfValueT' else 3
                arguments=[]
                for _ in range(count):
                    argument,end=_token(text,end);arguments.append(argument)
                for argument in arguments:
                    if _DEPS.search(argument) or any(_DEPS.search(m['body']) and key in argument for key,m in self.macros.items()):
                        raise ValueError('Unresolved conditional file dependency: '+command)
                    cursor_in=0
                    while cursor_in<len(argument):
                        token=base._COMMAND.search(argument,cursor_in)
                        if not token:break
                        cursor_in=token.end();kind=token.group(1)
                        if kind not in _DEFS:continue
                        target,kinds,body,cursor_in,simple=_definition(argument,cursor_in,kind)
                        self.macros[target]={'kinds':kinds,'body':body,'simple':simple,'command':kind,'ambiguous':True}
                parts.append(text[start:end])
            elif command=='newif':
                _,end=_token(text,end);parts.append(text[start:end])
            elif command.startswith('if') and command not in {'ifthenelse','ifstrequal','ifstrempty'}:
                self.conditional_depth+=1;parts.append(text[start:end])
            elif command=='fi':
                self.conditional_depth=max(0,self.conditional_depth-1);parts.append(text[start:end])
            elif command in {'input','include','subfile'}:
                end=_space(text,end)
                if end<len(text) and text[end]=='*':end+=1
                target,end=base._argument(text,_space(text,end),bare=command=='input')
                if target.startswith('\\jobname'):
                    stem=posixpath.splitext(posixpath.basename(self.main))[0]
                    target=target.replace('\\jobname',stem,1)
                if posixpath.splitext(target)[1].lower() in {'.aux','.toc','.out','.lof','.lot'}:
                    parts.append(self.marker('generated auxiliary input '+target))
                elif command=='include' and self.include_only is not None and target.removesuffix('.tex') not in self.include_only:
                    parts.append(self.marker('excluded by includeonly: '+target))
                else:parts.append(self._child(name,target,stack))
            elif command in _IMPORTS:
                directory,end=base._argument(text,_space(text,end));target,end=base._argument(text,_space(text,end))
                parts.append(self._child(name,posixpath.join(directory,target),stack))
            elif command=='includeonly':
                names,end=base._argument(text,_space(text,end))
                if any(c in names for c in '\\#$'):raise ValueError('Dynamic includeonly selection')
                self.include_only={n.strip().removesuffix('.tex') for n in names.split(',')}
                parts.append(text[start:end])
            elif command in {'InputIfFileExists','IfFileExists'}:
                target,end=base._argument(text,_space(text,end));yes,end=base._group(text,end);no,end=base._group(text,end)
                dependency=self.resolve(name,target,'.tex',required=False)
                if dependency is None and not no.strip() and not self.external_layout(target):
                    raise ValueError('Missing optional TeX dependency without fallback in '+name+': '+target)
                if dependency is None and posixpath.splitext(target)[1].lower() in base._LIBRARY:
                    raise ValueError('Unknown host-distribution file-existence branch: '+target)
                active=yes if dependency else no
                if dependency and command=='InputIfFileExists':active+='\n\\input{'+target+'}'
                parts.append(self.marker('literal file-existence branch: '+target))
                text=text[:start]+active+text[end:];cursor=start;continue
            elif command in {'usepackage','RequirePackage','documentclass','documentstyle','LoadClass','LoadClassWithOptions'}:
                end=_space(text,end)
                while end<len(text) and text[end]=='[':
                    _,end=base._group(text,end,'[',']');end=_space(text,end)
                targets,end=base._argument(text,end);parts.append(text[start:end])
                for target in targets.split(','):
                    target=target.strip()
                    if not target:continue
                    if '\\' in target:
                        if 'font' in target.lower():
                            self.notes.append('Unexecuted font-package selection');continue
                        raise ValueError('Dynamic formatting package name: '+target)
                    suffix='.sty' if command in {'usepackage','RequirePackage','documentstyle'} else '.cls'
                    dependency=self.resolve(name,target,suffix,required=False)
                    if dependency:parts.append(self.library(dependency))
            elif command in {'verbatiminput','lstinputlisting'}:
                end=base._optional_arguments(text,_space(text,end));target,end=base._argument(text,_space(text,end))
                dep=self.resolve(name,target,required=True)
                if dep not in self.included:self.included.append(dep)
                literal=self.sources[dep]
                self.work_bytes+=len(literal.encode())
                if self.work_bytes>base.MAX_EXPANDED:raise ValueError('Literal listing exceeds supported bound')
                parts.append('\nSOURCE FILE (literal listing): '+dep+'\n'+literal+'\n')
            elif command=='begin':
                environment,opening=base._group(text,end)
                if environment in self.dependent_environments:
                    raise ValueError('Custom environment contains unresolved file dependencies: '+environment)
                if environment in base._DRAWING or environment in _BIB:
                    end=base._environment_end(text,opening,environment)
                    parts.append(self.marker('bibliography' if environment in _BIB else 'figure drawing '+environment))
                elif environment in base._VERBATIM:
                    closing=re.search(r'\\end\s*\{'+re.escape(environment)+r'\}',text[opening:])
                    if not closing:raise ValueError('Unterminated TeX verbatim environment')
                    end=opening+closing.end();parts.append(text[start:end])
                else:end=opening;parts.append(text[start:end])
            elif command=='verb':
                if end<len(text) and text[end]=='*':end+=1
                if end>=len(text) or text[end].isspace():raise ValueError('Malformed TeX verbatim command')
                closing=text.find(text[end],end+1)
                if closing<0:raise ValueError('Unterminated TeX verbatim command')
                end=closing+1;parts.append(text[start:end])
            elif command in {'includegraphics','epsfig','psfig','epsfbox','epsffile','includepdf'}:
                end=_space(text,end)
                if end<len(text) and text[end]=='*':end=_space(text,end+1)
                while end<len(text) and text[end]=='[':
                    _,end=base._group(text,end,'[',']');end=_space(text,end)
                target,end=base._argument(text,end,bare=command in {'epsffile','epsfbox'})
                parts.append(self.marker('graphic '+target))
            elif command in {'bibliography','bibliographystyle','addbibresource'}:
                target,end=base._argument(text,base._optional_arguments(text,_space(text,end)))
                parts.append(self.marker('bibliography '+target))
            elif command=='printbibliography':
                end=base._optional_arguments(text,end);parts.append(self.marker('bibliography'))
            elif command in {'bibitem','entry'}:
                # Retain nonstandard reference lists rather than discarding a
                # guessed tail that could include an appendix or matter table.
                self.notes.append('Nonstandard bibliography retained as source')
                parts.append(text[start:end])
            elif command=='end':
                offset=_space(text,end)
                if offset<len(text) and text[offset]=='{':
                    environment,end=base._group(text,offset);parts.append(text[start:end])
                    if environment.strip()=='document':self.document_ended=True
                elif self.main_selection=='unique_plain_tex_root':
                    parts.append(text[start:end]);self.document_ended=True
                else:raise ValueError('Missing literal end-environment argument')
            elif command=='bye':
                parts.append(text[start:end]);self.document_ended=True
            elif command=='endinput':break
            elif command in {'openin','read','readline','scantokens','@input','@input@','@@input','@iinput'}:
                raise ValueError('Unsupported executable TeX dependency command: \\'+command)
            else:parts.append(text[start:end])
            cursor=end
        return ''.join(parts)

    def _reset(self,main):
        self.main=main;self.included=[];self.omissions=[];self.libraries=[]
        self.work_bytes=0;self.document_ended=False;self.macros={};self.include_only=None;self.expansions=0;self.notes=[];self.dependent_environments=set();self.conditional_depth=0

    def _markers(self,text):
        # Definitions and verbatim examples do not declare a document root.
        cursor=0;out=[]
        while cursor<len(text):
            match=base._COMMAND.search(text,cursor)
            if not match:out.append(text[cursor:]);break
            out.append(text[cursor:match.start()]);cmd=match.group(1);end=match.end()
            if cmd in _DEFS:
                try:_,_,_,end,_=_definition(text,end,cmd)
                except ValueError:pass
            elif cmd=='begin':
                try:env,opening=base._group(text,end)
                except ValueError:env,opening='',end
                if env in base._VERBATIM:
                    closing=re.search(r'\\end\s*\{'+re.escape(env)+r'\}',text[opening:])
                    if closing:end=opening+closing.end()
                else:out.append(text[match.start():end])
            else:out.append(text[match.start():end])
            cursor=end
        return ''.join(out)

    def choose_main(self):
        candidates=[]
        for name in self.sources:
            if posixpath.splitext(name)[1].lower() in base._LIBRARY|{'.bib','.bbl','.dtx','.ins','.json'}:continue
            text=self._markers(self.text(name))
            if base._MAIN.search(text):candidates.append(name)
        # A top-level wrapper can consist entirely of inputs. It must not be
        # mistaken for an unused file while its preamble alone becomes the root.
        edges={}
        for name in self.sources:
            if posixpath.splitext(name)[1].lower() in base._LIBRARY|{'.bib','.bbl','.json'}:continue
            text=self._markers(self.text(name));targets=[]
            for match in re.finditer(r'\\(?:input|include|subfile)\*?\s*(?:\{([^{}\\#$]+)\}|([^\s{}\\#$]+))',text):
                targets.append(match.group(1) or match.group(2))
            for match in re.finditer(r'\\(?:import|subimport|inputfrom|subinputfrom)\s*\{([^{}\\#$]+)\}\s*\{([^{}\\#$]+)\}',text):
                targets.append(posixpath.join(match.group(1),match.group(2)))
            deps=set()
            for target in targets:
                for directory in (posixpath.dirname(name),''):
                    for candidate in (target,target+'.tex'):
                        path=base._normal_name(posixpath.join(directory,candidate))
                        if path in self.sources:deps.add(path)
            edges[name]=deps
        changed=True
        while changed:
            changed=False
            for name,deps in edges.items():
                if name not in candidates and any(child in candidates for child in deps):
                    candidates.append(name);changed=True
        if not candidates:
            plain=[n for n in self.sources if n.lower().endswith(('.tex','.ltx'))
                   and re.search(r'\\end(?:\s|$)',self._markers(self.text(n)))
                   and len(self.text(n))>=1000
                   and re.search(r'\\(?:title|Title|btitle|magnification|centerline)\b',self.text(n))]
            if len(plain)==1:
                self._reset(plain[0]);self.main_selection='unique_plain_tex_root';return plain[0]
            raise ValueError('Response is not usable full TeX source: no unambiguous main document')
        excluded={}
        for name in candidates:
            unbacked=_BACKUP.sub('',name)
            if unbacked!=name and unbacked in self.sources:
                excluded[name]='Explicit backup suffix with corresponding primary file';continue
            text=self.text(name)
            if re.search(r'^\s*%\s*auto-ignore\b',self.sources[name],re.M|re.I):
                excluded[name]='arXiv auto-ignore directive';continue
            body=re.search(r'\\begin\s*\{document\}\s*(.{0,800})',text,re.S)
            if body and re.match(r'(?:We\s+thank\s+(?:the\s+)?(?:Referee|Reviewer)|Dear\s+(?:Editor|Referee|Reviewer))\b',body.group(1),re.I):
                excluded[name]='Explicit referee/editor correspondence opening';continue
            title=re.search(r'\\title\s*\{([^{}]{0,600})\}',text,re.S)
            if title and re.search(r'(?:response|reply|replies)\s+to\s+(?:the\s+)?(?:referee|reviewer|editor)',title.group(1),re.I):
                excluded[name]='Explicit referee-response title'
        preferred=[]
        for name,body in self.sources.items():
            if posixpath.basename(name).lower()=='00readme.json':
                metadata=json.loads(body)
                for row in metadata.get('sources',[]):
                    path=base._normal_name(posixpath.join(posixpath.dirname(name),row['filename']))
                    if row.get('usage')=='toplevel':preferred.append(path)
                    if row.get('usage')=='ignore':excluded[path]='arXiv ignore metadata'
        active=[n for n in candidates if n not in excluded]
        dependencies=set();failures={};outputs={}
        for candidate in active:
            self._reset(candidate)
            try:outputs[candidate]=self.process(candidate,probe=True)
            except ValueError as error:failures[candidate]=error
            dependencies.update(n for n in self.included if n!=candidate)
        roots=[n for n in active if n not in dependencies]
        if preferred:
            if len(set(preferred))!=1 or preferred[0] not in candidates:raise ValueError('Ambiguous or missing arXiv top-level TeX source')
            roots=[preferred[0]];self.main_selection='arxiv_toplevel_metadata'
            if roots[0] in excluded:
                self._reset(roots[0])
                try:outputs[roots[0]]=self.process(roots[0],probe=True)
                except ValueError as e:failures[roots[0]]=e
        elif len(roots)>1 and all(n in outputs for n in roots) and len({outputs[n] for n in roots})==1:
            roots=[sorted(roots)[0]];self.main_selection='identical_prepared_roots'
        if len(roots)!=1:raise ValueError('Ambiguous independent main TeX documents: '+', '.join(roots or active))
        main=roots[0]
        if main in failures:raise failures[main]
        self.excluded_roots=[{'file':n,'reason':r} for n,r in sorted(excluded.items())]
        self._reset(main)
        return main


def _prepare(sources):
    if len(sources)>base.MAX_MEMBERS or sum(len(t.encode()) for t in sources.values())>base.MAX_EXPANDED:
        raise ValueError('Source text exceeds expansion bound')
    cleaner=Cleaner(sources);main=cleaner.choose_main()
    cleaned='SOURCE FILE: '+main+'\n'+cleaner.process(main)
    if not cleaner.document_ended:
        raise ValueError('Main TeX source has no resolved document terminator')
    cleaned=re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+','\n\n',cleaned).strip()+'\n'
    raw=''.join('\nSOURCE FILE: '+name+'\n'+text+'\n' for name,text in sources.items())
    return cleaned,raw,{'cleaner_version':CLEANER_VERSION,'main_file':main,'main_selection':cleaner.main_selection,
                      'included_files':cleaner.included,'unexecuted_library_files':cleaner.libraries,
                      'omissions':cleaner.omissions,'excluded_document_roots':cleaner.excluded_roots,
                      'preparation_notes':sorted(set(cleaner.notes)),'literal_include_expansions':cleaner.expansions,
                      'cleaned_characters':len(cleaned),'raw_characters':sum(len(t) for t in sources.values())}


def prepare_tex(content):
    return _prepare(base._archive_sources(content))


def clean_tex(content):
    return prepare_tex(content)[0]
