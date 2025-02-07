#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include "../../include/thread_pool.h"  
#include "../../include/utils.h"        

static void make_test_file(const char* dir, const char* filename, const char* content) {
    char path[4096];
    snprintf(path, sizeof(path), "%s/%s", dir, filename);
    FILE* fp = fopen(path, "wb");
    assert(fp && "Failed to create test file");
    fwrite(content, 1, strlen(content), fp);
    fclose(fp);
}

static void remove_recursively(const char* path) {
    // Danger: very simplistic recursion removal with "rm -rf".
    char cmd[1024];
    snprintf(cmd, sizeof(cmd), "rm -rf %s", path);
    system(cmd);
}

static void create_test_environment(const char* base_dir) {
    mkdir(base_dir, 0777);

    char subdir[512];
    snprintf(subdir, sizeof(subdir), "%s/subdir", base_dir);
    mkdir(subdir, 0777);

    make_test_file(base_dir, "keep.txt", "keep.txt content line1\nline2\n");
    make_test_file(base_dir, "ignore.me", "ignore.me content\n");
    make_test_file(base_dir, "binary.bin", "ABC\0DEF", 7);
    make_test_file(base_dir, "another.txt", "another.txt line1\nline2\nsome more lines\n");
    make_test_file(subdir, "subfile.txt", "subfile content\nLine 2\n");
}

static int count_chunk_files(const char* dir) {
    char cmd[1024];
    snprintf(cmd, sizeof(cmd), "ls -1 %s/chunk-*.txt 2>/dev/null | wc -l", dir);
    FILE* fp = popen(cmd, "r");
    if (!fp) return -1;
    int count = 0;
    fscanf(fp, "%d", &count);
    pclose(fp);
    return count;
}

static int check_for_aggregator(const char* dir) {
    char aggregator[1024];
    snprintf(aggregator, sizeof(aggregator), "%s/whole_chunk_mode-output.txt", dir);
    FILE* fp = fopen(aggregator, "rb");
    if (!fp) return 0;
    fclose(fp);
    return 1;
}

static void scenario_basic_ignore(void) {
    printf("=== scenario_basic_ignore ===\n");
    char test_dir[] = "basic_ignore_testXXXXXX";
    char* tmp = mkdtemp(test_dir);
    assert(tmp && "mkdtemp failed for scenario_basic_ignore");

    create_test_environment(test_dir);

    CConfig config;
    memset(&config, 0, sizeof(config));
    config.max_size = 512;
    config.token_mode = 0;   // byte-based
    config.stream = 0;       // not streaming => produce chunk-N.txt
    config.output_dir = strdup(test_dir);
    config.num_ignore = 1;
    config.ignore_patterns = malloc(sizeof(char*));
    config.ignore_patterns[0] = strdup("*.me");
    config.num_unignore = 0;
    config.unignore_patterns = NULL;
    config.num_priority_rules = 0;
    config.priority_rules = NULL;
    config.num_binary_exts = 1;
    config.binary_exts = malloc(sizeof(char*));
    config.binary_exts[0] = strdup("bin");
    config.whole_chunk_mode = 0;

    ThreadPool* pool = create_thread_pool(2, ".", &config);
    assert(pool && "Failed to create thread pool for scenario_basic_ignore");

    thread_pool_process_directory(pool, test_dir);
    thread_pool_wait_until_done(pool);
    process_chunks(pool);

    int chunk_count = count_chunk_files(test_dir);
    printf("chunk_count = %d\n", chunk_count);
    assert(chunk_count >= 3 && "Expected at least 3 chunk files (ignore.me and binary.bin should not appear).");

    int aggregator_exists = check_for_aggregator(test_dir);
    assert(!aggregator_exists && "No aggregator file should exist in basic_ignore scenario.");

    destroy_thread_pool(pool);

    // free config fields
    free(config.output_dir);
    for (size_t i = 0; i < config.num_ignore; i++) {
        free(config.ignore_patterns[i]);
    }
    free(config.ignore_patterns);

    for (size_t i = 0; i < config.num_binary_exts; i++) {
        free(config.binary_exts[i]);
    }
    free(config.binary_exts);

    remove_recursively(test_dir);
    printf("=== scenario_basic_ignore PASSED ===\n\n");
}

static void scenario_priority_aggregator_token(void) {
    printf("=== scenario_priority_aggregator_token ===\n");
    char test_dir[] = "priority_agg_tokenXXXXXX";
    char* tmp = mkdtemp(test_dir);
    assert(tmp && "mkdtemp failed for scenario_priority_aggregator_token");

    create_test_environment(test_dir);

    CConfig config;
    memset(&config, 0, sizeof(config));
    config.max_size = 50;   
    config.token_mode = 1;  // chunk by tokens
    config.stream = 0;     
    config.whole_chunk_mode = 1;  // aggregator mode => single file

    config.output_dir = strdup(test_dir);

    config.num_ignore = 0;
    config.ignore_patterns = NULL;
    config.num_unignore = 0;
    config.unignore_patterns = NULL;

    config.num_priority_rules = 2;
    config.priority_rules = malloc(config.num_priority_rules * sizeof(CPriorityRule));
    config.priority_rules[0].pattern = strdup("*another.txt");
    config.priority_rules[0].score = 10;
    config.priority_rules[1].pattern = strdup("*keep.txt");
    config.priority_rules[1].score = 5;

    config.num_binary_exts = 1;
    config.binary_exts = malloc(sizeof(char*));
    config.binary_exts[0] = strdup("bin");

    ThreadPool* pool = create_thread_pool(2, ".", &config);
    assert(pool && "Failed to create pool for scenario_priority_aggregator_token");

    thread_pool_process_directory(pool, test_dir);
    thread_pool_wait_until_done(pool);
    process_chunks(pool);

    int chunk_count = count_chunk_files(test_dir);
    printf("scenario2 chunk_count = %d\n", chunk_count);
    assert(chunk_count == 0 && "Expected 0 chunk-* files in aggregator mode.");

    // aggregator file => yes
    int aggregator_exists = check_for_aggregator(test_dir);
    assert(aggregator_exists && "Expected aggregator file in aggregator mode.");


    {
        char aggregator_path[1024];
        snprintf(aggregator_path, sizeof(aggregator_path), "%s/whole_chunk_mode-output.txt", test_dir);
        size_t aggregator_size;
        char* aggregator_data = read_file_contents(aggregator_path, &aggregator_size);
        assert(aggregator_data && "Failed to read aggregator file data");

        char* another_pos = strstr(aggregator_data, "another.txt");
        char* keep_pos    = strstr(aggregator_data, "keep.txt");
        assert(another_pos && keep_pos && "Didn't find expected filenames in aggregator");
        assert(another_pos < keep_pos && "another.txt has higher priority => should appear first");

        free(aggregator_data);
    }

    destroy_thread_pool(pool);

    free(config.output_dir);
    for (size_t i = 0; i < config.num_priority_rules; i++) {
        free(config.priority_rules[i].pattern);
    }
    free(config.priority_rules);

    for (size_t i = 0; i < config.num_binary_exts; i++) {
        free(config.binary_exts[i]);
    }
    free(config.binary_exts);

    remove_recursively(test_dir);
    printf("=== scenario_priority_aggregator_token PASSED ===\n\n");
}

static void scenario_stream_stdout(void) {
    printf("=== scenario_stream_stdout ===\n");
    char test_dir[] = "stream_stdoutXXXXXX";
    char* tmp = mkdtemp(test_dir);
    assert(tmp && "mkdtemp failed for scenario_stream_stdout");

    create_test_environment(test_dir);

    CConfig config;
    memset(&config, 0, sizeof(config));
    config.max_size = 100000;  
    config.token_mode = 0;
    config.stream = 1;       
    config.whole_chunk_mode = 0; 

    config.output_dir = NULL; 

    config.num_ignore = 1;
    config.ignore_patterns = malloc(sizeof(char*));
    config.ignore_patterns[0] = strdup("binary.bin");

    config.num_unignore = 0;
    config.unignore_patterns = NULL;

    config.num_priority_rules = 0;
    config.priority_rules = NULL;

    config.num_binary_exts = 1;
    config.binary_exts = malloc(sizeof(char*));
    config.binary_exts[0] = strdup("bin");

    ThreadPool* pool = create_thread_pool(2, ".", &config);
    assert(pool);

    thread_pool_process_directory(pool, test_dir);
    thread_pool_wait_until_done(pool);
    process_chunks(pool);

    int chunk_count = count_chunk_files(test_dir);
    assert(chunk_count == 0 && "Should produce no chunk files when streaming to stdout.");

    int aggregator_exists = check_for_aggregator(test_dir);
    assert(!aggregator_exists);

    destroy_thread_pool(pool);

    free(config.ignore_patterns[0]);
    free(config.ignore_patterns);
    for (size_t i = 0; i < config.num_binary_exts; i++) {
        free(config.binary_exts[i]);
    }
    free(config.binary_exts);

    remove_recursively(test_dir);
    printf("=== scenario_stream_stdout PASSED ===\n\n");
}

int main(void) {
    scenario_basic_ignore();
    scenario_priority_aggregator_token();
    scenario_stream_stdout();

    printf("\nAll thread_pool tests completed successfully!\n");
    return 0;
}
