# Overview

This repository contains a parallel file processing and chunking tool implemented in Cython. It scans one or more directories, applies ignore rules, skips binary files, calculates a priority score, and writes out file contents in chunks of a configurable size.

# Key Features

1. Parallel scanning with a configurable number of threads
2. Ignore patterns + “unignore” overrides
3. Binary file skipping based on extension or null-byte detection
4. Priority scoring for matched rules

## Two output modes:
* Multi-chunk: Writes each chunk to a separate chunk-0.txt, chunk-1.txt, …
* Repo aggregator aggregator: Writes all chunked output into a single file or to stdout if streaming.

# Requirements
* Python 3.7+
* Cython (for building .pyx files)
* A C compiler toolchain (e.g., gcc or clang)
* (Optional) argparse for the CLI usage (built into Python standard library)

# Installation & Build

Clone or download this repository.

Install dependencies (Cython, etc.):

```bash
pip install cython
```

Build the Cython extension in place:

```bash
python setup.py build_ext --inplace
```

This compiles the .pyx sources into a native extension module (e.g., multi_dirs_chunker.cpython-39-darwin.so on macOS).

Check that compilation succeeded. You should see a .so or .pyd file in the src/ folder.

# Running via CLI
A typical entry point is cli.py, which uses argparse to expose a flexible command-line interface. Basic usage:

```bash
python cli.py [OPTIONS] [DIRS...]
```

## Common Options
* `DIRS`
The directories to scan. Defaults to the current directory (.) if none provided.

* `--ignore PATTERN ...`
One or more patterns to ignore (in addition to built-in ones). Example: --ignore *.log --ignore .git/**.

* `--unignore PATTERN ...`
Patterns to override the ignore rules. E.g., if --ignore includes *.log, but you want important.log, you can --unignore important.log.

* `--binary-extensions EXT ...`
File extensions that should be treated as binary and skipped. Defaults to exe, dll, so, etc.

* `--priority-rule PATTERN,SCORE`
Add a rule to give matched files some priority. Example: --priority-rule '.*\\.py,20'. You can repeat this option.

* `--max-size SIZE`
Maximum chunk size in bytes (if not using token mode) or tokens (if --token-mode is used). Defaults to 10 MB (10 * 1024 * 1024).

* `--token-mode`
Interprets --max-size as a token count rather than bytes.

* `--output-dir DIR`
If not using --stream or aggregator mode, chunk files will be placed here. Defaults to the current directory if omitted.

* `--stream`
Output everything to stdout instead of creating files.

* `--num-threads N`
Number of parallel worker threads.

* `--whole_chunk_mode-output`
If set, produces a single-file aggregator named whole_chunk_mode-output.txt (unless --stream is used, in which case it merges all content to stdout). Otherwise, the default is multiple chunk-N.txt files.

# Direct usage in python

You can also import the compiled extension and use the ParallelChunker class directly in Python:

```python
from multi_dirs_chunker import ParallelChunker

chunker = ParallelChunker(
    user_ignore=["*.log", ".git/**"],
    priority_rules=[(".*\\.py", 20)],
    max_size=1024 * 1024,  # 1 MB
    token_mode=False,
    output_dir="my_output",
    stream=False,
    num_threads=4,
    repomix_mode=False
)

chunker.process_directories(["./my_project"])
chunker.close()
```

Set =True if you want a single aggregated file in my_output/repomix-output.txt.

# FAQ

* Why have a single-file aggregator?

Some scenarios (like advanced code review or certain LLM-based tools) prefer a single big text file. The --repomix-mode option makes it easy.

* How can I skip even more files?

Use --ignore multiple times or add to BINARY_FILE_EXTENSIONS and built-in ignore patterns in multi_dirs_chunker.pyx.

* How do I choose between token vs. byte chunking?

If you’re sending data to a large language model with a known max token limit, --token-mode is better. Otherwise, normal byte-based chunking is simpler.
