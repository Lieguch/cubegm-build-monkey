/* ============================================================
 * SaveKeyMappingConfigFile   @ 0x000270e4   size=376B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SaveKeyMappingConfigFile(void)

{
  gh_u4 uVar1;
  int iVar2;
  FILE *__s;
  char acStack_90 [128];
  
  uVar1 = GetWorkPath();
  sprintf(acStack_90,"%ssaves",uVar1);
  iVar2 = access(acStack_90,0);
  if (iVar2 != 0) {
    mkdir(acStack_90,0x1ed);
  }
  uVar1 = GetWorkPath();
  iVar2 = gameType();
  sprintf(acStack_90,"%ssaves/%s",uVar1,*(gh_u4 *)(ArchivePath + iVar2 * 4));
  iVar2 = access(acStack_90,0);
  if (iVar2 != 0) {
    mkdir(acStack_90,0x1ed);
  }
  uVar1 = GetWorkPath();
  iVar2 = gameType();
  sprintf(acStack_90,"%ssaves/%s/%s.scf",uVar1,*(gh_u4 *)(ArchivePath + iVar2 * 4),RomName);
  RARCH_LOG("Save %s\n",acStack_90);
  __s = fopen(acStack_90,"wb");
  if (__s != (FILE *)0x0) {
    fwrite(&DisplayZoomFlag,4,1,__s);
    fwrite(keyMapping,4,0x18,__s);
    fflush(__s);
    iVar2 = fileno(__s);
    fsync(iVar2);
    fclose(__s);
  }
  init_user_joy_key_mask(keyMapping,8);
  return;
}
