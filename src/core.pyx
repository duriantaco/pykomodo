############################################################
# 1) Standard and C-level imports
############################################################
import os
import sys
cimport cython

from libc.stddef cimport size_t
from libc.stdlib cimport malloc, free, realloc
from libc.string cimport strcpy, strlen, strrchr, strcasecmp, memchr
from libc.stdio cimport FILE, fopen, fread, fclose

cdef extern from "fnmatch.h":
    int fnmatch(const char *pattern, const char *string, int flags)

############################################################
# 2) cimport from myheader.h
############################################################
cdef extern from "myheader.h":
    cdef struct CPriorityRule:
        char* pattern
        int score

    cdef struct CConfig:
        size_t max_size
        int token_mode
        char* output_dir
        int stream

        char** ignore_patterns
        char** unignore_patterns
        size_t num_ignore
        size_t num_unignore

        CPriorityRule* priority_rules
        size_t num_priority_rules

        char** binary_exts
        size_t num_binary_exts


############################################################
# 3) PyCConfig: a Python wrapper for CConfig
############################################################
cdef class PyCConfig:
    """
    A Python-visible class that holds an internal CConfig struct.
    """
    cdef CConfig c_conf

    def __cinit__(self):
        self.c_conf.max_size = 0
        self.c_conf.token_mode = 0
        self.c_conf.output_dir = <char*>NULL
        self.c_conf.stream = 0

        self.c_conf.ignore_patterns = <char**>NULL
        self.c_conf.unignore_patterns = <char**>NULL
        self.c_conf.num_ignore = 0
        self.c_conf.num_unignore = 0

        self.c_conf.priority_rules = <CPriorityRule*>NULL
        self.c_conf.num_priority_rules = 0

        self.c_conf.binary_exts = <char**>NULL
        self.c_conf.num_binary_exts = 0

    def __dealloc__(self):
        """
        Free all dynamically-allocated arrays so we don't leak memory.
        """
        cdef size_t i

        # ignore_patterns
        if self.c_conf.ignore_patterns != <char**>NULL and self.c_conf.num_ignore > 0:
            for i in range(self.c_conf.num_ignore):
                if self.c_conf.ignore_patterns[i] != <char*>NULL:
                    free(self.c_conf.ignore_patterns[i])
            free(self.c_conf.ignore_patterns)

        # unignore_patterns
        if self.c_conf.unignore_patterns != <char**>NULL and self.c_conf.num_unignore > 0:
            for i in range(self.c_conf.num_unignore):
                if self.c_conf.unignore_patterns[i] != <char*>NULL:
                    free(self.c_conf.unignore_patterns[i])
            free(self.c_conf.unignore_patterns)

        # priority_rules
        if self.c_conf.priority_rules != <CPriorityRule*>NULL and self.c_conf.num_priority_rules > 0:
            for i in range(self.c_conf.num_priority_rules):
                if self.c_conf.priority_rules[i].pattern != <char*>NULL:
                    free(self.c_conf.priority_rules[i].pattern)
            free(self.c_conf.priority_rules)

        # binary_exts
        if self.c_conf.binary_exts != <char**>NULL and self.c_conf.num_binary_exts > 0:
            for i in range(self.c_conf.num_binary_exts):
                if self.c_conf.binary_exts[i] != <char*>NULL:
                    free(self.c_conf.binary_exts[i])
            free(self.c_conf.binary_exts)

        # output_dir
        if self.c_conf.output_dir != <char*>NULL:
            free(self.c_conf.output_dir)


############################################################
# 4) cdef logic for ignoring and priority
############################################################
cdef bint cdef_should_ignore(const char* path, CConfig* config):
    """
    Return True if path is matched by ignore_patterns,
    unless unignore_patterns overrides it.
    """
    cdef int FNM_NOESCAPE = 0
    cdef int FNM_PATHNAME = 1
    cdef size_t i

    if config.unignore_patterns != NULL:
        for i in range(config.num_unignore):
            if fnmatch(config.unignore_patterns[i], path, FNM_NOESCAPE | FNM_PATHNAME) == 0:
                return False

    if config.ignore_patterns != NULL:
        for i in range(config.num_ignore):
            if fnmatch(config.ignore_patterns[i], path, FNM_NOESCAPE | FNM_PATHNAME) == 0:
                return True

    return False

cdef int cdef_calculate_priority(const char* path, CConfig* config):
    """
    Return highest matched priority score among config.priority_rules
    """
    cdef int highest = 0
    cdef size_t i
    if config.priority_rules != NULL:
        for i in range(config.num_priority_rules):
            if fnmatch(config.priority_rules[i].pattern, path, 0) == 0:
                if config.priority_rules[i].score > highest:
                    highest = config.priority_rules[i].score
    return highest


############################################################
# 5) cdef logic for checking binary file
############################################################
cdef bint cdef_is_binary_file(const char* path, char** exts, size_t ext_count):
    cdef const char* dot = strrchr(path, b'.')
    cdef FILE* fp
    cdef char buffer[512]
    cdef size_t nread
    cdef size_t i

    # extension check
    if dot != NULL:
        dot += 1  # skip '.'
        for i in range(ext_count):
            if strcasecmp(dot, exts[i]) == 0:
                return True

    # open file
    fp = fopen(path, "rb")
    if not fp:
        # If we can't open => treat as binary
        return True

    nread = fread(buffer, 1, 512, fp)
    fclose(fp)

    # null => binary
    for i in range(nread):
        if buffer[i] == b'\0':
            return True

    return False


############################################################
# 6) cpdef: py_is_binary_file
############################################################
@cython.binding(True)
cpdef bint py_is_binary_file(str path, list exts):
    """
    Python-callable function. Checks if 'path' is a "binary" file by:
      1) Checking if the extension is in 'exts'
      2) Or if the first 512 bytes contain a null byte
    """
    cdef bytes bpath = path.encode('utf-8')
    cdef const char* cpath = bpath

    cdef size_t ext_count = len(exts)
    cdef char** c_exts = <char**>NULL
    cdef Py_ssize_t i

    cdef bytes b_ext
    cdef char* one_ext
    cdef Py_ssize_t j
    cdef bint result

    if ext_count > 0:
        c_exts = <char**>malloc(ext_count * sizeof(char*))
        if not c_exts:
            raise MemoryError("Failed to allocate c_exts array")

        for i in range(ext_count):
            b_ext = exts[i].encode('utf-8')
            one_ext = <char*>malloc(len(b_ext) + 1)
            if not one_ext:
                # free everything allocated so far
                for j in range(i):
                    free(c_exts[j])
                free(c_exts)
                raise MemoryError("Failed to allocate extension string")

            strcpy(one_ext, b_ext)
            c_exts[i] = one_ext

    result = cdef_is_binary_file(cpath, c_exts, ext_count)

    # free c_exts
    if c_exts != <char**>NULL:
        for i in range(ext_count):
            free(c_exts[i])
        free(c_exts)

    return result


############################################################
# 7) cpdef wrappers for ignore, priority
############################################################
@cython.binding(True)
cpdef void add_ignore_pattern(PyCConfig py_cfg, str pattern):
    cdef CConfig* config = &py_cfg.c_conf
    cdef bytes pat_b = pattern.encode('utf-8')
    cdef char* new_pat = <char*>malloc(len(pat_b) + 1)
    if not new_pat:
        raise MemoryError("Failed to allocate new_pat")

    strcpy(new_pat, pat_b)

    cdef size_t old_count = config.num_ignore
    cdef size_t new_count = old_count + 1
    cdef char** new_array

    if not config.ignore_patterns:
        new_array = <char**>malloc(new_count * sizeof(char*))
        if not new_array:
            free(new_pat)
            raise MemoryError("Failed to allocate ignore_patterns array")
    else:
        new_array = <char**>realloc(config.ignore_patterns, new_count * sizeof(char*))
        if not new_array:
            free(new_pat)
            raise MemoryError("Failed to realloc ignore_patterns array")

    config.ignore_patterns = new_array
    config.ignore_patterns[old_count] = new_pat
    config.num_ignore = new_count

@cython.binding(True)
cpdef void add_priority_rule(PyCConfig py_cfg, str pattern, int score):
    cdef CConfig* config = &py_cfg.c_conf
    cdef bytes pat_b = pattern.encode('utf-8')
    cdef char* new_pat = <char*>malloc(len(pat_b) + 1)
    if not new_pat:
        raise MemoryError("Failed to allocate new_pat")

    strcpy(new_pat, pat_b)

    cdef size_t old_count = config.num_priority_rules
    cdef size_t new_count = old_count + 1
    cdef CPriorityRule* new_array

    if not config.priority_rules:
        new_array = <CPriorityRule*>malloc(new_count * sizeof(CPriorityRule))
        if not new_array:
            free(new_pat)
            raise MemoryError("Failed to allocate priority_rules array")
    else:
        new_array = <CPriorityRule*>realloc(config.priority_rules, new_count * sizeof(CPriorityRule))
        if not new_array:
            free(new_pat)
            raise MemoryError("Failed to realloc priority_rules array")

    config.priority_rules = new_array
    config.priority_rules[old_count].pattern = new_pat
    config.priority_rules[old_count].score = score
    config.num_priority_rules = new_count

@cython.binding(True)
cpdef bint py_should_ignore(str path, PyCConfig py_cfg):
    cdef CConfig* config = &py_cfg.c_conf
    cdef bytes b_path = path.encode('utf-8')
    return cdef_should_ignore(b_path, config)

@cython.binding(True)
cpdef int py_calculate_priority(str path, PyCConfig py_cfg):
    cdef CConfig* config = &py_cfg.c_conf
    cdef bytes b_path = path.encode('utf-8')
    return cdef_calculate_priority(b_path, config)


############################################################
# 8) py_read_file_contents, py_count_tokens, py_make_c_string
############################################################
@cython.binding(True)
cpdef str py_read_file_contents(str path):
    cdef bytes path_bytes = path.encode('utf-8')
    cdef FILE* f = fopen(path_bytes, "rb")
    if not f:
        return "<NULL>"

    cdef size_t chunk = 1024
    cdef size_t used = 0
    cdef char* buf = <char*>NULL
    cdef char* new_buf = <char*>NULL
    cdef size_t got

    buf = <char*>malloc(chunk)
    if not buf:
        fclose(f)
        raise MemoryError("Failed to allocate read buffer")

    while True:
        got = fread(buf + used, 1, chunk - used, f)
        if got == 0:
            break
        used += got

        if used == chunk:
            chunk *= 2
            new_buf = <char*>realloc(buf, chunk)
            if not new_buf:
                free(buf)
                fclose(f)
                raise MemoryError("Failed to reallocate buffer")
            buf = new_buf

    fclose(f)
    buf[used] = b'\0'
    cdef str output = (<bytes>buf).decode('utf-8', 'replace')
    free(buf)
    return output

@cython.binding(True)
cpdef size_t py_count_tokens(str text):
    """
    whitespace-based token counting
    """
    cdef bytes b_text = text.encode('utf-8')
    cdef size_t length = len(b_text)
    cdef size_t i
    cdef size_t count = 0
    cdef bint in_space = True
    cdef char c

    for i in range(length):
        c = b_text[i]
        if c in [b' ', b'\t', b'\r', b'\n', b'\f', b'\v']:
            in_space = True
        else:
            if in_space:
                count += 1
            in_space = False

    return count

@cython.binding(True)
cpdef str py_make_c_string(str text):
    """
    For completeness (if your test calls this).
    Convert str -> c-string -> decode -> return.
    If None => "<NULL>"
    """
    if text is None:
        return "<NULL>"

    cdef bytes b = text.encode('utf-8')
    cdef char* raw = <char*>malloc(len(b) + 1)
    if not raw:
        raise MemoryError("Failed to allocate raw")

    strcpy(raw, b)
    cdef str out = (<bytes>raw).decode('utf-8', 'replace')
    free(raw)
    return out
