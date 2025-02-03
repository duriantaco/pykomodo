# config_utils.pyx

from libc.stdlib cimport malloc, free
from libc.string cimport strcpy, strlen
from .config cimport CConfig, CPriorityRule

import sys

cdef char* make_c_string(object s) except NULL:
    if s is None:
        return <char*>NULL

    cdef bytes py_bytes = str(s).encode('utf8')
    cdef size_t length = len(py_bytes)

    cdef char* c_string = <char*>malloc((length + 1) * sizeof(char))
    if not c_string:
        raise MemoryError("Failed to allocate c_string in make_c_string")

    strcpy(c_string, py_bytes)
    return c_string


cdef CConfig convert_to_cconfig(object py_config) except *:
    """
    Takes a Python KomodoConfig object, returns a CConfig struct.
    """
    if not hasattr(py_config, 'ignore_patterns'):
        raise TypeError("Expected a KomodoConfig-like object with .ignore_patterns, etc.")

    cdef CConfig c_config

    c_config.ignore_patterns = NULL
    c_config.num_ignore = 0
    c_config.priority_rules = NULL
    c_config.num_priority_rules = 0
    c_config.binary_exts = NULL
    c_config.num_binary_exts = 0
    c_config.max_size = 0
    c_config.token_mode = False
    c_config.stream = False
    c_config.output_dir = NULL

    if py_config.ignore_patterns is None:
        py_config.ignore_patterns = []
    cdef int num_ignore = len(py_config.ignore_patterns)
    if num_ignore > 0:
        c_config.ignore_patterns = <char**>malloc(num_ignore * sizeof(char*))
        if not c_config.ignore_patterns:
            raise MemoryError("Failed to allocate ignore_patterns array")
        c_config.num_ignore = num_ignore
        for i, pat in enumerate(py_config.ignore_patterns):
            cdef char* cpat = make_c_string(pat)
            c_config.ignore_patterns[i] = cpat

    if py_config.priority_rules is None:
        py_config.priority_rules = []

    cdef int num_rules = len(py_config.priority_rules)
    if num_rules > 0:
        c_config.priority_rules = <CPriorityRule*>malloc(num_rules * sizeof(CPriorityRule))
        if not c_config.priority_rules:
            raise MemoryError("Failed to allocate priority_rules array")
        c_config.num_priority_rules = num_rules
        for i, rule in enumerate(py_config.priority_rules):
            c_config.priority_rules[i].pattern = make_c_string(rule.pattern)
            c_config.priority_rules[i].score = rule.score

    if py_config.binary_extensions is None:
        py_config.binary_extensions = []
    cdef int num_exts = len(py_config.binary_extensions)
    if num_exts > 0:
        c_config.binary_exts = <char**>malloc(num_exts * sizeof(char*))
        if not c_config.binary_exts:
            raise MemoryError("Failed to allocate binary_exts array")
        c_config.num_binary_exts = num_exts
        for i, ext in enumerate(py_config.binary_extensions):
            c_config.binary_exts[i] = make_c_string(ext)

    c_config.max_size = py_config.max_size
    c_config.token_mode = py_config.token_mode
    c_config.stream = py_config.stream
    c_config.output_dir = make_c_string(py_config.output_dir) if py_config.output_dir else NULL

    return c_config
