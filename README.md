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


* LLM Optimizations:

    * Metadata extraction (functions, classes, imports, docstrings)
    * Content relevance scoring
    * Redundancy removal across chunks
    * Configurable context window sizes

## Installation

```bash
pip install komodo
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
| `user_ignore` | Patterns to ignore | [] | List[str] |
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

# Acknowledgments
This project was inspired by [repomix](https://github.com/yamadashy/repomix), a repository content chunking tool.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Apache 2.0