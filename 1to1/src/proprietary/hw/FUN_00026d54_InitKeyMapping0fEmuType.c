/* ============================================================
 * InitKeyMapping0fEmuType   @ 0x00026d54   size=820B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void InitKeyMapping0fEmuType(void)

{
  gh_u4 uVar1;
  int iVar2;
  FILE *__stream;
  char acStack_1018 [4100];
  
  uVar1 = (gh_u4)GetWorkPath();
  iVar2 = gameType();
  sprintf(acStack_1018,"%ssaves/%s/%s.scf",uVar1,*(gh_u4 *)(ArchivePath + iVar2 * 4),RomName);
  RARCH_LOG("Load %s\n",acStack_1018);
  iVar2 = access(acStack_1018,0);
  if (iVar2 == 0) {
    __stream = fopen(acStack_1018,"rb");
    if (__stream == (FILE *)0x0) goto LAB_00026edc;
    if ((gh_ushort)Filetype == 8) {
      memcpy(keyMapping,DEFKeyMapping,0x60);
    }
    else if ((gh_ushort)Filetype < 9) {
      if ((gh_ushort)Filetype == 2) {
LAB_00026fa4:
        memcpy(keyMapping,NESKeyMapping,0x60);
      }
      else if ((gh_ushort)Filetype == 4) {
        memcpy(keyMapping,DEFKeyMapping,0x60);
      }
      else {
LAB_00026fec:
        memcpy(keyMapping,DEFKeyMapping,0x60);
      }
    }
    else {
      if ((gh_ushort)Filetype != 0x10) {
        if ((gh_ushort)Filetype != 0x400) goto LAB_00026fec;
        goto LAB_00026fa4;
      }
      memcpy(keyMapping,GBAKeyMapping,0x60);
    }
  }
  else {
    DisplayZoomFlag = 0x1ff;
    if ((gh_ushort)Filetype == 8) {
      memcpy(keyMapping,DEFKeyMapping,0x60);
    }
    else if ((gh_ushort)Filetype < 9) {
      if ((gh_ushort)Filetype == 2) {
LAB_00026e34:
        memcpy(keyMapping,NESKeyMapping,0x60);
      }
      else if ((gh_ushort)Filetype == 4) {
        memcpy(keyMapping,DEFKeyMapping,0x60);
      }
      else {
LAB_00026fc8:
        memcpy(keyMapping,DEFKeyMapping,0x60);
      }
    }
    else {
      if ((gh_ushort)Filetype != 0x10) {
        if ((gh_ushort)Filetype != 0x400) goto LAB_00026fc8;
        goto LAB_00026e34;
      }
      memcpy(keyMapping,GBAKeyMapping,0x60);
    }
    uVar1 = (gh_u4)GetWorkPath();
    iVar2 = gameType();
    sprintf(acStack_1018,"%ssaves/%s/default.scf",uVar1,*(gh_u4 *)(ArchivePath + iVar2 * 4));
    RARCH_LOG("Load %s\n",acStack_1018);
    __stream = fopen(acStack_1018,"rb");
    if (__stream == (FILE *)0x0) goto LAB_00026edc;
  }
  fread(&DisplayZoomFlag,4,1,__stream);
  fread(keyMapping,4,0x18,__stream);
  fclose(__stream);
LAB_00026edc:
  video_driver_set_rotation(DisplayZoomFlag);
  init_user_joy_key_mask(keyMapping,8);
  return;
}
