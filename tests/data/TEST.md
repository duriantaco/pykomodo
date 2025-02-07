# To compile 

for `test_utils`: `gcc -o test_utils test_utils.c ../../src/utils.c -I../include -Wall -Wextra -std=c99`

for `test_thread_pool`: `gcc -o test_thread_pool ../../src/thread_pool.c ../../src/thread_pool.c \ ../../src/utils.c -I. -lpthread -Wall -Wextra -std=c99`
 