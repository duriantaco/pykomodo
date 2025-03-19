Installation
=============

Requirements
-------------

- Python 3.9+ (for best results)
- `PyMuPDF <https://pypi.org/project/PyMuPDF>`_ (required only for PDF chunking)
- `pathspec <https://pypi.org/project/pathspec>`_

Basic Install
--------------

.. code-block:: bash

   pip install pykomodo==0.1.3

Or from source:

.. code-block:: bash

   git clone https://github.com/duriantaco/pykomodo.git
   cd pykomodo
   pip install -e .

Optional Tools
---------------

- `mypy` for type checking
- `pydantic` if you want typed configurations (``pykomodo_config.py`` style)
- `pytest` for running tests