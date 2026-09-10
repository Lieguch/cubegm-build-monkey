/* ============================================================
 * __libc_csu_init   @ 0x002dbc34   size=88B   callers=0
 * module: 99_crt_glibc
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* WARNING: Removing unreachable block (ram,0x002dbc60) */

void __libc_csu_init(int argc,char **argv,char **envp)

{
  int iVar1;
  undefined **ppuVar2;
  
                    /* Unresolved local var: size_t size@[???] */
  _init((EVP_PKEY_CTX *)argc);
                    /* Unresolved local var: size_t i@[???] */
  iVar1 = 0;
  ppuVar2 = &__frame_dummy_init_array_entry;
  do {
    iVar1 = iVar1 + 1;
    (*(code *)*ppuVar2)(argc,argv,envp);
    ppuVar2 = ppuVar2 + 1;
  } while (iVar1 != 1);
  return;
}
