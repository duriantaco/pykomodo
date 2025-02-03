# gitignore.pyx
# Example of using pathspec for .gitignore-like pattern handling
from libc.stdlib cimport malloc, free
from libc.string cimport strcpy, strlen
import pathspec

cdef class GitignoreHandler:
    cdef object spec
    def __cinit__(self, str root_path):
        patterns = []
        try:
            with open(f"{root_path}/.gitignore", "r") as f:
                file_lines = f.read().splitlines()
                for line in file_lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
        except FileNotFoundError:
            pass
        self.spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)

    def should_ignore(self, str path):
        return self.spec.match_file(path)