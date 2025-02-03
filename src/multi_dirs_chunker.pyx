# multi_dirs_chunker.pyx

from libc.stdlib cimport malloc, free, realloc, qsort
from libc.string cimport strcpy, strlen, strdup, strrchr, strcasecmp, memchr, memcpy
from libc.stdio cimport FILE, fopen, fclose, fread, fwrite, fflush, stdout
from posix.unistd cimport access, F_OK

cdef extern from "sys/types.h":
    ctypedef long mode_t
    ctypedef long off_t

cdef extern from "fnmatch.h":
    int fnmatch(const char* pattern, const char* string, int flags)

cdef extern from "dirent.h":
    cdef struct DIR:
        pass
    cdef struct dirent:
        char d_name[256]
        unsigned char d_type
    DIR* opendir(const char* name)
    dirent* readdir(DIR* dirp)
    int closedir(DIR* dirp)

cdef extern from "pthread.h":
    ctypedef struct pthread_mutex_t:
        pass
    ctypedef struct pthread_cond_t:
        pass
    ctypedef struct pthread_t:
        pass

    int pthread_mutex_init(pthread_mutex_t*, void*)
    int pthread_mutex_destroy(pthread_mutex_t*)
    int pthread_mutex_lock(pthread_mutex_t*)
    int pthread_mutex_unlock(pthread_mutex_t*)
    int pthread_cond_init(pthread_cond_t*, void*)
    int pthread_cond_destroy(pthread_cond_t*)
    int pthread_cond_wait(pthread_cond_t*, pthread_mutex_t*)
    int pthread_cond_signal(pthread_cond_t*)
    int pthread_cond_broadcast(pthread_cond_t*)
    int pthread_create(pthread_t*, void*, void*(*start_routine)(void*) noexcept, void*)
    int pthread_join(pthread_t, void**)

cdef enum:
    MAX_PATH_LEN = 4096

cdef extern from "sys/stat.h":
    ctypedef struct stat_t "struct stat":
        mode_t st_mode
        off_t st_size
    int stat(const char *path, stat_t *buf) noexcept
    int lstat(const char *path, stat_t *buf) noexcept
    int S_ISDIR(mode_t m)
    int S_ISREG(mode_t m)
    int S_ISLNK(mode_t m)

cdef extern from "stdio.h":
    int snprintf(char* s, size_t n, const char* format, ...)


##################################################
# 1) Our C structs and config
##################################################

cdef int INITIAL_QUEUE_SIZE = 1024

cdef struct CPriorityRule:
    char* pattern
    int score

cdef struct CConfig:
    size_t max_size
    bint token_mode
    char* output_dir
    bint stream

    char** ignore_patterns
    size_t num_ignore
    char** unignore_patterns
    size_t num_unignore
    CPriorityRule* priority_rules
    size_t num_priority_rules
    char** binary_exts
    size_t num_binary_exts

    bint whole_chunk_mode   


cdef struct FileEntry:
    char* path
    char* content
    int priority
    size_t size

cdef struct FileQueue:
    FileEntry** entries
    size_t count
    size_t capacity
    pthread_mutex_t mutex

cdef struct ThreadPool:
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

    size_t active_count


##################################################
# 2) Built-in ignore patterns
##################################################
cdef tuple BUILT_IN_IGNORES = (b".git", b".idea", b"__pycache__", b"*.pyc", b"*.pyo", b"node_modules", b"target")


cdef int NUM_BUILTIN_IGNORES = 7


##################################################
# 3) Helpers
##################################################

cdef char* make_c_string(str s) except NULL:
    if s is None:
        return <char*>NULL
    cdef bytes b = s.encode('utf-8')
    cdef char* c_str = <char*>malloc(len(b) + 1)
    if not c_str:
        raise MemoryError("Failed to allocate c_str")
    strcpy(c_str, b)
    return c_str



cdef void merge_ignore_patterns(CConfig* config,
                                list user_ignore,
                                list user_unignore):
    """
    Merge built-in ignore patterns (defined in the Python tuple BUILT_IN_IGNORES)
    with user-specified ignore patterns. Store user_unignore patterns separately.
    """
    cdef:
        int total_ign, idx, total_un, i
        char** new_ptr
        bytes pat_b, upat_b
        tuple builtin_ignores = BUILT_IN_IGNORES

    config.num_ignore = len(builtin_ignores)
    config.ignore_patterns = <char**>malloc(config.num_ignore * sizeof(char*))
    if not config.ignore_patterns:
        return

    for i in range(config.num_ignore):
        config.ignore_patterns[i] = strdup(builtin_ignores[i])
    
    total_ign = config.num_ignore + len(user_ignore)
    new_ptr = <char**>realloc(config.ignore_patterns, total_ign * sizeof(char*))
    if not new_ptr:
        return
    config.ignore_patterns = new_ptr

    idx = config.num_ignore
    for pat in user_ignore:
        pat_b = pat.encode('utf-8')
        config.ignore_patterns[idx] = strdup(pat_b)
        idx += 1
    config.num_ignore = total_ign

    total_un = len(user_unignore)
    if total_un > 0:
        config.unignore_patterns = <char**>malloc(total_un * sizeof(char*))
        if not config.unignore_patterns:
            return
        config.num_unignore = total_un
        for i, upat in enumerate(user_unignore):
            upat_b = upat.encode('utf-8')
            config.unignore_patterns[i] = strdup(upat_b)
    else:
        config.unignore_patterns = NULL
        config.num_unignore = 0


cdef bint pattern_matches(const char* path, const char* pat):
    cdef int FNM_NOESCAPE = 0
    cdef int FNM_PATHNAME = 1
    cdef int FNM_CASEFOLD = 16

    if fnmatch(pat, path, FNM_NOESCAPE | FNM_PATHNAME | FNM_CASEFOLD) == 0:
        return True
    return False


cdef bint should_ignore_file(const char* path, CConfig* config):
    """
    Return True if path is matched by any ignore pattern,
    except if matched by unignore pattern first => return False.
    """
    cdef size_t i

    for i in range(config.num_unignore):
        if pattern_matches(path, config.unignore_patterns[i]):
            return False

    for i in range(config.num_ignore):
        if pattern_matches(path, config.ignore_patterns[i]):
            return True

    return False

cdef bint is_binary_file(const char* path, CConfig* config):
    """
    Check extension or read for null bytes in first 8192 bytes.
    """
    cdef:
        const char* ext
        int i, j
        FILE* fp
        size_t size_read
        char buf[8192]

    ext = strrchr(path, b'.')
    if ext:
        ext += 1
        for i in range(config.num_binary_exts):
            if strcasecmp(ext, config.binary_exts[i]) == 0:
                return True

    fp = fopen(path, "rb")
    if not fp:
        return True

    size_read = fread(buf, 1, 8192, fp)
    fclose(fp)

    for j in range(size_read):
        if buf[j] == b'\0':
            return True
    return False

cdef int calculate_priority(const char* path, CConfig* config):

    cdef int highest = 0
    cdef int i
    for i in range(config.num_priority_rules):
        if pattern_matches(path, config.priority_rules[i].pattern):
            if config.priority_rules[i].score > highest:
                highest = config.priority_rules[i].score
    return highest


cdef char* read_file_contents(const char* path, size_t* size_out) except NULL:

    cdef FILE* fp = fopen(path, "rb")
    if not fp:
        return NULL

    cdef size_t used = 0
    cdef size_t capacity = 8192
    cdef char* buffer = <char*>malloc(capacity)
    cdef size_t nread
    cdef size_t chunk = 4096
    cdef char* new_buf

    if not buffer:
        fclose(fp)
        return NULL

    while True:
        nread = fread(buffer + used, 1, chunk, fp)
        if nread == 0:
            break
        used += nread
        if used + chunk > capacity:
            capacity *= 2
            new_buf = <char*>realloc(buffer, capacity)
            if not new_buf:
                free(buffer)
                fclose(fp)
                return NULL
            buffer = new_buf

    fclose(fp)
    buffer[used] = b'\0'
    if size_out != NULL:
        size_out[0] = used
    return buffer

cdef size_t count_tokens(const char* text):

    if not text:
        return 0

    cdef size_t count = 0
    cdef bint in_space = True
    cdef char c
    cdef size_t i = 0
    cdef size_t length = strlen(text)

    for i in range(length):
        c = text[i]
        if c in [b' ', b'\t', b'\n', b'\r', b'\f', b'\v']:
            in_space = True
        else:
            if in_space:
                count += 1
            in_space = False
    return count

##################################################
# 4) FileQueue & Basic Thread Functions
##################################################

cdef FileQueue* create_file_queue():
    cdef FileQueue* queue = <FileQueue*>malloc(sizeof(FileQueue))
    if not queue:
        return NULL
    queue.entries = <FileEntry**>malloc(INITIAL_QUEUE_SIZE * sizeof(FileEntry*))
    if not queue.entries:
        free(queue)
        return NULL
    queue.count = 0
    queue.capacity = INITIAL_QUEUE_SIZE
    pthread_mutex_init(&queue.mutex, NULL)
    return queue


cdef void destroy_file_queue(FileQueue* queue):
    if not queue:
        return
    if queue.entries:
        free(queue.entries)
    pthread_mutex_destroy(&queue.mutex)
    free(queue)


cdef void add_to_queue(FileQueue* queue, FileEntry* entry):
    cdef FileEntry** new_entries  
    pthread_mutex_lock(&queue.mutex)
    if queue.count == queue.capacity:
        queue.capacity *= 2
        new_entries = <FileEntry**>realloc(queue.entries, queue.capacity * sizeof(FileEntry*))
        if new_entries:
            queue.entries = new_entries
        else:
            pthread_mutex_unlock(&queue.mutex)
            return
    queue.entries[queue.count] = entry
    queue.count += 1
    pthread_mutex_unlock(&queue.mutex)

##################################################
# 5) Directory recursion
##################################################

cdef void process_directory(ThreadPool* pool, const char* dir_path):
    cdef DIR* dir
    cdef char* full_path
    cdef dirent* ent
    cdef int needed
    cdef stat_t st_buf
    cdef stat_t st_info
    cdef mode_t file_mode
    cdef FileEntry* fe = NULL
    
    dir = opendir(dir_path)
    if not dir:
        return

    full_path = <char*>malloc(MAX_PATH_LEN)
    if not full_path:
        closedir(dir)
        return

    try:
        while True:
            ent = readdir(dir)
            if not ent:
                break
            if ent.d_name[0] == b'.':
                continue

            needed = snprintf(full_path, MAX_PATH_LEN, "%s/%s", dir_path, ent.d_name)
            if needed < 0 or needed >= MAX_PATH_LEN:
                continue

            if lstat(full_path, &st_buf) == 0:
                file_mode = st_buf.st_mode
                if stat(full_path, &st_info) == 0:
                    
                    if S_ISDIR(st_info.st_mode):
                        process_directory(pool, full_path)
                    elif S_ISREG(st_info.st_mode):
                        if should_ignore_file(full_path, pool.config):
                            continue
                        if is_binary_file(full_path, pool.config):
                            continue

                        fe = <FileEntry*>malloc(sizeof(FileEntry))
                        if not fe:
                            continue
                        fe.path = strdup(full_path)
                        fe.content = NULL
                        fe.size = st_info.st_size
                        fe.priority = 0

                        add_to_queue(pool.queue, fe)

                        pthread_mutex_lock(&pool.mutex)
                        pthread_cond_signal(&pool.condition)
                        pthread_mutex_unlock(&pool.mutex)

    finally:
        closedir(dir)
        free(full_path)

##################################################
# 6) Worker thread
##################################################

cdef void* worker_thread(void* arg) noexcept:
    cdef ThreadPool* pool = <ThreadPool*>arg
    cdef FileEntry* entry = NULL
    cdef size_t file_size = 0
    cdef char* contents = NULL
    cdef FileEntry** new_pf = NULL

    while True:
        pthread_mutex_lock(&pool.mutex)
        while pool.queue.count == 0 and not pool.should_stop:
            pthread_cond_wait(&pool.condition, &pool.mutex)
        if pool.should_stop and pool.queue.count == 0:
            pthread_mutex_unlock(&pool.mutex)
            break

        entry = NULL
        if pool.queue.count > 0:
            pool.queue.count -= 1
            entry = pool.queue.entries[pool.queue.count]
            pool.active_count += 1
        pthread_mutex_unlock(&pool.mutex)

        if entry:
            file_size = 0
            contents = read_file_contents(entry.path, &file_size)
            if contents:
                entry.content = contents
                entry.size = file_size
                entry.priority = calculate_priority(entry.path, pool.config)

            pthread_mutex_lock(&pool.processed_mutex)
            if pool.processed_count == pool.processed_capacity:
                pool.processed_capacity *= 2
                new_pf = <FileEntry**>realloc(pool.processed_files,
                    pool.processed_capacity * sizeof(FileEntry*))
                if new_pf:
                    pool.processed_files = new_pf
            pool.processed_files[pool.processed_count] = entry
            pool.processed_count += 1
            pthread_mutex_unlock(&pool.processed_mutex)

            pthread_mutex_lock(&pool.mutex)
            pool.active_count -= 1
            pthread_cond_broadcast(&pool.condition)
            pthread_mutex_unlock(&pool.mutex)

    return NULL

##################################################
# 7) ThreadPool
##################################################

cdef ThreadPool* create_thread_pool(size_t num_threads, const char* base_path, CConfig* config):
    cdef ThreadPool* pool = <ThreadPool*>malloc(sizeof(ThreadPool))
    if not pool:
        return NULL

    pool.num_threads = num_threads
    pool.threads = <pthread_t*>malloc(num_threads * sizeof(pthread_t))
    if not pool.threads:
        free(pool)
        return NULL

    pool.queue = create_file_queue()
    if not pool.queue:
        free(pool.threads)
        free(pool)
        return NULL

    pool.base_path = strdup(base_path)
    pool.config = config
    pool.should_stop = 0
    pthread_mutex_init(&pool.mutex, NULL)
    pthread_cond_init(&pool.condition, NULL)

    pool.processed_capacity = INITIAL_QUEUE_SIZE
    pool.processed_count = 0
    pool.processed_files = <FileEntry**>malloc(pool.processed_capacity * sizeof(FileEntry*))
    if not pool.processed_files:
        # cleanup
        destroy_file_queue(pool.queue)
        free(pool.threads)
        free(pool)
        return NULL

    pthread_mutex_init(&pool.processed_mutex, NULL)
    pool.active_count = 0

    cdef int i
    for i in range(num_threads):
        pthread_create(&pool.threads[i], NULL, worker_thread, pool)

    return pool


cdef void destroy_thread_pool(ThreadPool* pool):
    if not pool:
        return

    pthread_mutex_lock(&pool.mutex)
    pool.should_stop = 1
    pthread_cond_broadcast(&pool.condition)
    pthread_mutex_unlock(&pool.mutex)

    cdef int i
    for i in range(pool.num_threads):
        pthread_join(pool.threads[i], NULL)

    free(pool.threads)

    if pool.queue:
        destroy_file_queue(pool.queue)

    for i in range(pool.processed_count):
        if pool.processed_files[i]:
            if pool.processed_files[i].path:
                free(pool.processed_files[i].path)
            if pool.processed_files[i].content:
                free(pool.processed_files[i].content)
            free(pool.processed_files[i])
    free(pool.processed_files)

    if pool.base_path:
        free(pool.base_path)

    pthread_mutex_destroy(&pool.mutex)
    pthread_cond_destroy(&pool.condition)
    pthread_mutex_destroy(&pool.processed_mutex)
    free(pool)


cdef void thread_pool_wait_until_done(ThreadPool* pool):
    pthread_mutex_lock(&pool.mutex)
    while True:
        if pool.queue.count == 0 and pool.active_count == 0:
            pthread_mutex_unlock(&pool.mutex)
            break
        pthread_cond_wait(&pool.condition, &pool.mutex)

cdef int compare_file_entries(const void* a, const void* b) noexcept nogil:    
    cdef FileEntry* fa = (<FileEntry**>a)[0]
    cdef FileEntry* fb = (<FileEntry**>b)[0]
    return fb.priority - fa.priority

##################################################
# 8) Writing logic
##################################################

cdef void write_chunk(const char* content, size_t size, int chunk_num, CConfig* config):

    cdef char filename[1024]

    if config.stream:
        fwrite(content, 1, size, stdout)
        fflush(stdout)
        return

    if config.output_dir:
        snprintf(filename, 1024, "%s/chunk-%d.txt", config.output_dir, chunk_num)
    else:
        snprintf(filename, 1024, "chunk-%d.txt", chunk_num)

    cdef FILE* f = fopen(filename, "w")
    if not f:
        return
    fwrite(content, 1, size, f)
    fclose(f)


cdef void write_chunk_single_file(const char* content, size_t size, FILE* outfile):
    """
    Single-file aggregator approach, if desired.
    """
    if not outfile:
        return
    fwrite(content, 1, size, outfile)
    # optionally flush: fflush(outfile)


##################################################
# 9) process_chunks Overhaul
##################################################

cdef void process_chunks(ThreadPool* pool):

    if not pool or not pool.processed_files or pool.processed_count == 0:
        return

    qsort(pool.processed_files, pool.processed_count, sizeof(FileEntry*), compare_file_entries)

    cdef size_t chunk_size = pool.config.max_size
    cdef char* current_chunk = <char*>malloc(chunk_size + 128)
    if not current_chunk:
        return

    cdef size_t chunk_used = 0
    cdef int chunk_number = 0
    cdef FILE* aggregator_file = NULL
    cdef char aggregator_name[1024]

    if pool.config.whole_chunk_mode:
        if pool.config.stream:
            aggregator_file = stdout
        else:
            if pool.config.output_dir:
                snprintf(aggregator_name, 1024, "%s/whole_chunk_mode-output.txt",
                         pool.config.output_dir)
            else:
                snprintf(aggregator_name, 1024, "whole_chunk_mode-output.txt")
            aggregator_file = fopen(aggregator_name, "w")
            if not aggregator_file:
                free(current_chunk)
                return

    cdef size_t i

    cdef FileEntry* entry = NULL
    cdef size_t entry_size = 0, header_len = 0, sep_len = 0, total_needed = 0
    cdef size_t content_pos = 0, remaining = 0, can_take = 0, taking = 0
    cdef bytes header_b, sep_b

    for i in range(pool.processed_count):
        entry = pool.processed_files[i]
        if not entry or not entry.content:
            continue

        if pool.config.token_mode:
            entry_size = count_tokens(entry.content)
        else:
            entry_size = strlen(entry.content)

        header_b = f"File: {entry.path}\n".encode("utf-8")
        header_len = len(header_b)
        sep_b = b"\n"
        sep_len = len(sep_b)
        total_needed = header_len + entry_size + sep_len

        if chunk_used > 0 and (chunk_used + total_needed > chunk_size):
            if pool.config.whole_chunk_mode:
                write_chunk_single_file(current_chunk, chunk_used, aggregator_file)
            else:
                write_chunk(current_chunk, chunk_used, chunk_number, pool.config)
            chunk_number += 1
            chunk_used = 0

        if total_needed > chunk_size:
            if chunk_used > 0:
                if pool.config.whole_chunk_mode:
                    write_chunk_single_file(current_chunk, chunk_used, aggregator_file)
                else:
                    write_chunk(current_chunk, chunk_used, chunk_number, pool.config)
                chunk_number += 1
                chunk_used = 0

            content_pos = 0
            remaining = entry_size
            while remaining > 0:
                can_take = chunk_size - header_len - sep_len
                taking = can_take if remaining > can_take else remaining

                memcpy(current_chunk + chunk_used, <char*>header_b, header_len)

                chunk_used += header_len

                memcpy(current_chunk + chunk_used, entry.content + content_pos, taking)
                chunk_used += taking

                memcpy(current_chunk + chunk_used, <char*>sep_b, sep_len)
                chunk_used += sep_len

                if pool.config.whole_chunk_mode:
                    write_chunk_single_file(current_chunk, chunk_used, aggregator_file)
                else:
                    write_chunk(current_chunk, chunk_used, chunk_number, pool.config)
                chunk_number += 1
                content_pos += taking
                remaining -= taking
                chunk_used = 0  
        else:
            memcpy(current_chunk + chunk_used, <char*>header_b, header_len)

            chunk_used += header_len

            memcpy(current_chunk + chunk_used, entry.content, entry_size)
            chunk_used += entry_size

            memcpy(current_chunk + chunk_used, <char*>sep_b, sep_len)
            chunk_used += sep_len

    if chunk_used > 0:
        if pool.config.whole_chunk_mode:
            write_chunk_single_file(current_chunk, chunk_used, aggregator_file)
        else:
            write_chunk(current_chunk, chunk_used, chunk_number, pool.config)

    free(current_chunk)

    if pool.config.whole_chunk_mode and aggregator_file and aggregator_file != stdout:
        fclose(aggregator_file)

##################################################
# 10) ParallelChunker Class
##################################################

cdef class ParallelChunker:
    cdef:
        ThreadPool* pool
        CConfig c_config
        bint is_pool_active

    def __cinit__(self,
                  list user_ignore = [],
                  list user_unignore = [],
                  list binary_extensions = ["exe","dll","so"],
                  list priority_rules = [],
                  size_t max_size = 10*1024*1024,
                  bint token_mode=False,
                  str output_dir=None,
                  bint stream=False,
                  size_t num_threads=4,
                  bint whole_chunk_mode=False
                  ):
        cdef int i
        cdef bytes ext_bytes
        
        self.c_config.max_size = max_size
        self.c_config.token_mode = token_mode
        self.c_config.stream = stream

        if output_dir is not None:
            self.c_config.output_dir = make_c_string(output_dir)
        else:
            self.c_config.output_dir = NULL

        self.c_config.whole_chunk_mode = whole_chunk_mode

        merge_ignore_patterns(&self.c_config, user_ignore, user_unignore)

        self.c_config.num_binary_exts = len(binary_extensions)
        if self.c_config.num_binary_exts > 0:
            self.c_config.binary_exts = <char**>malloc(self.c_config.num_binary_exts * sizeof(char*))
            if not self.c_config.binary_exts:
                raise MemoryError("Failed to allocate binary_exts")
            
            for i in range(self.c_config.num_binary_exts):
                self.c_config.binary_exts[i] = make_c_string(binary_extensions[i])
        else:
            self.c_config.binary_exts = NULL

        self.c_config.num_priority_rules = len(priority_rules)
        if self.c_config.num_priority_rules > 0:
            self.c_config.priority_rules = <CPriorityRule*>malloc(
                self.c_config.num_priority_rules * sizeof(CPriorityRule)
            )
            if not self.c_config.priority_rules:
                raise MemoryError("Failed to allocate priority_rules")
            
            for i in range(self.c_config.num_priority_rules):
                self.c_config.priority_rules[i].pattern = make_c_string(priority_rules[i][0])
                self.c_config.priority_rules[i].score = priority_rules[i][1]
        else:
            self.c_config.priority_rules = NULL

        self.pool = create_thread_pool(num_threads, b".", &self.c_config)
        if not self.pool:
            raise MemoryError("Failed to create thread pool")

        self.is_pool_active = True

    def process_directories(self, list dirs):
        if not self.is_pool_active:
            raise RuntimeError("Pool is already destroyed.")

        cdef bytes b_dir
        for d in dirs:
            b_dir = d.encode('utf-8')
            process_directory(self.pool, b_dir)

        thread_pool_wait_until_done(self.pool)
        process_chunks(self.pool)

    def close(self):
        if self.is_pool_active:
            destroy_thread_pool(self.pool)
            self.is_pool_active = False

    def __dealloc__(self):
        self.close()

        if self.c_config.output_dir:
            free(self.c_config.output_dir)

        if self.c_config.ignore_patterns:
            for i in range(self.c_config.num_ignore):
                if self.c_config.ignore_patterns[i]:
                    free(self.c_config.ignore_patterns[i])
            free(self.c_config.ignore_patterns)

        if self.c_config.unignore_patterns:
            for i in range(self.c_config.num_unignore):
                if self.c_config.unignore_patterns[i]:
                    free(self.c_config.unignore_patterns[i])
            free(self.c_config.unignore_patterns)

        if self.c_config.binary_exts:
            for i in range(self.c_config.num_binary_exts):
                if self.c_config.binary_exts[i]:
                    free(self.c_config.binary_exts[i])
            free(self.c_config.binary_exts)

        if self.c_config.priority_rules:
            for i in range(self.c_config.num_priority_rules):
                if self.c_config.priority_rules[i].pattern:
                    free(self.c_config.priority_rules[i].pattern)
            free(self.c_config.priority_rules)

