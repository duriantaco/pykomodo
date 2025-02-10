# Komodo Parallel Chunker

A high-performance, multi-threaded utility for processing large text-based codebases. It scans directories, filters files by patterns, and splits content into manageable chunks - perfect for feeding into Large Language Models (LLMs), building search indices, or analyzing large codebases.

## Key Features

- **Parallel Processing**: Fast file reading with configurable thread pools
- **Smart Filtering**: Built-in patterns for common excludes (.git, node_modules, etc.)
- **Two Chunking Modes**: Split by equal parts or fixed chunk sizes
- **Priority-based Processing**: Prioritize specific file types or patterns
- **Binary File Detection**: Automatic skipping of binary files
- **Advanced LLM Processing**: Automatic metadata extraction (functions, classes, imports)

## Installation

```bash
pip install komodo
```

## Quick Start

### Command Line Usage

Basic usage to chunk all text files in the current directory:

```bash
komodo . --equal-chunks 5
```

Process multiple directories with fixed chunk size:

```bash
komodo path1/ path2/ --max-chunk-size 1000
```

#### Chunking Modes

Komodo supports two chunking modes:

##### Fixed Number of Chunks: 

```bash
# Split into 5 equal chunks
komodo . --equal-chunks 5 --output-dir chunks
```

##### Fixed Chunk Size:

```bash
# Split into chunks of 1000 tokens each
komodo . --max-chunk-size 1000 --output-dir chunks
```

##### Priority Rules

```bash
# With equal chunks
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

| Option | Description | Default |
|--------|-------------|---------|
| `equal_chunks` | Number of equal-sized chunks | None |
| `max_chunk_size` | Maximum tokens per chunk | None |
| `output_dir` | Directory for output files | "chunks" |
| `num_threads` | Number of parallel processing threads | 4 |
| `user_ignore` | Patterns to ignore | [] |
| `user_unignore` | Patterns to explicitly include | [] |
| `binary_extensions` | File extensions to treat as binary | ["exe", "dll", "so"] |
| `priority_rules` | List of (pattern, score) tuples for prioritization | [] |
| `extract_metadata` | Extract code elements like functions and classes | true |
| `add_summaries` | Add content summaries to chunks | true |
| `remove_redundancy` | Remove duplicate content across chunks | true |
| `context_window` | Maximum context window size (for LLMs) | 4096 |
| `min_relevance_score` | Minimum relevance threshold for chunks | 0.3 |

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