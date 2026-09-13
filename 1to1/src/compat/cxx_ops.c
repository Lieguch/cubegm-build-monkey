/* cxx_ops.c — 静态链接测试用的 libstdc++ operator new/delete 替身
 *
 * 工厂 rkgame 是动态链接，_Znwj/_ZdlPv 由 libstdc++.so 提供（symtab 中为 *UND*）。
 * 本机静态试链没有 libstdc++（zig 的 musl 目标不带），故提供等价实现：
 *   _Znwj/_Znaj -> malloc ；_ZdlPv/_ZdaPv -> free
 * 仅用于 P3/P4 的链接与 ABI 验证；真机部署仍走动态 libstdc++（与工厂一致）。
 */
#include <stdlib.h>

void * _Znwj(unsigned int n)  { return malloc(n ? n : 1); }
void * _Znaj(unsigned int n)  { return malloc(n ? n : 1); }
void   _ZdlPv(void *p)        { free(p); }
void   _ZdaPv(void *p)        { free(p); }

/* nothrow 变体（若被引用） */
void * _ZnwjRKSt9nothrow_t(unsigned int n, const void *nt) { (void)nt; return malloc(n ? n : 1); }
void   _ZdlPvm(void *p, unsigned int n) { (void)n; free(p); }
