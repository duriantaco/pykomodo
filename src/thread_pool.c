// thread_pool.c

#include "thread_pool.h"
#include "utils.h"
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <libgen.h>
#include <fnmatch.h>
#include <stdio.h>
#include <errno.h>
#include <stdarg.h>
#include <time.h>
#include <pthread.h>
#include <unistd.h>


static void parse_and_merge_gitignore(CConfig* config, const char* gitignore_path);

#define INITIAL_QUEUE_SIZE 1024
#define MAX_PATH 4096
#define READ_CHUNK_SIZE 8192

void komodo_log_error(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    fprintf(stderr, "[KomodoError] ");
    vfprintf(stderr, fmt, args);
    va_end(args);
}

static int should_unignore_file(const char* path, const CConfig* config) {
    for (size_t i = 0; i < config->num_unignore; i++) {
        if (fnmatch(config->unignore_patterns[i], path,
                    FNM_PATHNAME | FNM_NOESCAPE | FNM_CASEFOLD) == 0) {
            return 1; // unignored => do not ignore
        }
    }
    return 0;
}

static int should_ignore_file(const char* path, const CConfig* config) {
    // if any unignore pattern matches => return false
    if (should_unignore_file(path, config)) {
        return 0;
    }

    for (size_t i = 0; i < config->num_ignore; i++) {
        const char* pattern = config->ignore_patterns[i];
        if (fnmatch(pattern, path, FNM_PATHNAME | FNM_NOESCAPE | FNM_CASEFOLD) == 0) {
            printf("Ignoring %s (matched pattern %s)\n", path, pattern);
            return 1;
        }
    }
    return 0;
}

static int calculate_priority(const char* path, const CConfig* config) {
    int highest_priority = 0;
    for (size_t i = 0; i < config->num_priority_rules; i++) {
        if (fnmatch(config->priority_rules[i].pattern, path,
                    FNM_PATHNAME | FNM_NOESCAPE | FNM_CASEFOLD) == 0) {
            int score = config->priority_rules[i].score;
            if (score > highest_priority) {
                highest_priority = score;
            }
        }
    }
    return highest_priority;
}

static int is_binary_file(const char* filename, const CConfig* config) {
    const char* ext = strrchr(filename, '.');
    if (ext) {
        ext++;
        for (size_t i = 0; i < config->num_binary_exts; i++) {
            if (strcasecmp(ext, config->binary_exts[i]) == 0) {
                return 1;
            }
        }
    }
    size_t size;
    char* content = read_file_contents(filename, &size);
    if (!content) return 1;

    int is_binary = 0;
    size_t check_size = size < 8192 ? size : 8192;
    for (size_t i = 0; i < check_size; i++) {
        if (content[i] == 0) {
            is_binary = 1;
            break;
        }
    }
    free(content);
    return is_binary;
}

/* ---------- FileQueue ---------- */
static FileQueue* create_file_queue() {
    FileQueue* queue = malloc(sizeof(FileQueue));
    if (!queue) return NULL;

    queue->entries = malloc(INITIAL_QUEUE_SIZE * sizeof(FileEntry*));
    if (!queue->entries) {
        free(queue);
        return NULL;
    }
    queue->count = 0;
    queue->capacity = INITIAL_QUEUE_SIZE;
    pthread_mutex_init(&queue->mutex, NULL);
    return queue;
}

static void add_to_queue(FileQueue* queue, FileEntry* entry) {
    pthread_mutex_lock(&queue->mutex);
    if (queue->count == queue->capacity) {
        queue->capacity *= 2;
        FileEntry** new_entries = realloc(queue->entries,
                                          queue->capacity * sizeof(FileEntry*));
        if (new_entries) {
            queue->entries = new_entries;
        } else {
            // if reallocation failed, skip adding
            pthread_mutex_unlock(&queue->mutex);
            return;
        }
    }
    queue->entries[queue->count++] = entry;
    pthread_mutex_unlock(&queue->mutex);
}

static void process_file(FileEntry* entry, const CConfig* config) {
    size_t file_size;
    char* content = read_file_contents(entry->path, &file_size);
    if (!content) return;

    entry->content = content;
    entry->size = file_size;
    entry->priority = calculate_priority(entry->path, config);
}

static void process_directory(ThreadPool* pool, const char* dir_path) {
    printf("Opening directory: %s\n", dir_path);
    DIR* dir = opendir(dir_path);
    if (!dir) {
        komodo_log_error("Failed to open directory: %s\n", dir_path);
        return;
    }

    struct dirent* entry;
    char full_path[MAX_PATH];

    while ((entry = readdir(dir))) {
        if (entry->d_name[0] == '.') {
            continue;
        }
        if ((strlen(dir_path) + strlen(entry->d_name) + 2) > MAX_PATH) {
            continue;
        }

        snprintf(full_path, MAX_PATH, "%s/%s", dir_path, entry->d_name);

        struct stat st;
        struct stat lst;

        if (lstat(full_path, &lst) == 0 && S_ISLNK(lst.st_mode)) {
            // skip symlink
            continue;
        }

        if (stat(full_path, &st) == -1) {
            continue;
        }

        if (S_ISDIR(st.st_mode)) {
            process_directory(pool, full_path);
        } else if (S_ISREG(st.st_mode)) {
            if (should_ignore_file(full_path, pool->config)) {
                continue;
            }
            if (is_binary_file(full_path, pool->config)) {
                printf("Skipping binary file: %s\n", full_path);
                continue;
            }

            FileEntry* file_entry = malloc(sizeof(FileEntry));
            if (!file_entry) {
                continue;
            }
            file_entry->path = strdup(full_path);
            file_entry->content = NULL;
            file_entry->size = st.st_size;
            file_entry->priority = 0;

            add_to_queue(pool->queue, file_entry);

            pthread_mutex_lock(&pool->mutex);
            pthread_cond_signal(&pool->condition);
            pthread_mutex_unlock(&pool->mutex);
        }
    }

    closedir(dir);
    printf("Finished directory: %s\n", dir_path);
}

static void* worker_thread(void* arg) {
    ThreadPool* pool = (ThreadPool*)arg;
    while (1) {
        pthread_mutex_lock(&pool->mutex);
        while (pool->queue->count == 0 && !pool->should_stop) {
            pthread_cond_wait(&pool->condition, &pool->mutex);
        }
        if (pool->should_stop && pool->queue->count == 0) {
            pthread_mutex_unlock(&pool->mutex);
            break;
        }

        FileEntry* entry = NULL;
        if (pool->queue->count > 0) {
            entry = pool->queue->entries[--pool->queue->count];
            pool->active_count++;
        }
        pthread_mutex_unlock(&pool->mutex);

        if (entry) {
            process_file(entry, pool->config);

            pthread_mutex_lock(&pool->processed_mutex);
            if (pool->processed_count == pool->processed_capacity) {
                pool->processed_capacity *= 2;
                FileEntry** new_array =
                    realloc(pool->processed_files,
                            pool->processed_capacity * sizeof(FileEntry*));
                if (new_array) {
                    pool->processed_files = new_array;
                }
            }
            pool->processed_files[pool->processed_count++] = entry;
            pthread_mutex_unlock(&pool->processed_mutex);

            pthread_mutex_lock(&pool->mutex);
            pool->active_count--;
            pthread_cond_broadcast(&pool->condition);
            pthread_mutex_unlock(&pool->mutex);
        }
    }
    return NULL;
}

void thread_pool_wait_until_done(ThreadPool* pool) {
    pthread_mutex_lock(&pool->mutex);
    while (1) {
        if (pool->queue->count == 0 && pool->active_count == 0) {
            pthread_mutex_unlock(&pool->mutex);
            break;
        }
        pthread_cond_wait(&pool->condition, &pool->mutex);
    }
}

ThreadPool* create_thread_pool(size_t num_threads, const char* base_path, CConfig* config) {
    ThreadPool* pool = malloc(sizeof(ThreadPool));
    if (!pool) return NULL;

    pool->num_threads = num_threads;
    pool->threads = malloc(num_threads * sizeof(pthread_t));
    if (!pool->threads) {
        free(pool);
        return NULL;
    }

    pool->queue = create_file_queue();
    if (!pool->queue) {
        free(pool->threads);
        free(pool);
        return NULL;
    }

    pool->base_path = strdup(base_path);
    pool->config = config;
    pool->should_stop = 0;
    pool->active_count = 0;

    pool->processed_capacity = INITIAL_QUEUE_SIZE;
    pool->processed_count = 0;
    pool->processed_files = malloc(pool->processed_capacity * sizeof(FileEntry*));
    if (!pool->processed_files) {
        // cleanup
        free(pool->threads);
        free(pool);
        return NULL;
    }

    pthread_mutex_init(&pool->mutex, NULL);
    pthread_mutex_init(&pool->processed_mutex, NULL);
    pthread_cond_init(&pool->condition, NULL);

    for (size_t i = 0; i < num_threads; i++) {
        pthread_create(&pool->threads[i], NULL, worker_thread, pool);
    }

    return pool;
}

void destroy_thread_pool(ThreadPool* pool) {
    if (!pool) return;

    pthread_mutex_lock(&pool->mutex);
    pool->should_stop = 1;
    pthread_cond_broadcast(&pool->condition);
    pthread_mutex_unlock(&pool->mutex);

    for (size_t i = 0; i < pool->num_threads; i++) {
        pthread_join(pool->threads[i], NULL);
    }

    if (pool->queue) {
        for (size_t i = 0; i < pool->queue->count; i++) {
            if (pool->queue->entries[i]) {
                free(pool->queue->entries[i]->path);
                free(pool->queue->entries[i]->content);
                free(pool->queue->entries[i]);
            }
        }
        free(pool->queue->entries);
        pthread_mutex_destroy(&pool->queue->mutex);
        free(pool->queue);
    }

    for (size_t i = 0; i < pool->processed_count; i++) {
        if (pool->processed_files[i]) {
            free(pool->processed_files[i]->path);
            free(pool->processed_files[i]->content);
            free(pool->processed_files[i]);
        }
    }
    free(pool->processed_files);

    free(pool->threads);
    free(pool->base_path);
    pthread_mutex_destroy(&pool->mutex);
    pthread_mutex_destroy(&pool->processed_mutex);
    pthread_cond_destroy(&pool->condition);
    free(pool);
}

void thread_pool_process_directory(ThreadPool* pool, const char* dir_path) {
    if (!pool || !dir_path) {
        printf("Error: Invalid pool or dir_path\n");
        return;
    }
    process_directory(pool, dir_path);
}

static int compare_file_entries(const void* a, const void* b) {
    FileEntry* fa = *(FileEntry**)a;
    FileEntry* fb = *(FileEntry**)b;
    return fb->priority - fa->priority; // desc
}

static void write_chunk(const char* content, size_t size, int chunk_num, const CConfig* config) {
    if (config->stream) {
        fwrite(content, 1, size, stdout);
        fflush(stdout);
        return;
    }
    char filename[1024];
    if (config->output_dir) {
        snprintf(filename, sizeof(filename), "%s/chunk-%d.txt", config->output_dir, chunk_num);
    } else {
        snprintf(filename, sizeof(filename), "chunk-%d.txt", chunk_num);
    }
    FILE* f = fopen(filename, "w");
    if (!f) return;
    fwrite(content, 1, size, f);
    fclose(f);
}

void process_chunks(ThreadPool* pool) {
    if (!pool || !pool->processed_files || pool->processed_count == 0) return;
    printf("Processing %zu files into chunks...\n", pool->processed_count);

    qsort(pool->processed_files, pool->processed_count,
          sizeof(FileEntry*), compare_file_entries);

    size_t chunk_size = pool->config->max_size;
    char* current_chunk = malloc(chunk_size + 128);
    if (!current_chunk) return;
    size_t chunk_used = 0;
    int chunk_number = 0;

    for (size_t i = 0; i < pool->processed_count; i++) {
        FileEntry* entry = pool->processed_files[i];
        if (!entry->content) continue;

        size_t entry_size;
        if (pool->config->token_mode) {
            entry_size = count_tokens(entry->content);
        } else {
            entry_size = strlen(entry->content);
        }

        char header[512];
        int header_len = snprintf(header, sizeof(header),
                                  "chunk %d\n>>>> %s\n",
                                  chunk_number, entry->path);
        if (header_len < 0) header_len = 0;

        size_t total_needed = header_len + entry_size + 1; // +1 for newline

        if (chunk_used > 0 && (chunk_used + total_needed > chunk_size)) {
            write_chunk(current_chunk, chunk_used, chunk_number++, pool->config);
            chunk_used = 0;
        }

        if (total_needed > chunk_size) {
            // split
            if (chunk_used > 0) {
                write_chunk(current_chunk, chunk_used, chunk_number++, pool->config);
                chunk_used = 0;
            }
            size_t content_pos = 0;
            size_t remaining = entry_size;
            int part = 0;
            while (remaining > 0) {
                chunk_used = 0;
                size_t can_take = chunk_size - header_len - 1;
                size_t taking = (remaining > can_take) ? can_take : remaining;
                int used_header = snprintf(current_chunk + chunk_used,
                                           chunk_size + 128 - chunk_used,
                                           "chunk %d\n>>>> %s:part %d\n",
                                           chunk_number, entry->path, part);
                if (used_header < 0) used_header = 0;
                chunk_used += used_header;

                memcpy(current_chunk + chunk_used,
                       entry->content + content_pos, taking);
                chunk_used += taking;
                current_chunk[chunk_used++] = '\n';

                write_chunk(current_chunk, chunk_used, chunk_number++, pool->config);
                content_pos += taking;
                remaining -= taking;
                part++;
            }
        } else {
            // fits
            memcpy(current_chunk + chunk_used, header, header_len);
            chunk_used += header_len;
            memcpy(current_chunk + chunk_used, entry->content, entry_size);
            chunk_used += entry_size;
            current_chunk[chunk_used++] = '\n';
        }
    }

    if (chunk_used > 0) {
        write_chunk(current_chunk, chunk_used, chunk_number, pool->config);
    }
    free(current_chunk);
}



// size_t count_tokens(const char* text) {
//     if (!text) return 0;
//     size_t count = 0;
//     int in_space = 1;
//     for (const char* p = text; *p; p++) {
//         if (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') {
//             in_space = 1;
//         } else {
//             if (in_space) count++;
//             in_space = 0;
//         }
//     }
//     return count;
// }

// char* read_file_contents(const char* path, size_t* size_out) {
//     FILE* file = fopen(path, "rb");
//     if (!file) return NULL;
//     size_t used = 0;
//     size_t capacity = 8192;
//     char* buffer = malloc(capacity);
//     if (!buffer) {
//         fclose(file);
//         return NULL;
//     }

//     while (!feof(file)) {
//         if (used + 4096 > capacity) {
//             capacity *= 2;
//             char* new_buf = realloc(buffer, capacity);
//             if (!new_buf) {
//                 free(buffer);
//                 fclose(file);
//                 return NULL;
//             }
//             buffer = new_buf;
//         }
//         size_t read = fread(buffer + used, 1, 4096, file);
//         if (read == 0) break;
//         used += read;
//     }
//     fclose(file);
//     if (size_out) *size_out = used;
//     buffer[used] = '\0';
//     return buffer;
// }

// parse_and_merge_gitignore: optional if you want to read .gitignore
static void parse_and_merge_gitignore(CConfig* config, const char* gitignore_path) {
    FILE* f = fopen(gitignore_path, "r");
    if (!f) {
        return;
    }
    char line[1024];
    while (fgets(line, sizeof(line), f)) {
        char* nl = strrchr(line, '\n');
        if (nl) *nl = '\0';
        if (!line[0] || line[0] == '#') {
            continue;
        }
        config->num_ignore += 1;
        char** new_array = realloc(config->ignore_patterns,
                                   config->num_ignore * sizeof(char*));
        if (!new_array) {
            fclose(f);
            return;
        }
        config->ignore_patterns = new_array;
        config->ignore_patterns[config->num_ignore - 1] = strdup(line);
    }
    fclose(f);
}
