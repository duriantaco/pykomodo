# Komodo Parallel Chunker
A multi-threaded utility for scanning directories, ignoring or un-ignoring files by pattern, skipping binary files, assigning priority scores, and splitting text content into chunks.

It supports both command-line usage (via the included cli.py) and integration into Python scripts (via the ParallelChunker class). You can choose to chunk by bytes or by tokens (whitespace-delimited), stream all output to stdout, or write them into separate chunk files (or one single aggregator file).

# Motivation: 

* Purpose: This project aims to recursively scan one or more directories, filter out undesired files (e.g., binary files, certain patterns), then chunk the textual contents into smaller segments. It's designed for workflows where you need to process large sets of text-based files efficiently—especially for tasks like feeding context to Large Language Models (LLMs), indexing content for search, or extracting information from large codebases.

* Why: Handling large repositories with thousands of text files can be time-consuming and prone to memory issues when done sequentially. Our chunker uses a thread pool to read these files in parallel, ignoring files that match certain patterns (e.g., .git/, node_modules/), skipping binary files, and chunking only what you care about (e.g., .py, .cpp, docs, or other textual files). Then it can output them as multiple small chunks or one big aggregated file, sorted by priority (higher priority patterns first).

# Features
* Parallel file reading through a pool of threads.
* Ignore and Unignore patterns to skip or force-include certain files.
* Binary file detection (by extension or by scanning for null bytes).
* Custom priority rules (e.g., place .py at priority 10, .cpp at priority 20, etc.).
* Token-based or byte-based chunking.
* Multiple output modes:
    * Write each chunk to a separate file: chunk-1.txt, chunk-2.txt, etc.
    * Stream everything to stdout (for piping).
    * Write to a single aggregator file (when --whole_chunk-mode is set).
* Configurable via CLI or direct Python usage.

# Installation


```bash
pip install komodo
```

# CLI Usage

A simple CLI script, cli.py, is included. If installed properly (either locally or from PyPI with an entry_points definition), you can run:

```bash
komodo --help
```

```bash
python cli.py --help
```

```bash
usage: cli.py [-h] [--ignore ...] [--unignore ...] [--binary-extensions ...]
              [--priority-rule pattern,score] [--max-size INT]
              [--token-mode] [--output-dir DIR] [--stream]
              [--num-threads INT] [--whole_chunk-mode]
              [dirs ...]

Chunk and optionally produce a single-file aggregator output for text-based files.

positional arguments:
  dirs                  One or more directories to scan. Defaults to current directory if none.

optional arguments:
  -h, --help            show this help message and exit
  --ignore ...          Ignore patterns (e.g., *.log, .git/**)
  --unignore ...        Unignore patterns to override ignores
  --binary-extensions ...
                        File extensions treated as binary (skipped)
  --priority-rule       'pattern,score' format (can be repeated)
  --max-size INT        Max chunk size in bytes or tokens
  --token-mode          If set, interpret max-size as tokens
  --output-dir DIR      Output directory for chunked files
  --stream              If set, write all output to stdout
  --num-threads INT     Number of worker threads for parallel reading
  --whole_chunk-mode    Use single aggregator file instead of multiple

```

# Real-World Demo

Suppose you have a local clone of the Scikit-Learn repository. Let's chunk it by bytes (10 KB each chunk) and place it into a single aggregator file, ignoring *.png and skipping docs/_build:

```bash
python cli.py ~/repos/scikit-learn \
    --ignore "*.png" --ignore "_build" \
    --binary-extensions exe dll so \
    --priority-rule "*.py,10" --priority-rule "*.rst,5" \
    --max-size 10240 \
    --output-dir ./chunks_output \
    --whole_chunk-mode \
    --num-threads 8
``` 


```python
from src.core.multi_dirs_chunker import ParallelChunker

chunker = ParallelChunker(
    user_ignore=[".git", "*.pyc"],
    user_unignore=[], 
    binary_extensions=["exe", "dll", "so"],
    priority_rules=[("*.py", 10), ("*.md", 5)],
    max_size=2000,
    token_mode=True,     # True => interpret max_size as tokens
    output_dir="my_chunks",
    stream=False,        # False => write to files
    num_threads=4,
    whole_chunk_mode=False
)

chunker.process_directories([
    "/path/to/my_python_app",
    "/path/to/another_dir"
])

chunker.close()
```
# Configuration and Parameters
Below is a summary of the main parameters you can pass either via CLI or to ParallelChunker:

* user_ignore / --ignore
A list of patterns (fnmatch-style) to ignore. Example: [".git", "*.pyc", "node_modules"].

* user_unignore / --unignore
A list of patterns to override the ignore list. Example: if you generally ignore *.png but want to re-include banner.png, put ["banner.png"] in unignore.

* binary_extensions / --binary-extensions
Extensions to treat as binary. Example: ["exe", "dll", "so"].

* priority_rules / --priority-rule
A list of (pattern, score) pairs. Higher score => higher priority => processed/written first.
CLI: --priority-rule '*.py,10' --priority-rule '*.md,5'

* max_size / --max-size
If token_mode=False, treat as max bytes per chunk. If token_mode=True, treat as max tokens per chunk.

* token_mode / --token-mode
If True, chunk by whitespace-delimited tokens. If False, chunk by raw bytes.

* output_dir / --output-dir
Directory where chunk files (or the aggregator file) are written. Defaults to current directory if omitted.

* stream / --stream
If True, write to stdout instead of creating chunk files. Useful for piping to other commands.

* num_threads / --num-threads
How many worker threads to spawn for parallel reading.

* *hole_chunk_mode / --whole_chunk-mode
If True, produce a single aggregator file named whole_chunk_mode-output.txt (or stdout if --stream).
If False, produce multiple chunk-N.txt files.