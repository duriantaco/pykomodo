#ifndef UTILS_H
#define UTILS_H

#include <stddef.h>

size_t count_tokens(const char* text);
char* read_file_contents(const char* path, size_t* size_out);

#endif