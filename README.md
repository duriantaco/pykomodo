# Komodo Parallel Chunker

A high-performance, multi-threaded utility for processing large text-based codebases. It scans directories, filters files by patterns, and splits content into manageable chunks - perfect for feeding into Large Language Models (LLMs), building search indices, or analyzing large codebases.

## Key Features

- **Parallel Processing**: Fast file reading with configurable thread pools
- **Smart Filtering**: Built-in patterns for common excludes (.git, node_modules, etc.)
- **Flexible Chunking**: Split by bytes or tokens with customizable sizes
- **Priority-based Processing**: Prioritize specific file types or patterns
- **Multiple Output Modes**: Individual chunks, single file, or stdout streaming
- **Binary File Detection**: Automatic skipping of binary files

## Installation

```bash
pip install komodo
```

## Quick Start

### Command Line Usage

Basic usage to chunk all text files in the current directory:

```bash
komodo .
```

Process multiple directories with custom chunk size:

```bash
komodo path1/ path2/ --max-size 1048576  # 1MB chunks
```

Token-based chunking with priorities:

```bash
komodo . \
  --token-mode \
  --max-tokens-per-chunk 2000 \
  --priority-rule "*.py,10" \
  --priority-rule "*.md,5" \
  --output-dir chunks
```

### Python API Usage

Basic usage:

```python
from komodo import ParallelChunker

chunker = ParallelChunker(
    max_size=1024 * 1024,  # 1MB chunks
    output_dir="output"
)
chunker.process_directory("path/to/code")
```

Advanced configuration:

```python
chunker = ParallelChunker(
    user_ignore=["*.log", "node_modules/**"],
    user_unignore=["important.log"],
    binary_extensions=["exe", "dll", "so", "bin"],
    priority_rules=[
        ("*.py", 10),    # Python files first
        ("*.md", 5),     # Then documentation
        ("*.txt", 1)     # Then other text files
    ],
    token_mode=True,
    max_tokens_per_chunk=2000,
    num_threads=4,
    whole_chunk_mode=True,
    output_dir="chunks"
)

# Process multiple directories
chunker.process_directories([
    "src/",
    "docs/",
    "tests/"
])
```

## Common Use Cases

### 1. Preparing Context for LLMs

Split a large codebase into chunks suitable for LLM context windows:

```python
chunker = ParallelChunker(
    token_mode=True,
    max_tokens_per_chunk=4000,  # Adjust based on your LLM's context window
    priority_rules=[
        ("*.py", 10),    # Prioritize source code
        ("README*", 8),  # Then documentation
    ],
    user_ignore=["tests/**", "**/__pycache__/**"],
    output_dir="llm_chunks"
)
chunker.process_directory("my_project")
```

### 2. Codebase Analysis

Process a repository while focusing on specific file types:

```python
chunker = ParallelChunker(
    user_ignore=["*.test.js", "test_*.py"],
    priority_rules=[
        ("src/*.py", 10),
        ("lib/*.js", 8),
        ("*.cpp", 5)
    ],
    whole_chunk_mode=True,  # Single output file
    output_dir="analysis"
)
chunker.process_directory("repo_path")
```

### 3. Documentation Processing

Collect and chunk documentation files:

```python
chunker = ParallelChunker(
    user_unignore=["*.md", "*.rst", "*.txt"],
    user_ignore=["*"],  # Ignore everything else
    token_mode=True,
    num_token_chunks=5,  # Split into 5 equal parts
    output_dir="docs_chunks"
)
chunker.process_directories(["docs/", "wiki/"])
```

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `max_size` | Maximum chunk size in bytes (or tokens if token_mode=True) | 10MB |
| `token_mode` | Split by tokens instead of bytes | False |
| `output_dir` | Directory for output files | None (current dir) |
| `stream` | Stream output to stdout | False |
| `num_threads` | Number of parallel processing threads | 4 |
| `whole_chunk_mode` | Combine all chunks into single file | False |
| `max_tokens_per_chunk` | Maximum tokens per chunk (token_mode only) | None |
| `num_token_chunks` | Split into exact number of chunks (token_mode only) | None |

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

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Add your license information here]