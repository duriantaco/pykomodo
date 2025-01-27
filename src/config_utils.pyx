from libc.stdlib cimport malloc, free
from libc.string cimport strdup, strcpy, strlen

from .config cimport CConfig, CPriorityRule

import typing
import sys

cdef char* make_c_string(s) except NULL:
    if s is None:
        return NULL
    py_bytes = str(s).encode('utf8')
    cdef char* c_string = <char*>malloc((len(py_bytes) + 1) * sizeof(char))
    if not c_string:
        raise MemoryError()
    strcpy(c_string, py_bytes)
    return c_string

cdef CConfig convert_to_cconfig(object py_config) except *:
    """
    Takes a Python KomodoConfig object, returns a CConfig struct.
    """
    if not hasattr(py_config, 'ignore_patterns'):
        raise TypeError("Expected a KomodoConfig with ignore_patterns, etc.")

    cdef CConfig c_config

    # init struct to avoid garbage values
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
    c_config.ignore_patterns = <char**>malloc(num_ignore * sizeof(char*))
    c_config.num_ignore = num_ignore
    for i, pat in enumerate(py_config.ignore_patterns):
        c_config.ignore_patterns[i] = make_c_string(pat)

    if py_config.priority_rules is None:
        py_config.priority_rules = []
    cdef int num_rules = len(py_config.priority_rules)
    c_config.priority_rules = <CPriorityRule*>malloc(num_rules * sizeof(CPriorityRule))
    c_config.num_priority_rules = num_rules
    for i, rule in enumerate(py_config.priority_rules):
        c_config.priority_rules[i].pattern = make_c_string(rule.pattern)
        c_config.priority_rules[i].score = rule.score

    if py_config.binary_extensions is None:
        py_config.binary_extensions = []
    cdef int num_exts = len(py_config.binary_extensions)
    c_config.binary_exts = <char**>malloc(num_exts * sizeof(char*))
    c_config.num_binary_exts = num_exts
    for i, ext in enumerate(py_config.binary_extensions):
        c_config.binary_exts[i] = make_c_string(ext)

    c_config.max_size = py_config.max_size
    c_config.token_mode = py_config.token_mode
    c_config.stream = py_config.stream
    c_config.output_dir = make_c_string(py_config.output_dir) if py_config.output_dir else NULL

    return c_config