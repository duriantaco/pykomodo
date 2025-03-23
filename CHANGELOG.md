# Changelog

## [0.1.5] - 2025-03-24

### Patch
- Ignore venv 

## [0.1.4] - 2025-03-23

### Fixed
- Improved ignore pattern system to properly exclude virtual environments, site-packages, and test data
- Fixed issue with verbose parameter in file reading methods
- Enhanced builtin ignores to properly handle paths with double-star notation (`**/pattern/**`)

### Added
- Support for reading `.pykomodo-ignore` file in project directories
- Integration with existing `.gitignore` files for more consistent ignoring
- Smarter Python file handling in virtual environments to prevent processing library files
- Additional ignore patterns for common directories and file types that should be excluded:
  - Better handling for environment directories (`venv`, `.venv`, `env`, etc.)
  - Proper ignoring of package metadata and build artifacts
  - Exclusion of temporary files and system directories
  - Improved handling of test data directories

### Changed
- Modified Python file unignoring to respect virtual environment paths
- Improved pattern matching for more reliable file filtering

## [0.1.3] - 2025-03-19

### Fixed
- Fixed ignore node modules, but if it doesn't work also, try this `komodo . --equal-chunks 5 --file-type js --ignore "**/node_modules/**"`. Difference here is we are specifying the file-type

## [0.1.2] - 2025-03-14

### Added
- **Token-Based Chunking**: Added a new `TokenBasedChunker` that provides token-based chunking with tiktoken integration
  - `--max-tokens` CLI flag for accurate token counting using tiktoken (when available)
  - Fallback to word-based counting when tiktoken isn't installed
  - Compatible with both equal chunks and maximum size approaches
  - Handles long lines by intelligently splitting them into multiple chunks
  - Applies semantic chunking for Python files
  - Integrates with the PDF chunking system

### Improved
- Better handling of lines that exceed token limits
- Verbose mode with detailed output on token counts

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