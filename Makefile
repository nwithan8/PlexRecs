PYTHON_BINARY := python3
VIRTUAL_ENV := venv
VIRTUAL_BIN := $(VIRTUAL_ENV)/bin
PROJECT_NAME := PlexRecs

## help - Display help about make targets for this Makefile
help:
	@cat Makefile | grep '^## ' --color=never | cut -c4- | sed -e "`printf 's/ - /\t- /;'`" | column -s "`printf '\t'`" -t

## build - Builds the project in preparation for release
build:
	$(PYTHON_BINARY) setup.py sdist bdist_wheel

## coverage - Test the project and generate an HTML coverage report
coverage:
	$(VIRTUAL_BIN)/pytest --cov=$(PROJECT_NAME) --cov-branch --cov-report=html --cov-report=term-missing

## clean - Remove the virtual environment and clear out .pyc files
clean:
	rm -rf $(VIRTUAL_ENV)
	find . -name '*.pyc' -delete
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info

## install - Install the project locally
install:
	$(PYTHON_BINARY) -m pyenv virtualenv 3.10.3 $(PROJECT_NAME)
	$(PYTHON_BINARY) -m pyenv local $(PROJECT_NAME)
	$(VIRTUAL_BIN)/pip install -r requirements.txt

## test - Test the project
test:
	$(VIRTUAL_BIN)/pytest --exitfirst --verbose --failed-first

.PHONY: help build coverage clean black black-check format format-check install isort isort-check lint mypy test