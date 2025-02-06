/* dirent_wrapper.h */
#ifndef DIRENT_WRAPPER_H
#define DIRENT_WRAPPER_H

#ifdef __cplusplus
extern "C" {
#endif

typedef void* DIRHandle;
typedef void* DirEntHandle;

DIRHandle my_opendir(const char* path);
DirEntHandle my_readdir(DIRHandle d);
int my_closedir(DIRHandle d);
const char* my_dirent_name(DirEntHandle ent);

#ifdef __cplusplus
}
#endif

#endif 
