#include "dirent_wrapper.h"
#include <dirent.h>
#include <stdlib.h>

DIRHandle my_opendir(const char* path)
{
    DIR* d = opendir(path);
    return (DIRHandle)d;
}

DirEntHandle my_readdir(DIRHandle d)
{
    DIR* dd = (DIR*)d;
    struct dirent* e = readdir(dd);
    return (DirEntHandle)e;
}

int my_closedir(DIRHandle d)
{
    DIR* dd = (DIR*)d;
    return closedir(dd);
}

const char* my_dirent_name(DirEntHandle ent)
{
    struct dirent* e = (struct dirent*)ent;
    if (!e) return NULL;
    return e->d_name;
}
