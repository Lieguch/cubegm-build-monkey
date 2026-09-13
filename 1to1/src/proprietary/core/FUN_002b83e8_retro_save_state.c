/* ============================================================
 * retro_save_state   @ 0x002b83e8   size=352B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 retro_save_state(char *param_1)

{
  void *__ptr;
  FILE *__s;
  void *__ptr_00;
  size_t local_20;
  size_t local_1c;
  
  _retro_serialize_size = (gh_code *)dlsym(handle_emurun,"retro_serialize_size");
  if (_retro_serialize_size == (gh_code *)0x0) {
    RARCH_LOG("find retro_serialize_size process fail \n");
    return 0;
  }
  local_20 = (*_retro_serialize_size)();
  __ptr = malloc(local_20 << 1);
  if (__ptr != (void *)0x0) {
    _retro_serialize = (gh_code *)dlsym(handle_emurun,"retro_serialize");
    if (_retro_serialize == (gh_code *)0x0) {
      RARCH_LOG("find retro_serialize process fail \n");
      return 0;
    }
    (*_retro_serialize)(__ptr,local_20);
    RARCH_LOG("retro_save_state:%s\n",param_1);
    __s = fopen(param_1,"wb");
    if (__s != (FILE *)0x0) {
      local_1c = local_20;
      __ptr_00 = malloc(local_20);
      compress(__ptr_00,&local_1c,__ptr,local_20);
      local_20 = local_1c;
      fwrite(&local_20,1,4,__s);
      fwrite(__ptr_00,1,local_20,__s);
      free(__ptr_00);
      fclose(__s);
    }
    free(__ptr);
  }
  return 1;
}
