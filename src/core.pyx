# core.pyx

# 1. Standard C imports & definitions
cimport cython
from posix.unistd cimport access, F_OK
import os
import sys

from libc.stddef cimport size_t
from libc.stdlib cimport malloc, free, realloc
from libc.string cimport strcpy, strlen, strrchr, strcasecmp, memchr
from libc.stdio cimport FILE, fopen, fread, fclose

cdef extern from "fnmatch.h":
    int fnmatch(const char *pattern, const char *string, int flags)

cdef extern from "pthread.h":
    ctypedef struct pthread_mutex_t:
        pass
    ctypedef struct pthread_cond_t:
        pass
    ctypedef struct pthread_t:
        pass

cdef extern from "stdio.h":
    int snprintf(char* s, size_t n, const char* format, ...)

# 2. Dirent definitions
cdef extern from "dirent.h":
    cdef struct DIR:
        pass

    cdef struct dirent:
        char d_name[256]
        unsigned char d_type

    DIR* opendir(const char* name)
    dirent* readdir(DIR* dirp)
    int closedir(DIR* dirp)

cdef int DT_DIR = 4

# 3. Our custom C structs
cdef extern from "myheader.h":
    cdef struct CPriorityRule:
        char* pattern
        int score

    cdef struct CConfig:
        size_t max_size
        bint token_mode
        char* output_dir
        bint stream
        char** ignore_patterns
        char** unignore_patterns
        size_t num_ignore
        size_t num_unignore
        CPriorityRule* priority_rules
        size_t num_priority_rules
        char** binary_exts
        size_t num_binary_exts

    cdef struct ProcessedFile:
        char* rel_path
        char* content
        int priority

# 4. Helper: make_c_string
cdef char* make_c_string(object s) except NULL:
    """
    Convert a Python string (or None) to a newly allocated C char*.
    Caller must free() it later.
    """
    if s is None:
        return <char*>NULL
    cdef bytes py_bytes = str(s).encode('utf-8')
    cdef size_t length = len(py_bytes)

    cdef char* buf = <char*>malloc((length + 1) * sizeof(char))
    if not buf:
        raise MemoryError("Failed to allocate c string")

    strcpy(buf, py_bytes)
    return buf

# 5. should_ignore
cdef bint should_ignore(const char* rel_path, CConfig* config):
    """
    Now also checks unignore patterns. If any unignore pattern matches => do NOT ignore.
    Otherwise, if any ignore pattern matches => ignore.
    """
    cdef size_t i

    if config.unignore_patterns != NULL and config.num_unignore > 0:
        for i in range(config.num_unignore):
            if fnmatch(config.unignore_patterns[i], rel_path, 1 | 2 | 16) == 0:
                return False

    if config.ignore_patterns != NULL and config.num_ignore > 0:
        for i in range(config.num_ignore):
            if fnmatch(config.ignore_patterns[i], rel_path, 1 | 2 | 16) == 0:
                return True

    return False

# 6. calculate_priority
cdef int calculate_priority(const char* rel_path, CConfig* config):
    """
    Use fnmatch on each config.priority_rules. Return the highest matched score.
    """
    cdef int highest = 0
    cdef int i

    for i in range(config.num_priority_rules):
        if fnmatch(config.priority_rules[i].pattern, rel_path, 1 | 2 | 16) == 0:
            if config.priority_rules[i].score > highest:
                highest = config.priority_rules[i].score
    return highest

# 7. read_file_contents
cdef char* read_file_contents(const char* path) except NULL:
    """
    Read entire file into a newly allocated buffer, or NULL on error.

    NOTE: We must declare all cdef variables before we use them
    in this function to avoid 'cdef statement not allowed here' errors.
    """
    cdef FILE* f = fopen(path, "rb")
    if not f:
        return NULL

    cdef size_t chunk = 65536
    cdef size_t used = 0
    cdef char* buf = <char*>malloc(chunk)
    if not buf:
        fclose(f)
        return NULL

    cdef size_t got
    cdef char* new_buf

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
                return NULL
            buf = new_buf

    fclose(f)
    buf[used] = b'\0'
    return buf

cdef size_t count_tokens(const char* text):
    """
    Quick whitespace-based token counter.
    """
    if text == NULL:
        return 0
    cdef size_t length = strlen(text)
    cdef size_t i = 0
    cdef size_t count = 0
    cdef bint in_space = True
    cdef char c

    for i in range(length):
        c = text[i]
        if c in [b' ', b'\t', b'\r', b'\n', b'\f', b'\v']:
            in_space = True
        else:
            if in_space:
                count += 1
            in_space = False
    return count

# 8. is_binary_file
cdef bint is_binary_file(const char* path, const char** exts, size_t num_exts):
    """
    Quick check if file extension is in exts or if first 512 bytes have a null byte.
    """
    cdef const char* ext = strrchr(path, b'.')
    cdef FILE* fp
    cdef char buffer[512]
    cdef size_t nread
    cdef int i

    if ext != NULL:
        ext += 1
        for i in range(num_exts):
            if strcasecmp(ext, exts[i]) == 0:
                return True

    fp = fopen(path, "rb")
    if not fp:
        return True

    nread = fread(buffer, 1, 512, fp)
    fclose(fp)
    if memchr(buffer, 0, nread) != NULL:
        return True

    return False
