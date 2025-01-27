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
        CPriorityRule* priority_rules
        char** binary_exts
        size_t num_ignore
        size_t num_priority_rules
        size_t num_binary_exts

    cdef struct ProcessedFile:
        char* rel_path
        char* content
        int priority
