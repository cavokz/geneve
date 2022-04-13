ifeq ($(VENV),)
	PYTHON:=python3
else
	PYTHON:=source $(VENV)/bin/activate; python3
endif

all: lint tests

prereq:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

lint:
	$(PYTHON) -m flake8 geneve tests --ignore D203 --max-line-length 120 --exclude geneve/kql

tests: tests/*.py
	$(PYTHON) -m pytest

online_tests: tests/*.py
	TEST_SIGNALS_QUERIES=1 $(PYTHON) -m pytest tests/test_emitter_*.py

run:
	$(PYTHON) -m geneve --version
	$(PYTHON) -m geneve --help
	$(PYTHON) -m geneve

pkg_build:
	$(PYTHON) -m build

pkg_install:
	$(PYTHON) -m pip install --force-reinstall dist/geneve-*.whl

pkg_try:
	geneve --version
	geneve --help
	geneve

package: pkg_build pkg_install pkg_try

.PHONY: lint tests online_tests run
