#include "../include/utils.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

size_t count_tokens(const char* text) {
    if (!text) return 0;
    
    size_t count = 0;
    int in_space = 1;
    
    for (const char* p = text; *p; p++) {
        if (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') {
            in_space = 1;
        } else {
            if (in_space) count++;
            in_space = 0;
        }
    }
    return count;
}

/**
 * Reads the contents of a file into a dynamically allocated buffer.
 *
 * @param path The path to the file to be read.
 * @param size_out A pointer to a size_t variable where the size of the read data will be stored.
 *                 If NULL, the size will not be stored.
 * @return A pointer to the buffer containing the file contents, or NULL if an error occurred.
 *         The caller is responsible for freeing the buffer.
 */
char* read_file_contents(const char* path, size_t* size_out) {
    FILE* file = fopen(path, "rb");
    if (!file) return NULL;

    size_t used = 0;
    size_t capacity = 8192;
    char* buffer = malloc(capacity);
    
    while (!feof(file)) {
        if (used + 4096 > capacity) {
            capacity *= 2;
            char* new_buf = realloc(buffer, capacity);
            if (!new_buf) {
                free(buffer);
                fclose(file);
                return NULL;
            }
            buffer = new_buf;
        }
        
        size_t read = fread(buffer + used, 1, 4096, file);
        if (read == 0) break;
        used += read;
    }
    
    fclose(file);
    
    if (size_out) *size_out = used;
    buffer[used] = '\0';
    return buffer;
}