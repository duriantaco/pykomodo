# Changelog

## [0.1.1] - 2025-03-11

### Fixed
- Built-in ignores added `.env`

### Added
- **Automatic redaction of api keys** pykomodo automatically scans your repo and redacts all api keys. 


## [0.1.0] - 2025-02-28

### Fixed
- Resolved an issue in the chunking logic to ensure that the exact number of chunks is correct

### Added
- **Introducing PDF chunking** which will work for `--equal-chunks` and `--max-chunk-size`.
- **New flag** to specify what file types you want

Bumped version up to 0.1.0 for major changes

## [0.0.6] - 2025-02-25
### Added
- **Type hints** for key classes (`ParallelChunker`, `EnhancedParallelChunker`, `PyCConfig`), improving IDE auto-completion and static analysis
- **Pydantic-based configuration** example (`pykomodo_config.py`), demonstrating how to validate and run the chunker with typed settings

## [0.0.4] - 2025-02-24
### Added
- **AST-based semantic chunking** for Python files:
  - Use `--semantic-chunking` on the CLI or `semantic_chunking=True` in the Python API
  - Splits `.py` files by top-level functions and classes
  - Falls back to a single chunk if a file has invalid syntax
  - Non-Python files remain chunked by the existing size-based logic
- Updated tests to cover semantic chunking scenarios, including syntax-error edge cases
- **Dry Run before chunking**: Added dry-run to see what files were added/removed, no actual chunking is carried out

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