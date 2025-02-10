.PHONY: test build clean

test:
	pytest tests/

build:
	python -m build

clean:
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +