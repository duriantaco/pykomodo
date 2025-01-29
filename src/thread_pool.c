// src/thread_pool.c
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
#include "thread_pool.h"
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

static int should_ignore_file(const char* path, const CConfig* config) {
    for (size_t i = 0; i < config->num_ignore; i++) {
        const char* pattern = config->ignore_patterns[i];
        if (fnmatch(pattern, path, FNM_PATHNAME | FNM_NOESCAPE) == 0) {
            printf("Ignoring %s (matched pattern %s)\n", path, pattern);
            return 1;
        }
    }
    return 0;
}

static int calculate_priority(const char* path, const CConfig* config) {
    int highest_priority = 0;
    
    for (size_t i = 0; i < config->num_priority_rules; i++) {
        if (fnmatch(config->priority_rules[i].pattern, path, 0)== 0) {
            int score = config->priority_rules[i].score;
            if (score > highest_priority) {
                highest_priority = score;
                printf("File %s matched pattern %s with priority %d\n",
                       path, config->priority_rules[i].pattern, score);
            }
        }
    }
    
    return highest_priority;
}

static int is_binary_file(const char* filename, const CConfig* config) {
    const char* ext = strrchr(filename, '.');
    if (!ext) return 0;
    ext++; 

    for (size_t i = 0; i < config->num_binary_exts; i++) {
        if (strcasecmp(ext, config->binary_exts[i]) == 0) {
            return 1;
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

/**
 * @brief Creates a new file queue.
 *
 * This function allocates memory for a new FileQueue structure and initializes
 * its members. The queue is initially empty with a capacity defined by 
 * INITIAL_QUEUE_SIZE. A mutex is also initialized to ensure thread safety 
 * when accessing the queue.
 *
 * @return A pointer to the newly created FileQueue.
 */
static FileQueue* create_file_queue() {
    FileQueue* queue = malloc(sizeof(FileQueue));
    queue->entries = malloc(INITIAL_QUEUE_SIZE * sizeof(FileEntry*));
    queue->count = 0;
    queue->capacity = INITIAL_QUEUE_SIZE;
    pthread_mutex_init(&queue->mutex, NULL);
    return queue;
}

static void add_to_queue(FileQueue* queue, FileEntry* entry) {
    pthread_mutex_lock(&queue->mutex);
    
    if (queue->count == queue->capacity) {
        queue->capacity *= 2;
        queue->entries = realloc(queue->entries, queue->capacity * sizeof(FileEntry*));
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

    char gitignore_path[MAX_PATH];
    snprintf(gitignore_path, MAX_PATH, "%s/.gitignore", dir_path);
    parse_and_merge_gitignore(pool->config, gitignore_path);

    struct dirent* entry;
    char full_path[MAX_PATH];
    
    while ((entry = readdir(dir))) {
        printf("Found entry: %s\n", entry->d_name);
        if (entry->d_name[0] == '.') {
            printf("Skipping hidden file: %s\n", entry->d_name);
            continue;
        }
        
        if (strlen(dir_path) + strlen(entry->d_name) + 2 > MAX_PATH) {
            printf("Path too long, skipping: %s/%s\n", dir_path, entry->d_name);
            continue;
        }

        snprintf(full_path, MAX_PATH, "%s/%s", dir_path, entry->d_name);
        printf("Processing: %s\n", full_path);
        
        struct stat st;

        struct stat lst;
        if (lstat(full_path, &lst) == 0 && S_ISLNK(lst.st_mode)) {
            printf("Skipping symbolic link: %s\n", full_path);
            continue;
        }

        if (stat(full_path, &st) == -1) {
            printf("Failed to stat: %s\n", full_path);
            continue;
        }

        if (S_ISDIR(st.st_mode)) {
            printf("Found directory: %s\n", full_path);
            process_directory(pool, full_path);  
        }
        else if (S_ISREG(st.st_mode)) {
            if (should_ignore_file(full_path, pool->config)) {
                printf("Ignoring file: %s\n", full_path);
                continue;
            }
            if (is_binary_file(full_path, pool->config)) {
                printf("Skipping binary file: %s\n", full_path);
                continue;
            }

            printf("Creating file entry for: %s\n", full_path);
            FileEntry* file_entry = malloc(sizeof(FileEntry));
            if (!file_entry) {
                printf("Failed to allocate FileEntry\n");
                continue;
            }
            file_entry->path = strdup(full_path);
            file_entry->content = NULL;
            file_entry->size = st.st_size;
            file_entry->priority = 0;

            add_to_queue(pool->queue, file_entry);
            
            printf("Added to queue: %s\n", full_path);
            
            pthread_mutex_lock(&pool->mutex);
            pthread_cond_signal(&pool->condition);
            pthread_mutex_unlock(&pool->mutex);
        }
    }

    closedir(dir);
    printf("Finished processing directory: %s\n", dir_path);
}

static void* worker_thread(void* arg) {
    ThreadPool* pool = (ThreadPool*)arg;
    printf("Worker thread started\n");

    while (1) {
        pthread_mutex_lock(&pool->mutex);

        // Wait until there's something in the queue or we should stop
        while (pool->queue->count == 0 && !pool->should_stop) {
            pthread_cond_wait(&pool->condition, &pool->mutex);
        }

        // If we're told to stop and no more items in queue, break
        if (pool->should_stop && pool->queue->count == 0) {
            pthread_mutex_unlock(&pool->mutex);
            break;
        }

        // 2a) Take one item from the queue
        FileEntry* entry = NULL;
        if (pool->queue->count > 0) {
            entry = pool->queue->entries[--pool->queue->count];
            // 2b) Mark an active task
            pool->active_count++;
        }
        pthread_mutex_unlock(&pool->mutex);

        if (entry) {
            // Actually process the file
            process_file(entry, pool->config);

            // Add to processed_files
            pthread_mutex_lock(&pool->processed_mutex);
            if (pool->processed_count == pool->processed_capacity) {
                pool->processed_capacity *= 2;
                pool->processed_files = realloc(pool->processed_files, 
                    pool->processed_capacity * sizeof(FileEntry*));
            }
            pool->processed_files[pool->processed_count++] = entry;
            pthread_mutex_unlock(&pool->processed_mutex);

            // 2c) Decrement active_count
            pthread_mutex_lock(&pool->mutex);
            pool->active_count--;
            // Signal in case something is waiting for active_count
            pthread_cond_broadcast(&pool->condition);
            pthread_mutex_unlock(&pool->mutex);
        }
    }

    return NULL;
}

// 3) Now define thread_pool_wait_until_done
void thread_pool_wait_until_done(ThreadPool* pool) {
    pthread_mutex_lock(&pool->mutex);
    while (1) {
        // if queue->count == 0 and no active tasks, we're done
        if (pool->queue->count == 0 && pool->active_count == 0) {
            pthread_mutex_unlock(&pool->mutex);
            break;
        }
        // otherwise wait on the same condition
        pthread_cond_wait(&pool->condition, &pool->mutex);
    }
}

/**
 * @brief Creates a thread pool with a specified number of threads.
 *
 * This function initializes a thread pool structure, allocates memory for the threads,
 * and sets up the necessary synchronization primitives. It also initializes the file queue
 * and other relevant fields.
 *
 * @param num_threads The number of threads to create in the thread pool.
 * @param base_path The base path to be used by the thread pool.
 * @param config A pointer to the configuration structure.
 * @return A pointer to the newly created ThreadPool structure.
 */
ThreadPool* create_thread_pool(size_t num_threads, const char* base_path, CConfig* config) {
    ThreadPool* pool = malloc(sizeof(ThreadPool));
    pool->num_threads = num_threads;
    pool->threads = malloc(num_threads * sizeof(pthread_t));
    pool->queue = create_file_queue();
    pool->base_path = strdup(base_path);
    pool->config = config;
    pool->should_stop = 0;
    pool->active_count = 0;
    
    pool->processed_capacity = INITIAL_QUEUE_SIZE;
    pool->processed_count = 0;
    pool->processed_files = malloc(pool->processed_capacity * sizeof(FileEntry*));
    
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

void thread_pool_process_directory(ThreadPool* pool) {
    printf("Starting directory processing...\n");
    if (!pool || !pool->base_path) {
        printf("Error: Invalid pool or base path\n");
        return;
    }
    printf("Processing directory: %s\n", pool->base_path);
    process_directory(pool, pool->base_path);
    printf("Directory processing complete\n");
}


static int compare_file_entries(const void* a, const void* b) {
    FileEntry* fa = *(FileEntry**)a;
    FileEntry* fb = *(FileEntry**)b;
    return fb->priority - fa->priority;
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

/**
 * @brief Processes the files in the thread pool and divides them into chunks.
 *
 * This function processes the files stored in the thread pool, dividing them into chunks
 * based on the maximum chunk size specified in the pool's configuration. Each chunk is
 * written out using the `write_chunk` function. If a file's content is too large to fit
 * into a single chunk, it is split into multiple parts.
 *
 * @param pool A pointer to the ThreadPool structure containing the files to be processed.
 *             If the pool is NULL, or if there are no processed files, the function returns
 *             immediately.
 *
 * The function performs the following steps:
 * 1. Sorts the processed files using `qsort` and the `compare_file_entries` comparator.
 * 2. Allocates memory for the current chunk buffer.
 * 3. Iterates over each processed file entry:
 *    - If the file entry has no content, it is skipped.
 *    - Calculates the size of the file entry's content.
 *    - Determines the total size needed for the chunk header and file content.
 *    - If the current chunk buffer cannot accommodate the new file entry, the current chunk
 *      is written out and a new chunk is started.
 *    - If the file entry is too large to fit into a single chunk, it is split into multiple
 *      parts, each written out as a separate chunk.
 *    - Otherwise, the file entry is added to the current chunk.
 * 4. If there is any remaining data in the current chunk buffer after processing all files,
 *    it is written out.
 * 5. Frees the allocated memory for the current chunk buffer.
 *
 * The function uses the following constants:
 * - `CHUNK_HEADER_SIZE`: The size of the buffer allocated for the chunk header.
 * - `CHUNK_HEADER`: The format string for the chunk header.
 * - `FILE_SEPARATOR`: The separator string used between file entries in a chunk.
 */
void process_chunks(ThreadPool* pool) {
    if (!pool || !pool->processed_files || pool->processed_count == 0) return;
    printf("Processing %zu files into chunks...\n", pool->processed_count);

    const size_t CHUNK_HEADER_SIZE = 128;  
    const char* CHUNK_HEADER = "chunk %d\n>>>> %s\n";
    const char* FILE_SEPARATOR = "\n";

    qsort(pool->processed_files, pool->processed_count, sizeof(FileEntry*), compare_file_entries);

    size_t chunk_size = pool->config->max_size;
    char* current_chunk = malloc(chunk_size + CHUNK_HEADER_SIZE);
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

        size_t header_len = snprintf(NULL, 0, CHUNK_HEADER, chunk_number, entry->path) + 1;
        size_t total_needed = header_len + entry_size + strlen(FILE_SEPARATOR);

        if (chunk_used > 0 && (chunk_used + total_needed > chunk_size)) {
            write_chunk(current_chunk, chunk_used, chunk_number++, pool->config);
            chunk_used = 0;
        }

        if (total_needed > chunk_size) {
            if (chunk_used > 0) {
                write_chunk(current_chunk, chunk_used, chunk_number++, pool->config);
                chunk_used = 0;
            }

            size_t content_pos = 0;
            size_t remaining = entry_size;
            int part = 0;

            while (remaining > 0) {
                chunk_used = 0;
                size_t can_take = chunk_size - header_len - strlen(FILE_SEPARATOR);
                size_t taking = (remaining > can_take) ? can_take : remaining;

                chunk_used += snprintf(current_chunk + chunk_used, CHUNK_HEADER_SIZE,
                    "chunk %d\n>>>> %s:part %d\n", chunk_number, entry->path, part);

                memcpy(current_chunk + chunk_used,
                       entry->content + content_pos,
                       taking);
                chunk_used += taking;

                strcpy(current_chunk + chunk_used, FILE_SEPARATOR);
                chunk_used += strlen(FILE_SEPARATOR);

                write_chunk(current_chunk, chunk_used, chunk_number++, pool->config);

                content_pos += taking;
                remaining -= taking;
                part++;
            }
            continue;
        }

        // file fits in chunk
        chunk_used += snprintf(current_chunk + chunk_used, CHUNK_HEADER_SIZE,
            CHUNK_HEADER, chunk_number, entry->path);

        memcpy(current_chunk + chunk_used, entry->content, entry_size);
        chunk_used += entry_size;

        strcpy(current_chunk + chunk_used, FILE_SEPARATOR);
        chunk_used += strlen(FILE_SEPARATOR);
    }

    if (chunk_used > 0) {
        write_chunk(current_chunk, chunk_used, chunk_number, pool->config);
    }

    free(current_chunk);
}

static void parse_and_merge_gitignore(CConfig* config, const char* gitignore_path) {
    FILE* f = fopen(gitignore_path, "r");
    if (!f) {
        return;
    }

    char line[1024];
    while (fgets(line, sizeof(line), f)) {
        char* nl = strrchr(line, '\n');
        if (nl) *nl = '\0';

        if (line[0] == '\0' || line[0] == '#') {
            continue;
        }

        config->num_ignore += 1;
        config->ignore_patterns = realloc(config->ignore_patterns,
            config->num_ignore * sizeof(char*));
        if (!config->ignore_patterns) {
            fclose(f);
            return; // out of memory
        }

        char* pattern = strdup(line);
        config->ignore_patterns[config->num_ignore - 1] = pattern;
    }

    fclose(f);
}