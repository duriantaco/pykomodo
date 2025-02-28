.. _api_reference:

==============
API Reference
==============

PyKomodo provides several modules for document processing, chunking, and management.

.. contents:: Table of Contents
   :depth: 2
   :local:

Core Module
==========

.. automodule:: pykomodo.core
   :members:
   :undoc-members:
   :show-inheritance:

.. highlight:: python

Example usage::

    from pykomodo.core import TextProcessor
    
    processor = TextProcessor()
    result = processor.process_text(my_document)

Multi-Directory Chunker
=====================

.. automodule:: pykomodo.multi_dirs_chunker
   :members:
   :undoc-members:
   :show-inheritance:

.. highlight:: python

Example usage::

    from pykomodo.multi_dirs_chunker import MultiDirChunker
    
    chunker = MultiDirChunker()
    chunks = chunker.chunk_directories(['path/to/dir1', 'path/to/dir2'], chunk_size=1000)

Enhanced Chunker
==============

.. automodule:: pykomodo.enhanced_chunker
   :members:
   :undoc-members:
   :show-inheritance:

Command Line Interface
====================

.. automodule:: pykomodo.command_line
   :members:
   :undoc-members:
   :show-inheritance:

Configuration
===========

.. automodule:: pykomodo.pykomodo_config
   :members:
   :undoc-members:
   :show-inheritance:

.. highlight:: python

Example configuration::

    from pykomodo.pykomodo_config import PyKomodoConfig
    
    config = PyKomodoConfig()
    config.load_config('config.yaml')