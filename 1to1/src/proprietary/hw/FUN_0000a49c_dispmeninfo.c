/* ============================================================
 * dispmeninfo   @ 0x0000a49c   size=128B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

void dispmeninfo(void)

{
  FILE *__stream;
  int iVar1;
  char acStack_7c [104];
  
  puts("\n============================");
  __stream = fopen("/proc/meminfo","rb");
  if (__stream != (FILE *)0x0) {
    iVar1 = 4;
    do {
      fgets(acStack_7c,100,__stream);
      printf("%s",acStack_7c);
      iVar1 = iVar1 + -1;
    } while (iVar1 != 0);
    fclose(__stream);
  }
  puts("============================");
  return;
}
