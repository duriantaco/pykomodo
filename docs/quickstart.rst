Quickstart
===========

This guide gets you started with pykomodo, a tool for chunking files in parallel.

Installation
-------------

Install pykomodo via pip:

.. code-block:: bash

   pip install pykomodo==0.1.5

CLI Example
------------

Chunk your current directory into 3 equal parts:

.. code-block:: bash

   komodo . --equal-chunks 3 --output-dir chunks/

This creates a ``chunks/`` directory with your split files.

API Example
------------

Use pykomodo programmatically:

.. code-block:: python

   from pykomodo.multi_dirs_chunker import ParallelChunker

   chunker = ParallelChunker(equal_chunks=3, output_dir="chunks")
   chunker.process_directory(".")

Next Steps
-----------

Check out :ref:`usage` for more examples or :ref:`cli_reference` for all options.