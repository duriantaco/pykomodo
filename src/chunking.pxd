# chunking.pxd

cdef extern from "chunking.h":
    """
    typedef struct {
        char* rel_path;
        char* content;
        int priority;
    } ProcessedFile;
    """
    ctypedef struct ProcessedFile:
        char* rel_path
        char* content
        int priority
