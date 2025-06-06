<p align="center">
  <img src="assets/KOMODO.png" alt="KOMODO Logo" width="200">
</p>

A Python-based parallel file chunking system designed for processing large codebases into LLM-friendly chunks. The tool provides intelligent file filtering, multi-threaded processing, and advanced chunking capabilities optimized for machine learning contexts.

<p align="center">
  <img src="assets/dashboard.gif" alt="KOMODO Dashboard Demo" width="730">
</p>

## Core Features

* **NEW** Front end tool for chunking. Run `komodo --dashboard`

* Parallel Processing: Multi-threaded file reading with configurable thread pools

* Smart File Filtering:
    * Built-in patterns for common excludes (.git, node_modules, pycache, etc.)
    * Customizable ignore/unignore patterns
    * Intelligent binary file detection

* Flexible Chunking:
    * Equal-parts chunking: Split content into N equal chunks
    * Size-based chunking: Split by maximum chunk size
    * Semantic (AST-based) chunking for Python files  
    * Dry-run mode: If you only want to see which files **would** be chunked
    * Token based chunking: Split by tokens for LLMs

* LLM Optimizations:
    * Metadata extraction (functions, classes, imports, docstrings)
    * Content relevance scoring
    * Redundancy removal across chunks
    * Configurable context window sizes
  
* Chunking PDF Files:
  * Split PDF content by pages and paragraphs (rather than lines)
  * Perform basic text cleanup to handle multi-column layouts, or text from HTML-like elements if present
  * Create multiple chunks for large PDFs while preserving some logical structure

* We scan your repos for api keys and automatically redact it. `.env` files are also ignored

## Installation

```bash
pip install komodo==0.2.5
```

Link to pypi: https://pypi.org/project/pykomodo/

## Quick Start

### Command Line Usage

Here’s a complete list of available command-line options for the `komodo` tool:

| Option                | Description                                                                                   | Default Value      |
|-----------------------|-----------------------------------------------------------------------------------------------|--------------------|
| `--dashboard`         | Launches the front end for chunking     | N/A                |
| `--version`           | Show the version of komodo         | N/A                |
| `dirs`                | Directories to process (space-separated; e.g., `komodo dir1/ dir2/`).                         | Current directory (`.`) |
| `--equal-chunks N`    | Split content into N equal chunks. Mutually exclusive with `--max-chunk-size`.                | None               |
| `--max-chunk-size M`  | Maximum size per chunk (tokens without `--semantic-chunks`; lines for `.py` with it).         | None               |
| `--max-tokens N`    | Maximum tokens per chunk (uses token-based chunking).                                      | None               |
| `--output-dir DIR`    | Directory where chunk files are saved.                                                        | `"chunks"`         |
| `--ignore PATTERN`    | Add a pattern to ignore (repeatable, e.g., `--ignore "*.log"`).                               | None               |
| `--unignore PATTERN`  | Add a pattern to unignore (repeatable, overrides ignores).                                    | None               |
| `--dry-run`           | List files that would be processed without creating chunks.                                   | False              |
| `--priority PATTERN,SCORE` | Set priority for file patterns (repeatable, e.g., `--priority "*.py,10"`).                | None               |
| `--num-threads N`     | Number of threads for parallel processing.                                                    | 4                  |
| `--enhanced`          | Use `EnhancedParallelChunker` for LLM optimizations.                                          | False              |
| `--semantic-chunks`   | Enable AST-based chunking for `.py` files (splits by functions/classes).                      | False              |
| `--context-window N`  | Target LLM context window size in bytes (used with `--enhanced`).                             | 4096               |
| `--min-relevance F`   | Minimum relevance score for chunks (0.0-1.0, used with `--enhanced`).                         | 0.3                |
| `--no-metadata`       | Disable metadata extraction (used with `--enhanced`).                                         | False (metadata enabled) |
| `--keep-redundant`    | Keep redundant content across chunks (used with `--enhanced`).                                | False (removes redundancy) |
| `--no-summaries`      | Disable summary generation (used with `--enhanced`; currently a placeholder in code).          | False (summaries enabled) |
| `--file-type TYPE`    | Only process files of this extension (e.g., `pdf`, `py`).                                     | None               |

**Notes:**
- Options like `--equal-chunks` and `--max-chunk-size` cannot be used together (enforced by the CLI).
- Use `--dry-run` to test your ignore/unignore patterns or priority rules without generating output.

#### Basic usage

##### CLI

```bash
# Split into 5 equal chunks
komodo . --equal-chunks 5

# Process multiple directories
komodo path1/ path2/ --max-chunk-size 1000
```

#### Chunking Modes

Komodo offers flexible chunking strategies, with behavior varying based on options and the chunker type (`ParallelChunker` or `EnhancedParallelChunker` with `--enhanced`).

- **Fixed Number of Chunks (`--equal-chunks N`)**:
  - **Base Chunker**: Keeps files whole, distributing them into N chunks with approximately equal total character counts. i.e. 5 different chunks or 5 text files. 
    ```bash
    komodo . --equal-chunks 5 --output-dir chunks
    ```

  - **Enhanced Chunker**: Combines all file contents into one text blob, then splits into N chunks of roughly equal byte size, potentially splitting files mid-content.
    ```bash
    komodo . --equal-chunks 5 --enhanced
    ```

- **Fixed Size Chunks (--max-chunk-size M)**:
Without `--semantic-chunks`: Splits each file into chunks with at most M tokens (words), keeping lines whole. i.e. x number of chunks with 2000 tokens each or 5000 tokens each etc. 

  ```bash
  komodo . --max-chunk-size 2000
  ```

  **Important: You must specify either --equal-chunks or --max-chunk-size, but not both.**


- **With --semantic-chunks**:

* For .py files: Aims for chunks of M lines, grouping top-level functions/classes as atomic units. If a function exceeds M lines, it becomes a single chunk.
* For non-.py files: Still splits by M tokens.

  ```bash
  komodo . --max-chunk-size 200 --semantic-chunks
  ```

- **With --max-tokens**:

  ```bash
  komodo . --max-tokens 1000 --output-dir chunks
  ```

* Precise token limits: Chunks content based on token counts rather than line counts
* Tiktoken integration: Uses OpenAI's tiktoken library when available for accurate LLM token counting
* Fallback tokenization: Falls back to word-based splitting when tiktoken is unavailable

- **PDF Chunking**:

  Uses PyMuPDF to split PDFs by pages and paragraphs, respecting --max-chunk-size in tokens.

    ```bash
    komodo . --max-chunk-size 500 /path/to/output --file-type pdf
    ```

    or 

    ```bash
    komodo . --equal-chunks 10 --output-dir /path/to/output --file-type pdf
    ```

    **IMPORTANT: Do note that for PDFs with a lot of images, this PDF chunker will NOT WORK. This current PDF chunker is NOT capable of chunking formulas/images** 

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

  **Note: If node_modules fails to be ignored, run this command instead `komodo . --equal-chunks 5 --file-type js --ignore "**/node_modules/**"`. The key here is that you are specifying the file type.**

  ##### Safest (Recursive) Ignoring

  If you want to ensure that Komodo skips all files inside a particular directory (including all subfolders), you can use the ** wildcard before and after the folder name:

    ```bash
    # safest mode: skip everything in "results/" and "docs/" recursively
    komodo . --equal-chunks 5 \
      --ignore "**/results/**" \
      --ignore "**/docs/**"
    ```

  **Pro Tip: If in doubt, just use **/folder/** to recursively ignore that folder and everything beneath it. This is the most reliable way to avoid processing unwanted files in subdirectories.**

  ##### Fixed Number of Chunks with ignore mode

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

### Dry Run

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

Basic configuration with file_type:
```python
import os
from pykomodo.multi_dirs_chunker import ParallelChunker

os.makedirs("/Users/test/komodo/pdf", exist_ok=True)
output_dir = "/Users/test/komodo/pdf"

chunker = ParallelChunker(
    max_chunk_size=1000,
    output_dir=output_dir,
    file_type="pdf" 
)

chunker.process_directory("/Users/test/komodo/")

print("PDF processing completed successfully!")
```

### Front-end Usage

To run the front end for chunking, just use `komodo --dashboard`

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

### File Type Restriction

The file_type parameter of the ParallelChunker constructor lets you restrict which file extensions you process.

```python
import os
from pykomodo.multi_dirs_chunker import ParallelChunker

os.makedirs("/path/to/dir", exist_ok=True)
output_dir = "/path/to/dir"

chunker = ParallelChunker(
    max_chunk_size=1000,
    output_dir=output_dir,
    file_type="pdf" 
)

chunker.process_directory("/path/to/dir")

print("PDF processing completed successfully!")
```

### Typed Classes & Pydantic-Based Configuration

Komodo’s main classes (`ParallelChunker`, `EnhancedParallelChunker`, etc.) now include **type hints**. Nothing changes at runtime, but if you’re using an IDE or a type checker like `mypy`, you’ll get improved error checking and auto-completion - or hopefully. 

You can also use **Pydantic** to configure Komodo with strongly typed settings. For instance:

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from pykomodo.multi_dirs_chunker import ParallelChunker
from pykomodo.enhanced_chunker import EnhancedParallelChunker

class KomodoConfig(BaseModel):
    directories: List[str] = Field(default_factory=lambda: ["."], description="Directories to process.")
    equal_chunks: Optional[int] = None
    max_chunk_size: Optional[int] = None
    output_dir: str = "chunks"
    semantic_chunking: bool = False
    enhanced: bool = False
    context_window: int = 4096
    min_relevance_score: float = 0.3
    remove_redundancy: bool = True
    extract_metadata: bool = True

def run_chunker_with_config(config: KomodoConfig):
    ChunkerClass = EnhancedParallelChunker if config.enhanced else ParallelChunker

    chunker = ChunkerClass(
        equal_chunks=config.equal_chunks,
        max_chunk_size=config.max_chunk_size,
        output_dir=config.output_dir,
        semantic_chunking=config.semantic_chunking,
        context_window=config.context_window if config.enhanced else None,
        min_relevance_score=config.min_relevance_score if config.enhanced else None,
        remove_redundancy=config.remove_redundancy if config.enhanced else None,
        extract_metadata=config.extract_metadata if config.enhanced else None,
    )

    chunker.process_directories(config.directories)
    chunker.close()

if __name__ == "__main__":
    # example use with typed + validated config
    cfg = KomodoConfig(directories=["src/", "docs/"], equal_chunks=5, enhanced=True)
    run_chunker_with_config(cfg)
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

  * If you omit the leading `/` in a pattern like `/Users/oha/...`, Komodo treats it as relative and won’t match your actual absolute path.

2. `/**` vs. `/*`

* `folder/**` matches all files and subfolders under folder.
* `folder/*` only matches the immediate contents of folder, not deeper subdirectories.
* Overwriting Multiple `--ignore` Flags

3. Folder Name vs. Actual Path

* If your path is really `src/komodo/content/results`, but you only wrote `results/**`, you may need a double-star approach `(**/results/**)` to cover deeper paths.

## Troubleshooting

If you see `"[Error] Processing failed: No module named 'frontend'"`, just run `pip install --upgrade pymupdf`. If the wrong package — fitz 0.0.x (an abandoned library) — is in your `PYTHONPATH` instead of `PyMuPDF`, that library will try to import frontend and crashes because that module doesn’t exist.

# Acknowledgments
This project was inspired by [repomix](https://github.com/yamadashy/repomix), a repository content chunking tool.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Apache 2.0