#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "../../include/utils.h"

static void test_count_tokens(void) {
    assert(count_tokens(NULL) == 0);

    assert(count_tokens("") == 0);

    assert(count_tokens("    \t  \n  ") == 0);

    assert(count_tokens("Hello") == 1);

    assert(count_tokens("Hello world") == 2);

    assert(count_tokens("   Leading  spaces    here  ") == 3);

    assert(count_tokens(" multiple\twords \n across \r different whitespace") == 5);

    printf("test_count_tokens: All assertions passed.\n");
}

static void test_read_file_contents(void) {
    {
        char* data = read_file_contents("no_such_file_123.txt", NULL);
        assert(data == NULL);
    }

    const char* tmp_filename = "test_tempfile.txt";
    {
        const char* expected = "Hello, file content!\nAnother line.";
        FILE* fp = fopen(tmp_filename, "wb");
        assert(fp && "Failed to create test file.");
        fwrite(expected, 1, strlen(expected), fp);
        fclose(fp);

        size_t size_out = 0;
        char* data = read_file_contents(tmp_filename, &size_out);
        assert(data != NULL && "read_file_contents returned NULL unexpectedly");
        assert(size_out == strlen(expected));

        assert(strcmp(data, expected) == 0);
        free(data);

        remove(tmp_filename);
    }

    printf("test_read_file_contents: All assertions passed.\n");
}

int main(void) {
    test_count_tokens();
    test_read_file_contents();

    printf("All tests in test_utils passed successfully.\n");
    return 0;
}
