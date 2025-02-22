<p align="center">
  <img src="assets/KOMODO.png" alt="KOMODO Logo" width="200">
</p>

A Python-based parallel file chunking system designed for processing large codebases into LLM-friendly chunks. The tool provides intelligent file filtering, multi-threaded processing, and advanced chunking capabilities optimized for machine learning contexts.

## Core Features

* Parallel Processing: Multi-threaded file reading with configurable thread pools

* Smart File Filtering:

    * Built-in patterns for common excludes (.git, node_modules, pycache, etc.)
    * Customizable ignore/unignore patterns
    * Intelligent binary file detection


* Flexible Chunking:

    * Equal-parts chunking: Split content into N equal chunks
    * Size-based chunking: Split by maximum chunk size
    * ** ***NEW*** **: **Semantic (AST-based) chunking** for Python files
  
* ** ***NEW*** ** Dry-run mode: If you only want to see which files **would** be chunked


* LLM Optimizations:

    * Metadata extraction (functions, classes, imports, docstrings)
    * Content relevance scoring
    * Redundancy removal across chunks
    * Configurable context window sizes

## Installation

```bash
pip install komodo==0.0.4
```

## Quick Start

### Command Line Usage

#### Basic usage 

```bash
# Split into 5 equal chunks
komodo . --equal-chunks 5

# Process multiple directories
komodo path1/ path2/ --max-chunk-size 1000
```

#### Chunking Modes

Komodo supports two chunking modes:

##### Fixed Number of Chunks: 

```bash
# Split into 5 equal chunks
komodo . --equal-chunks 5 --output-dir chunks
```

##### Fixed Number of Tokens:

```bash
# Split into chunks of 1000 tokens each
komodo . --max-chunk-size 1000 --output-dir chunks
```

##### ** ***NEW*** **: Semantic (AST-based) Chunking (For Python)

```bash
# Use semantic chunking for Python files
# The .py files are split by top-level function/class boundaries;
# all non-.py files are chunked by your usual line- or size-based approach.
komodo . --max-chunk-size 200 --semantic-chunks
```

* What does `--max-chunk-size 200` mean here?

It means that when chunking lines from the file, Komodo aims for chunks no more than 200 **lines (not tokens)**. However, because we’re in “semantic” mode, each top-level Python definition (function or class) is considered atomic. If a single function or class is itself bigger than 200 lines, it will be placed into one oversized chunk on its own. **Komodo won’t split that function in half.** 

* In practice

  * For normal-sized functions/classes (<200 lines), Komodo accumulates them until adding another function would exceed 200 lines, then starts a new chunk.

  * For an extremely large function or class (e.g. 300 lines), Komodo ignores the usual 200-line limit for that one block and puts it all in a single chunk.

  * Non-Python files keep following line-based splitting at 200 lines per chunk.

This approach strikes a balance: you get roughly 200 lines per chunk unless a single function is bigger, in which case it remains “atomic” and goes into an oversize chunk. That way you never get a function split across two chunks.

**Note**: If you face any issues and the function is still being split into 2, just increase the number, although good practise dictates that you **should not** be writing a 5000 line function. i.e. `komodo . --max-chunk-size 5000 --semantic-chunks`

#### Ignoring & Unignoring Files

* Add ignore patterns with --ignore.
* Unignore specific patterns with --unignore.
* Komodo also has built-in ignores like .git, __pycache__, node_modules, etc.

```bash
# Skip everything in "results/" (relative) and "docs/" (relative)
komodo . --equal-chunks 5 \
  --ignore "results/**" \
  --ignore "docs/**"

# Skip an absolute path
komodo . --equal-chunks 5 \
  --ignore "/Users/oha/komodo/results/**"

# Skip all .rst files, but unignore README.rst
komodo . --equal-chunks 5 \
  --ignore "*.rst" \
  --unignore "README.rst"
```

##### Safest (Recursive) Ignoring

If you want to ensure that Komodo skips all files inside a particular directory (including all subfolders), you can use the ** wildcard before and after the folder name:

```bash
# safest mode: skip everything in "results/" and "docs/" recursively
komodo . --equal-chunks 5 \
  --ignore "**/results/**" \
  --ignore "**/docs/**"
```

**Pro Tip: If in doubt, just use **/folder/** to recursively ignore that folder and everything beneath it. This is the most reliable way to avoid processing unwanted files in subdirectories.**

#### Fixed Number of Chunks with ignore mode

* `--ignore "/Users/oha/treeline/results/**"` tells the chunker to skip any files in that absolute directory path.
* `--ignore "docs/*"` tells it to skip any files under a relative folder named docs/.

```bash
komodo . --equal-chunks 5 --ignore "/Users/oha/treeline/results/**" --ignore "docs/*" 
```

##### Priority Rules

Priority Rules help determine which files should be processed first or given more importance. Files with higher priority scores are processed first

```bash
# With equal chunks, 10 which is .py is higher than 5, so 10 will get processed first
komodo . \
  --equal-chunks 5 \
  --priority "*.py,10" \ 
  --priority "*.md,5" \
  --output-dir chunks

# Or with max chunk size
komodo . \
  --max-chunk-size 1000 \
  --priority "*.py,10" \
  --priority "*.md,5" \
  --output-dir chunks
```

#### LLM Optimization Options
Enable metadata extraction and content optimization:

```bash
komodo . \
  --equal-chunks 5 \
  --enhanced \
  --context-window 4096 \
  --min-relevance 0.3
```

```bash     
komodo . \
  --equal-chunks 5 \
  --enhanced \
  --keep-redundant \
  --min-relevance 0.5
```

```bash
komodo . \
  --equal-chunks 5 \
  --enhanced \
  --no-metadata \
  --context-window 8192
```

### ** ***New*** ** Dry Run

If you only want to see which files **would** be chunked (and in what priority order), without actually writing any output chunks, you can specify `--dry-run`. This is especially helpful if you’re testing new ignore/unignore patterns or priority rules. Note again, there will be **NO CHUNKING** being done. This is just to let you see what files will be chunked.

Example:

```bash
## vanilla approach 
komodo . --equal-chunks 5 --dry-run

## with priorities for .py files. these get processed faster. but note this is just a dry run
komodo . --equal-chunks 5 --dry-run \
    --priority "*.py,10" \
    --priority "*.md,5"
```

No chunks are created. Komodo simply prints the would-be processed files, sorted by priority. This is an easy way to confirm your ignore patterns and see exactly which files the chunker will pick up.

### Python API Usage

Basic usage:

```python
from komodo import ParallelChunker

# Split into 5 equal chunks
chunker = ParallelChunker(
    equal_chunks=5,
    output_dir="chunks"
)
chunker.process_directory("path/to/code")
```

Advanced configuration:

```python
chunker = ParallelChunker(
    equal_chunks=5,  # or max_chunk_size=1000
    
    user_ignore=["*.log", "node_modules/**"],
    user_unignore=["important.log"],
    binary_extensions=["exe", "dll", "so", "bin"],
    
    priority_rules=[
        ("*.py", 10),
        ("*.md", 5),
        ("*.txt", 1)
    ],
    
    output_dir="chunks",
    num_threads=4
)

chunker.process_directories(["src/", "docs/", "tests/"])
```

## Advanced LLM Features

### Metadata Extraction
Each chunk automatically extracts and includes:
- Function definitions
- Class declarations
- Import statements
- Docstrings

### Relevance Scoring
Chunks are scored based on:
- Code/comment ratio
- Function/class density
- Documentation quality
- Import significance

### Redundancy Removal
Automatically removes duplicate content across chunks while preserving unique context.

Example with LLM optimizations:

```python
chunker = ParallelChunker(
    equal_chunks=5,
    extract_metadata=True,
    remove_redundancy=True,
    context_window=4096,
    min_relevance_score=0.3
)
```

## Common Use Cases

### 1. Preparing Context for LLMs

Split a large codebase into equal chunks suitable for LLM context windows:

```python
chunker = ParallelChunker(
    equal_chunks=5,
    priority_rules=[
        ("*.py", 10),    
        ("README*", 8), 
    ],
    user_ignore=["tests/**", "**/__pycache__/**"],
    output_dir="llm_chunks"
)
chunker.process_directory("my_project")
```

## Configuration Options

| Option | Description | Default | Type |
|--------|-------------|---------|------|
| `equal_chunks` | Number of equal-sized chunks | None | int |
| `max_chunk_size` | Maximum tokens per chunk | None | int | 
| `output_dir` | Directory for output files | "chunks" | str |
| `num_threads` | Number of parallel processing threads | 4 | int | 
| `ignore` | Patterns to ignore | [] | List[str] |
| `user_unignore` | Patterns to explicitly include | [] | List[str] |
| `binary_extensions` | Extensions to treat as binary | ["exe", "dll", "so"] | List[str] |
| `priority_rules` | File patterns and their priorities| [] | List[Tuple[str, int]] |
| `extract_metadata` | Extract code elements like functions and classes | true | bool |
| `add_summaries` | Add content summaries to chunks | true | bool |
| `remove_redundancy` | Remove duplicate content across chunks | true | bool |
| `context_window` | Maximum context window size (for LLMs) | 4096 | int | 
| `min_relevance_score` | Minimum relevance threshold for chunks | 0.3 | float |

## Built-in Ignore Patterns

The chunker automatically ignores common non-text and build-related files:

- `**/.git/**`
- `**/.idea/**`
- `__pycache__`
- `*.pyc`
- `*.pyo`
- `**/node_modules/**`
- `target`
- `venv`

## Common Gotchas

1. Leading Slash for Absolute Paths

If you omit the leading `/` in a pattern like `/Users/oha/...`, Komodo treats it as relative and won’t match your actual absolute path.

2. `/**` vs. `/*`

* `folder/**` matches all files and subfolders under folder.
* `folder/*` only matches the immediate contents of folder, not deeper subdirectories.
Overwriting Multiple `--ignore` Flags

3. Folder Name vs. Actual Path

* If your path is really `src/komodo/content/results`, but you only wrote `results/**`, you may need a double-star approach `(**/results/**)` to cover deeper paths.

# Acknowledgments
This project was inspired by [repomix](https://github.com/yamadashy/repomix), a repository content chunking tool.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Apache 2.0