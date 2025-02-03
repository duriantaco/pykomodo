// include/thread_pool.h
#ifndef THREAD_POOL_H
#define THREAD_POOL_H

#include <pthread.h>
#include "myheader.h"

typedef struct {
    char* path;
    char* content;
    int priority;
    size_t size;
} FileEntry;

typedef struct {
    FileEntry** entries;
    size_t count;
    size_t capacity;
    pthread_mutex_t mutex;
} FileQueue;

typedef struct {
    pthread_t* threads;
    size_t num_threads;
    FileQueue* queue;
    char* base_path;
    CConfig* config;
    int should_stop;
    pthread_mutex_t mutex;
    pthread_cond_t condition;
    FileEntry** processed_files;
    size_t processed_count;
    size_t processed_capacity;
    pthread_mutex_t processed_mutex;
    size_t active_count;
} ThreadPool;

ThreadPool* create_thread_pool(size_t num_threads, const char* base_path, CConfig* config);
void destroy_thread_pool(ThreadPool* pool);

void thread_pool_process_directory(ThreadPool* pool, const char* dir_path);
void process_chunks(ThreadPool* pool);

static int compare_file_entries(const void* a, const void* b);
static void write_chunk(const char* content, size_t size, int chunk_num, const CConfig* config);

void thread_pool_wait_until_done(ThreadPool* pool);

#endif