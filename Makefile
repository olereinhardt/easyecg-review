.PHONY: install test build clean
install:
	python3 -m pip install -e '.[dev]'
test:
	python3 -m pytest -q
build:
	python3 -m build
clean:
	rm -rf build dist .pytest_cache src/*.egg-info
