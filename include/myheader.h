#ifndef MYHEADER_H
#define MYHEADER_H

#include <stddef.h>  

typedef struct CPriorityRule {
    char* pattern;
    int score;
} CPriorityRule;

typedef struct CConfig {
    size_t max_size;
    int token_mode;       
    char* output_dir;
    int stream;           
    char** ignore_patterns;
    CPriorityRule* priority_rules;
    char** binary_exts;
    size_t num_ignore;
    size_t num_priority_rules;
    size_t num_binary_exts;
} CConfig;

typedef struct ProcessedFile {
    char* rel_path;
    char* content;
    int priority;
} ProcessedFile;

#endif