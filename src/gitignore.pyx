# src/gitignore.pyx
from libc.stdlib cimport malloc, free
from libc.string cimport strcpy, strlen
import pathspec

cdef class GitignoreHandler:
    cdef object spec
    
    def __cinit__(self, str root_path):
        patterns = []
        try:
            with open(f"{root_path}/.gitignore") as f:
                patterns = f.read().splitlines()
        except FileNotFoundError:
            pass
            
        self.spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)
    
    def should_ignore(self, str path):
        return self.spec.match_file(path)