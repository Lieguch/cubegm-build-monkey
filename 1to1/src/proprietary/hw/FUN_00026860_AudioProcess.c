/* ============================================================
 * AudioProcess   @ 0x00026860   size=744B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void AudioProcess(void)

{
  gh_byte bVar1;
  gh_byte bVar2;
  gh_u2 uVar3;
  gh_u2 uVar4;
  short sVar5;
  gh_u4 uVar6;
  gh_byte *pbVar7;
  short *psVar8;
  gh_byte *pbVar9;
  int iVar10;
  int iVar11;
  int iVar12;
  int iVar13;
  int iVar14;
  int *piVar15;
  gh_uint in_fpscr;
  float fVar16;
  float fVar17;
  float fVar18;
  gh_u1 *local_74;
  int local_70;
  short local_60 [4];
  timeval local_58;
  timeval local_50;
  struct timezone tStack_48;
  struct timezone tStack_40;
  
  if (((SoundPlayer_blob)._0_4_ != 0) && ((SoundPlayer_blob)._32_4_ = 0, (SoundPlayer_blob)._4_4_ == 1)) {
    Mp3DecodeLoop(0);
  }
  if (((SoundPlayer_blob)._36_4_ != 0) && ((SoundPlayer_blob)._68_4_ = 0, (SoundPlayer_blob)._40_4_ == 1)) {
    Mp3DecodeLoop();
  }
  fVar18 = 0.0;
  local_74 = SoundBuffer;
  local_70 = 0x3ceaf2;
  do {
    iVar11 = 0;
    *(gh_u2 *)(local_70 + -2) = 0;
    *(gh_u2 *)(local_74 + 2) = 0;
    piVar15 = (int *)SoundPlayer;
    do {
      iVar10 = *piVar15;
      if (iVar10 != 0) {
        fVar17 = (float)piVar15[8];
        in_fpscr = in_fpscr & 0xfffffff | (gh_uint)(fVar17 == fVar18) << 0x1e |
                   (gh_uint)(fVar18 <= fVar17) << 0x1d;
        bVar1 = (gh_byte)(in_fpscr >> 0x18);
        if (!(gh_bool)(bVar1 >> 5 & 1) || (gh_bool)(bVar1 >> 6)) {
          iVar13 = piVar15[3];
          iVar12 = piVar15[7];
          iVar14 = piVar15[2];
          do {
            if (iVar13 == 0) {
              psVar8 = (short *)piVar15[6];
              if (iVar14 == 0) {
                pbVar9 = (gh_byte *)((int)psVar8 + 1);
                sVar5 = (short)(char)*psVar8 << 8;
                piVar15[6] = (int)pbVar9;
                *(short *)((int)local_60 + iVar11) = sVar5;
              }
              else {
                pbVar9 = (gh_byte *)(psVar8 + 1);
                sVar5 = *psVar8;
                *(short *)((int)local_60 + iVar11) = sVar5;
                piVar15[6] = (int)pbVar9;
              }
              *(short *)((int)local_60 + iVar11 + 2) = sVar5;
            }
            else {
              pbVar7 = (gh_byte *)piVar15[6];
              if (iVar14 == 0) {
                pbVar9 = pbVar7 + 2;
                bVar1 = *pbVar7;
                piVar15[6] = (int)(pbVar7 + 1);
                bVar2 = pbVar7[1];
                *(gh_ushort *)((int)local_60 + iVar11) = (gh_ushort)bVar1 << 8;
                piVar15[6] = (int)pbVar9;
                *(gh_ushort *)((int)local_60 + iVar11 + 2) = (gh_ushort)bVar2 << 8;
              }
              else {
                uVar3 = *(gh_u2 *)pbVar7;
                pbVar9 = pbVar7 + 4;
                uVar4 = *(gh_u2 *)(pbVar7 + 2);
                piVar15[6] = (int)pbVar9;
                *(gh_u2 *)((int)local_60 + iVar11) = uVar3;
                *(gh_u2 *)((int)local_60 + iVar11 + 2) = uVar4;
              }
            }
            if (iVar12 <= (int)pbVar9) {
              if (piVar15[5] == 0) {
                *piVar15 = 0;
                break;
              }
              piVar15[6] = iVar10;
            }
            uVar6 = __aeabi_idiv((gh_uint)0xf4240,piVar15[4]);
            fVar16 = (float)VectorSignedToFloat(uVar6,(gh_byte)(in_fpscr >> 0x16) & 3);
            fVar17 = fVar16 + fVar17;
            in_fpscr = in_fpscr & 0xfffffff | (gh_uint)(fVar17 == fVar18) << 0x1e |
                       (gh_uint)(fVar18 <= fVar17) << 0x1d;
            piVar15[8] = (int)fVar17;
            bVar1 = (gh_byte)(in_fpscr >> 0x18);
          } while (!(gh_bool)(bVar1 >> 5 & 1) || (gh_bool)(bVar1 >> 6));
        }
        sVar5 = *(short *)((int)local_60 + iVar11 + 2);
        *(short *)(local_70 + -2) = *(short *)(local_70 + -2) + *(short *)((int)local_60 + iVar11);
        *(short *)(local_74 + 2) = sVar5 + *(short *)(local_74 + 2);
      }
      iVar11 = iVar11 + 4;
      piVar15 = piVar15 + 9;
    } while (iVar11 != 8);
    fVar18 = fVar18 + 22.0;
    *(short *)(local_70 + -2) = *(short *)(local_70 + -2) / 2;
    *(short *)(local_74 + 2) = *(short *)(local_74 + 2) / 2;
    local_74 = local_74 + 4;
    local_70 = local_70 + 4;
    if (local_74 == (gh_u1 *)0x3cf66c) {
      gettimeofday(&local_58,&tStack_48);
      PlaySound(SoundBuffer,0x2df);
      gettimeofday(&local_50,&tStack_40);
      if (5000 < ((local_50.tv_sec - local_58.tv_sec) * 1000000 + local_50.tv_usec) -
                 local_58.tv_usec) {
        RARCH_LOG("[%d.%06d] ++++ AudioProcess timer over %dus ++++\n");
        errorcount = errorcount + 1;
      }
      return;
    }
  } while( true );
}
