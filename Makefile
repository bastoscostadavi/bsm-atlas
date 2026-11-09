PYTHON ?= python3

.PHONY: prepare build check serve site

prepare:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/data_snapshot.py restore

build: prepare
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/build_problem_preview.py
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/build_mechanism_preview.py
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m bsm_atlas build

check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/check.py

serve: build
	$(PYTHON) -m http.server 8000 --bind 127.0.0.1 --directory website

site: build
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/package_site.py
