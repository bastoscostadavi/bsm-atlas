# Static catalogue scale test

This benchmark creates **100,000 synthetic paper records and 5,000 distinct gauge–matter specifications**. The spectra are the SM with different multiplicities of a real singlet scalar; their references are explicitly fictional test records. Twenty percent of the papers link to a model. One model has 10,000 references and 10,000 evidence associations.

The fixtures are generated in temporary storage, validated through the catalogue's ordinary mathematical and projection code, and exercised through the same static data format and JavaScript loader used by the site. They are never ingested or published as scientific records.

Run after `make build`:

```sh
python3 -B benchmarks/static_catalogue.py --papers 100000 --models 5000
```

The recorded [measurements](scalability.json) include:

- Initial data: four requests, about **0.9 MB gzipped**. No full model tables, paper metadata or quotations are fetched at startup.
- A 10,000-reference model: **20 full paper records** loaded for its first reference page.
- A search with 1,000 matches: **20 result records** loaded for its first page.
- A 10,000-association evidence list: **20 associations** loaded on opening its first page.

The timings use a filesystem-backed fetch harness, so they measure local processing and data access, **not browser rendering or network page-load time**. Record counts, number of requests and transferred byte counts are useful delivery checks; real papers, model complexity and citation distributions will differ.

`tests/atlas-store.test.mjs` separately checks the real catalogue, DOM output, exact counts, reference and evidence pagination, indexed search, old entry links, request failures, stale responses, actual execution of the bundled search worker and the worker-unavailable fallback. `tests/test_snapshot.py` checks source restoration and preservation of active ingestion data.
