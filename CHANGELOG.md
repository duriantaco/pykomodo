# Changelog

## [0.0.4] - 2025-03-02
### Added
- **AST-based semantic chunking** for Python files:
  - Use `--semantic-chunking` on the CLI or `semantic_chunking=True` in the Python API
  - Splits `.py` files by top-level functions and classes
  - Falls back to a single chunk if a file has invalid syntax
  - Non-Python files remain chunked by the existing size-based logic
- Updated tests to cover semantic chunking scenarios, including syntax-error edge cases
- Added dry-run to see what files were added/removed, no actual chunking is carried out

## [0.0.3] - 2025-02-18
## Changed
- Reorganized code into `src/pykomodo` so that `import pykomodo` works properly when installed
- Updated pyproject.toml to use [tool.setuptools.packages.find] for correct packaging
- Made path adjustments to the core files 

## [0.0.1] - 2025-02-11
### Changed
- Revised `--ignore` and `--unignore` to use `action="append"`, allowing multiple flags without overwriting

## [0.0.0] - 2025-02-10
- Initial release
- Parallel chunking functionality
- LLM optimizations