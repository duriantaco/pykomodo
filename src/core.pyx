# core.pyx

cimport cython

# --------------------------------------------------------------------------
# 1. Standard C imports & definitions
# --------------------------------------------------------------------------
from libc.stdlib cimport malloc, free, realloc
from libc.string cimport strcpy, strlen, strrchr, strcasecmp, memchr
from libc.stdio cimport FILE, fopen, fread, fclose

cdef extern from "pthread.h":
    ctypedef struct pthread_mutex_t:
        pass
    ctypedef struct pthread_cond_t:
        pass
    ctypedef struct pthread_t:
        pass

cdef extern from "stdio.h":
    int snprintf(char* s, size_t n, const char* format, ...)

from libc.stddef cimport size_t

# --------------------------------------------------------------------------
# 2. Dirent definitions
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# 3. Our custom C structs (from an actual header file)
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# 4. Python imports
# --------------------------------------------------------------------------
import sys

# --------------------------------------------------------------------------
# 5. Helper: make_c_string
# --------------------------------------------------------------------------
cdef char* make_c_string(object s) except NULL:
    """
    Convert a Python string (or None) to a newly allocated C char*.
    Caller must free() it later if non-null.
    """
    if s is None:
        return <char*>NULL
    cdef bytes py_bytes = str(s).encode('utf-8')
    cdef size_t length = len(py_bytes)

    cdef char* buf = <char*>malloc((length + 1) * sizeof(char))
    if not buf:
        raise MemoryError("Failed to allocate for string")

    strcpy(buf, py_bytes)
    return buf

# --------------------------------------------------------------------------
# 6. Convert from Python config -> CConfig
# --------------------------------------------------------------------------
cdef CConfig convert_to_cconfig(object py_config):
    """
    Convert a Python config object (with .max_size, .token_mode, etc.)
    into a fully allocated CConfig struct.
    """
    cdef CConfig c_config

    c_config.max_size = py_config.max_size
    c_config.token_mode = py_config.token_mode
    c_config.stream = py_config.stream
    c_config.output_dir = make_c_string(py_config.output_dir)

    # ignore_patterns
    if py_config.ignore_patterns is None:
        py_config.ignore_patterns = []
    cdef int num_ignore = len(py_config.ignore_patterns)
    c_config.num_ignore = num_ignore
    if num_ignore > 0:
        c_config.ignore_patterns = <char**>malloc(num_ignore * sizeof(char*))
        for i in range(num_ignore):
            c_config.ignore_patterns[i] = make_c_string(py_config.ignore_patterns[i])
    else:
        c_config.ignore_patterns = <char**>NULL

    # priority_rules
    if py_config.priority_rules is None:
        py_config.priority_rules = []
    cdef int num_rules = len(py_config.priority_rules)
    c_config.num_priority_rules = num_rules
    if num_rules > 0:
        c_config.priority_rules = <CPriorityRule*>malloc(num_rules * sizeof(CPriorityRule))
        for i, rule in enumerate(py_config.priority_rules):
            c_config.priority_rules[i].pattern = make_c_string(rule.pattern)
            c_config.priority_rules[i].score = rule.score
    else:
        c_config.priority_rules = <CPriorityRule*>NULL

    # binary_exts
    if py_config.binary_extensions is None:
        py_config.binary_extensions = []
    cdef int num_exts = len(py_config.binary_extensions)
    c_config.num_binary_exts = num_exts
    if num_exts > 0:
        c_config.binary_exts = <char**>malloc(num_exts * sizeof(char*))
        for i in range(num_exts):
            c_config.binary_exts[i] = make_c_string(py_config.binary_extensions[i])
    else:
        c_config.binary_exts = <char**>NULL

    return c_config

# --------------------------------------------------------------------------
# 7. File reading helpers
# --------------------------------------------------------------------------
cdef char* read_file_contents(const char* path) except NULL:
    """
    Read a file in binary mode and return a newly allocated buffer
    containing the full contents, NUL-terminated. Caller must free().
    Returns NULL on error (e.g., file doesn't exist).
    """
    cdef FILE* f = fopen(path, "rb")
    if not f:
        return NULL

    cdef size_t chunk = 65536
    cdef size_t used = 0
    cdef char* buf = <char*>malloc(chunk)
    cdef char* new_buf
    if not buf:
        fclose(f)
        return NULL

    cdef size_t got
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
    Quick 'word-like token' counter. Splits on whitespace.
    """
    if text == NULL:
        return 0
    cdef:
        size_t length = strlen(text)
        size_t i = 0
        size_t count = 0
        bint in_space = True
        char c

    for i in range(length):
        c = text[i]
        if c in [b' ', b'\t', b'\r', b'\n', b'\f', b'\v']:
            in_space = True
        else:
            if in_space:
                count += 1
            in_space = False
    return count

# --------------------------------------------------------------------------
# 8. Directory / ignoring stubs (placeholders)
# --------------------------------------------------------------------------
cdef char* get_relative_path(const char* fullpath, const char* base_path) except NULL:
    """
    Placeholder for your real 'relative path' logic.
    """
    cdef size_t length = strlen(fullpath)
    cdef char* out = <char*>malloc(length + 1)
    if not out:
        return NULL
    strcpy(out, fullpath)
    return out

cdef bint should_ignore(const char* rel_path, CConfig* config):
    """
    Placeholder for your 'ignore' logic, e.g. matching rel_path to patterns.
    """
    return False

cdef int calculate_priority(const char* rel_path, CConfig* config):
    """
    Placeholder for your real scoring logic.
    """
    return 0

# --------------------------------------------------------------------------
# 9. The main Chunker class
# --------------------------------------------------------------------------
cdef class Chunker:
    """
    Example class that stores CConfig, processes files, and writes chunks.
    """
    cdef CConfig c_config
    cdef list processed_files

    def __cinit__(self, object py_config):
        from src.config import KomodoConfig
        if not isinstance(py_config, KomodoConfig):
            raise TypeError("Chunker requires a KomodoConfig")

        self.c_config = convert_to_cconfig(py_config)
        self.processed_files = []

    def add_file(self, rel_path: str, content: str, priority: int):
        """
        Store file info in a C struct and keep a Python list of them.
        """
        cdef ProcessedFile pf
        pf.rel_path = make_c_string(rel_path)
        pf.content = make_c_string(content)
        pf.priority = priority
        self.processed_files.append(pf)

    def write_chunks(self):
        """
        Example logic for chunking data up to c_config.max_size.
        """
        cdef:
            size_t current_size = 0
            list current_chunk = []
            int chunk_idx = 0
            size_t entry_size

        self.processed_files.sort(key=lambda x: x.priority, reverse=True)

        for pf in self.processed_files:
            entry_size = self._calculate_entry_size(pf)
            if current_size + entry_size > self.c_config.max_size and current_chunk:
                self._flush_chunk(current_chunk, chunk_idx)
                chunk_idx += 1
                current_size = 0
                current_chunk = []

            current_chunk.append(pf)
            current_size += entry_size

        if current_chunk:
            self._flush_chunk(current_chunk, chunk_idx)

    cdef size_t _calculate_entry_size(self, ProcessedFile pf):
        if self.c_config.token_mode:
            return count_tokens(pf.content)
        else:
            return strlen(pf.content) if pf.content else 0

    cdef void _flush_chunk(self, list chunk_files, int chunk_idx):
        """
        Placeholder. Actually write out chunk_files to disk or something.
        """
        pass

# --------------------------------------------------------------------------
# 10. Additional Global Functions
# --------------------------------------------------------------------------
cdef bint is_binary_file(const char* path, const char** exts, size_t num_exts):
    """
    Quick check: if file extension is in exts, or if we see a NUL byte
    in first 512 bytes => treat as binary.
    """
    cdef:
        const char* ext = strrchr(path, b'.')
        FILE* fp
        char buffer[512]
        size_t nread
        int i

    if ext != NULL:
        ext += 1  # skip the '.'
        for i in range(num_exts):
            if strcasecmp(ext, exts[i]) == 0:
                return True

    # read first 512 bytes & check for NUL
    fp = fopen(path, "rb")
    if not fp:
        return True  # if unreadable, treat as binary or do something else

    nread = fread(buffer, 1, 512, fp)
    fclose(fp)
    if memchr(buffer, 0, nread) != NULL:
        return True

    return False

def py_is_binary(path: str, binary_exts: list) -> bool:
    """
    Python wrapper for is_binary_file.
    """
    cdef:
        bytes b_path = path.encode()
        size_t num_exts = len(binary_exts)
        const char** c_exts = <const char**>malloc(num_exts * sizeof(char*))
        bint result
        int i

    if not c_exts:
        raise MemoryError("Failed to allocate c_exts")

    for i in range(num_exts):
        c_exts[i] = make_c_string(binary_exts[i])

    result = is_binary_file(b_path, c_exts, num_exts)

    # each allocated extension string shall be FREEEEEE
    for i in range(num_exts):
        if c_exts[i] != NULL:
            free(c_exts[i])
    free(c_exts)

    return bool(result)

def process_directory(str start_path, object py_config):
    """
    Example directory walker that uses readdir to find files,
    reads each file, and adds to a Chunker instance.
    """
    cdef Chunker chunk
    cdef char* cpath
    cdef DIR* dirp
    cdef dirent* entry
    cdef char fullpath[1024]
    cdef char* contents

    chunk = Chunker(py_config)
    cpath = make_c_string(start_path)

    dirp = opendir(cpath)
    if not dirp:
        free(cpath)
        return chunk

    while True:
        entry = readdir(dirp)
        if not entry:
            break

        # IGNORE all hidden dot files
        if entry.d_name[0] == b'.':
            continue

        snprintf(fullpath, 1024, b"%s/%s", cpath, entry.d_name)

        if entry.d_type == DT_DIR:
            # You could recurse here if desired
            pass
        else:
            contents = read_file_contents(fullpath)
            if contents:
                chunk.add_file(
                    rel_path=entry.d_name.decode(),
                    content=contents.decode(),
                    priority=0
                )
                free(contents)

    closedir(dirp)
    free(cpath)
    return chunk

cdef extern from "thread_pool.h":
    ctypedef struct FileEntry:
        char* path
        char* content
        int priority
        size_t size

    ctypedef struct FileQueue:
        FileEntry** entries
        size_t count
        size_t capacity
        pthread_mutex_t mutex

    ctypedef struct ThreadPool:
        pthread_t* threads
        size_t num_threads
        FileQueue* queue
        char* base_path
        CConfig* config
        int should_stop
        pthread_mutex_t mutex
        pthread_cond_t condition
        FileEntry** processed_files
        size_t processed_count
        size_t processed_capacity
        pthread_mutex_t processed_mutex

    ThreadPool* create_thread_pool(size_t num_threads, const char* base_path, CConfig* config)
    void destroy_thread_pool(ThreadPool* pool)
    void thread_pool_process_directory(ThreadPool* pool)

cdef class ParallelChunker:
    cdef ThreadPool* pool
    cdef CConfig c_config
    
    def __cinit__(self, object py_config, int num_threads=16):
        self.c_config = convert_to_cconfig(py_config)
        self.pool = create_thread_pool(num_threads, ".", &self.c_config)
    
    def __dealloc__(self):
        if self.pool:
            destroy_thread_pool(self.pool)
            
    def process_directory(self, str path):
        cdef char* c_path = make_c_string(path)
        thread_pool_process_directory(self.pool)
        free(c_path)
