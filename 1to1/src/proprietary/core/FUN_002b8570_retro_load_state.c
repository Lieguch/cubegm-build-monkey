/* ============================================================
 * retro_load_state   @ 0x002b8570   size=344B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 retro_load_state(char *param_1)

{
  void *__ptr;
  FILE *__stream;
  void *__ptr_00;
  int local_20;
  size_t local_1c [2];
  
  _retro_serialize_size = (code *)dlsym(handle,"retro_serialize_size");
  if (_retro_serialize_size == (code *)0x0) {
    RARCH_LOG("find retro_serialize_size process fail \n");
    return 0;
  }
  local_20 = (*_retro_serialize_size)();
  __ptr = malloc(local_20 << 1);
  if (__ptr != (void *)0x0) {
    __stream = fopen(param_1,"rb");
    if (__stream != (FILE *)0x0) {
      fseek(__stream,0,0);
      fread(local_1c,1,4,__stream);
      __ptr_00 = malloc(local_1c[0]);
      fread(__ptr_00,1,local_1c[0],__stream);
      fclose(__stream);
      uncompress(__ptr,&local_20,__ptr_00,local_1c[0]);
      free(__ptr_00);
    }
    _retro_unserialize = (code *)dlsym(handle,"retro_unserialize");
    if (_retro_unserialize == (code *)0x0) {
      RARCH_LOG("find retro_unserialize process fail \n");
      return 0;
    }
    (*_retro_unserialize)(__ptr,local_20);
    free(__ptr);
  }
  return 1;
}
