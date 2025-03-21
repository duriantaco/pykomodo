Chunking Guide
===============

Equal Chunking
---------------

Splits content into a fixed number of chunks.

- **Pros:** Simple, predictable output.
- **Cons:** May split mid-logic.
- **Use When:** You need uniform chunk counts.

**Example:**

.. code-block:: bash

   komodo src/ --equal-chunks 5

Size-Based Chunking
--------------------

Limits chunks to a maximum size (tokens or lines with semantic chunking).

- **Pros:** Controls chunk size.
- **Cons:** Variable chunk count.
- **Use When:** Size constraints matter (e.g., LLM context windows).

**Example:**

.. code-block:: bash

   komodo src/ --max-chunk-size 1000

Semantic Chunking
------------------

Splits Python files by AST (functions/classes).

- **Pros:** Preserves logical units.
- **Cons:** Limited to Python, requires valid syntax.
- **Use When:** Processing Python code for analysis or training.

**Example:**

.. code-block:: bash

   komodo src/ --max-chunk-size 200 --semantic-chunks

PDF Chunking
-------------

Komodo integrates with `PyMuPDF <https://pymupdf.readthedocs.io/>`_ to parse text from PDF files:

- **Text Extraction**: Uses multiple methods (plain text, HTML, structured blocks) to handle various PDF layouts, including multi-column and academic papers.
- **Splitting**: Divides content by pages and paragraphs, aiming to keep paragraphs whole within ``--max-chunk-size`` (in tokens).
- **Output**: Each chunk includes a header like ``--- Page N ---`` to indicate page boundaries.
- If you set ``file_type="pdf"``, only `.pdf` files are processed; all other files are skipped.

Ignoring/Unignoring
--------------------

You can exclude or re-include files via command-line flags like:

.. code-block:: bash

   komodo . --equal-chunks 5 \
       --ignore "**/test/**" \
       --unignore "**/test/specific_test.py"

**Pattern Syntax**:
- Patterns use Unix shell-style wildcards (e.g., ``*``, ``?``, ``[seq]``, ``[!seq]``).
- Use ``**`` to match directories recursively (e.g., ``**/test/**`` matches all files under any ``test`` directory).

Built-In Ignore Patterns
-------------------------

Komodo automatically ignores:

- .git, .idea, __pycache__, node_modules
- Common binary file extensions (exe, dll, etc.)
- Image files like .png, .jpg, etc.

If you want to override, pass additional patterns with ``--ignore`` or ``--unignore``.

Priority Rules
---------------

You can specify which files to process first using priority rules:

.. code-block:: bash

   komodo . --max-chunk-size 200 \
       --priority "*.py,10" \
       --priority "*.md,5"

This means ``*.py`` files have priority 10, ``*.md`` has priority 5. Komodo processes them in descending order of priority.