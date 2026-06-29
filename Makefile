PYTHON ?= .venv/bin/python

.PHONY: test lint typecheck e2e converge montecarlo sensitivity soak

test:
	$(PYTHON) -m pytest -q --cov=rocketsim --cov-report=term-missing

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy rocketsim tests

e2e:
	$(PYTHON) -m rocketsim.cli e2e

converge:
	$(PYTHON) -m rocketsim.cli converge

montecarlo:
	$(PYTHON) -m rocketsim.cli montecarlo

sensitivity:
	$(PYTHON) -m rocketsim.cli sensitivity

soak:
	$(PYTHON) -m rocketsim.cli soak
