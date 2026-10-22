PYTHON ?= python3

.PHONY: build check serve

build:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m bsm_atlas build

check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/check.py

serve:
	$(PYTHON) -m http.server 8000 --bind 127.0.0.1 --directory website
