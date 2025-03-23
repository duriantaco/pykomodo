.. _usage:

Usage
======

Command Line Interface
-----------------------

**Workflow 1: Basic Chunking**

1. Install pykomodo:

   .. code-block:: bash

      pip install pykomodo==0.1.4

2. Chunk your directory into 5 equal parts:

   .. code-block:: bash

      komodo . --equal-chunks 5 --output-dir my_chunks/

3. Verify the output:

   .. code-block:: bash

      ls my_chunks/
      # Lists chunk-0.txt, chunk-1.txt, ..., chunk-4.txt

**Workflow 2: Advanced Chunking with Filtering**

1. Chunk a project, ignoring logs and tests:

   .. code-block:: bash

      komodo /path/to/project --max-chunk-size 1000 \
          --ignore "*.log" --ignore "**/tests/**" \
          --output-dir project_chunks/

2. Add priority rules:

   .. code-block:: bash

      komodo /path/to/project --max-chunk-size 1000 \
          --ignore "*.log" --ignore "**/tests/**" \
          --priority "*.py,10" --priority "*.md,5" \
          --output-dir prioritized_chunks/

**Workflow 3: Semantic Chunking for Python**

1. Use semantic chunking:

   .. code-block:: bash

      komodo src/ --max-chunk-size 200 --semantic-chunks --output-dir semantic_chunks/

2. Files are split by functions/classes, targeting 200 lines per chunk.

Python API
-----------

**Basic API Usage**

.. code-block:: python

   from pykomodo.multi_dirs_chunker import ParallelChunker

   chunker = ParallelChunker(equal_chunks=5, output_dir="chunks")
   chunker.process_directory("path/to/code")

**Advanced API Usage**

.. code-block:: python

   from pykomodo.enhanced_chunker import EnhancedParallelChunker

   chunker = EnhancedParallelChunker(
       max_chunk_size=1000,
       extract_metadata=True,
       remove_redundancy=True,
       context_window=4096,
       min_relevance_score=0.5,
       output_dir="enhanced_chunks"
   )
   chunker.process_directory("src/")