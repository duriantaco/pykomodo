# Changelog

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