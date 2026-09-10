/* ============================================================
 * MP3GetNextFrameInfo   @ 0x002b87f4   size=80B   callers=0
 * module: 06_helix_mp3
 * ============================================================ */

undefined4 MP3GetNextFrameInfo(int param_1,undefined4 param_2,undefined4 param_3)

{
  int iVar1;
  
  if (param_1 == 0) {
    return 0xfffffffb;
  }
  iVar1 = xmp3_UnpackFrameHeader(param_1,param_3);
  if ((iVar1 != -1) && (*(int *)(param_1 + 2000) == 3)) {
    MP3GetLastFrameInfo(param_1,param_2);
    return 0;
  }
  return 0xfffffffa;
}
