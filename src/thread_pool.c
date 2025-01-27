// src/thread_pool.c
#include "thread_pool.h"
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <libgen.h>
#include <fnmatch.h>
#include <stdio.h>

#define INITIAL_QUEUE_SIZE 1024
#define MAX_PATH 4096
#define READ_CHUNK_SIZE 8192

static char* read_file_contents(const char* path, size_t* size_out) {
    FILE* file = fopen(path, "rb");
    if (!file) return NULL;

    char* buffer = NULL;
    char* new_buffer;
    size_t used = 0;
    size_t buffer_size = READ_CHUNK_SIZE;
    buffer = malloc(buffer_size);

    while (!feof(file)) {
        if (used + READ_CHUNK_SIZE > buffer_size) {
            buffer_size *= 2;
            new_buffer = realloc(buffer, buffer_size);
            if (!new_buffer) {
                free(buffer);
                fclose(file);
                return NULL;
            }
            buffer = new_buffer;
        }

        size_t read_size = fread(buffer + used, 1, READ_CHUNK_SIZE, file);
        if (read_size == 0) break;
        used += read_size;
    }

    fclose(file);

    if (used + 1 > buffer_size) {
        new_buffer = realloc(buffer, used + 1);
        if (!new_buffer) {
            free(buffer);
            return NULL;
        }
        buffer = new_buffer;
    }
    buffer[used] = '\0';
    
    if (size_out) *size_out = used;
    return buffer;
}

static int should_ignore_file(const char* filename, const CConfig* config) {
    for (size_t i = 0; i < config->num_ignore; i++) {
        if (fnmatch(config->ignore_patterns[i], filename, FNM_PATHNAME) == 0) {
            return 1;
        }
    }
    return 0;
}

static int calculate_priority(const char* filename, const CConfig* config) {
    int highest_priority = 0;
    for (size_t i = 0; i < config->num_priority_rules; i++) {
        if (fnmatch(config->priority_rules[i].pattern, filename, FNM_PATHNAME) == 0) {
            if (config->priority_rules[i].score > highest_priority) {
                highest_priority = config->priority_rules[i].score;
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
    DIR* dir = opendir(dir_path);
    if (!dir) return;

    struct dirent* entry;
    char full_path[MAX_PATH];
    
    while ((entry = readdir(dir))) {
        if (entry->d_name[0] == '.') continue;
        
        snprintf(full_path, MAX_PATH, "%s/%s", dir_path, entry->d_name);
        
        struct stat st;
        if (stat(full_path, &st) == -1) continue;

        if (S_ISDIR(st.st_mode)) {
            process_directory(pool, full_path);  
        }
        else if (S_ISREG(st.st_mode)) {
            if (should_ignore_file(full_path, pool->config)) continue;
            if (is_binary_file(full_path, pool->config)) continue;

            FileEntry* file_entry = malloc(sizeof(FileEntry));
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
        }
        
        pthread_mutex_unlock(&pool->mutex);
        
        if (entry) {
            process_file(entry, pool->config);
            
            pthread_mutex_lock(&pool->processed_mutex);
            if (pool->processed_count == pool->processed_capacity) {
                pool->processed_capacity *= 2;
                pool->processed_files = realloc(pool->processed_files, 
                    pool->processed_capacity * sizeof(FileEntry*));
            }
            pool->processed_files[pool->processed_count++] = entry;
            pthread_mutex_unlock(&pool->processed_mutex);
        }
    }
    
    return NULL;
}

ThreadPool* create_thread_pool(size_t num_threads, const char* base_path, CConfig* config) {
    ThreadPool* pool = malloc(sizeof(ThreadPool));
    pool->num_threads = num_threads;
    pool->threads = malloc(num_threads * sizeof(pthread_t));
    pool->queue = create_file_queue();
    pool->base_path = strdup(base_path);
    pool->config = config;
    pool->should_stop = 0;
    
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
    if (!pool || !pool->base_path) return;
    process_directory(pool, pool->base_path);
}