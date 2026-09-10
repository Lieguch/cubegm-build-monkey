/* ============================================================
 * mui_load_state   @ 0x0002eac8   size=2020B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 mui_load_state(void)

{
  gh_u4 uVar1;
  int iVar2;
  FILE *__stream;
  long lVar3;
  void *__ptr;
  void *__ptr_00;
  gh_uint uVar4;
  bool bVar5;
  size_t __size;
  int iVar6;
  int local_dc;
  size_t local_d8;
  void *local_d4;
  int local_d0;
  int local_cc;
  int local_c8;
  int local_c4;
  int local_c0;
  void *local_bc;
  int local_b8;
  int local_b4;
  int local_b0;
  int local_ac;
  int local_a8;
  int local_a4 [6];
  char acStack_8c [104];
  
  DAT_003af27c = 0;
  if (*(gh_ushort *)(DAT_003af2b8 + 0x1e) < *(gh_ushort *)(DAT_003af2b8 + 0x12)) {
    m_statetab._16_4_ = 0;
    m_statetab._88_4_ = 3;
    m_statetab._68_4_ = 0xffffffff;
    m_statetab._140_4_ = 0xffffffff;
  }
  else {
    m_statetab._16_4_ = 0xffffffff;
    m_statetab._88_4_ = 0xffffffff;
    m_statetab._68_4_ = 2;
    m_statetab._140_4_ = 5;
  }
joined_r0x0002eb88:
  if (DAT_003af2b8 == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af2b8,"game.raw");
  }
  iVar6 = 0;
  memcpy(DAT_003af29c,(void *)((int)DAT_003af2b8 + *DAT_003af2b8),
         (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 6) * (gh_uint)*(gh_ushort *)(DAT_003af2b8 + 1) * 2);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8,4);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8,7);
  local_c8 = DAT_003af828;
  local_b8 = DAT_003af820;
  local_b4 = DAT_003af824;
  local_b0 = DAT_003af820 + DAT_003af828;
  local_c0 = DAT_003af828 << 1;
  local_c4 = DAT_003af82c;
  local_ac = DAT_003af824 + DAT_003af82c;
  local_bc = DAT_003af29c;
  local_d4 = bimapFilebuffer;
  local_a8 = DAT_003af2a0 << 1;
  local_d0 = 0;
  local_cc = 0;
  blockcopy(&local_bc,&local_d4);
  do {
    while( true ) {
      uVar1 = GetWorkPath();
      iVar2 = gameType();
      sprintf(acStack_8c,"%sstates/%s/%s.sv%d",uVar1,*(gh_u4 *)(ArchivePath + iVar2 * 4),
              RomName,iVar6);
      iVar2 = access(acStack_8c,0);
      if (iVar2 == 0) break;
      local_a4[iVar6] = 0;
LAB_0002ec70:
      iVar6 = iVar6 + 1;
      if (iVar6 == 6) goto LAB_0002ee58;
    }
    local_a4[iVar6] = 1;
    __stream = fopen(acStack_8c,"rb");
    if (__stream == (FILE *)0x0) goto LAB_0002ec70;
    fseek(__stream,0,2);
    lVar3 = ftell(__stream);
    fseek(__stream,0,0);
    fread(&local_dc,1,4,__stream);
    __size = lVar3 - local_dc;
    __ptr = malloc(__size);
    local_d8 = DAT_003af82c * DAT_003af828 * 2;
    __ptr_00 = malloc(local_d8);
    fseek(__stream,local_dc,1);
    fread(__ptr,1,__size,__stream);
    fclose(__stream);
    uncompress(__ptr_00,&local_d8,__ptr,__size);
    local_c8 = DAT_003af828;
    local_b4 = (iVar6 / 3) * 0xa8 + *(gh_ushort *)((int)DAT_003af2b8 + 0x7a) + 4;
    local_b8 = (iVar6 % 3) * 0xa8 + *(gh_ushort *)(DAT_003af2b8 + 0x1e) + 4;
    local_bc = DAT_003af29c;
    local_a8 = DAT_003af2a0 << 1;
    local_c4 = DAT_003af82c;
    iVar6 = iVar6 + 1;
    local_c0 = DAT_003af828 << 1;
    local_b0 = local_b8 + 0xa0;
    local_ac = local_b4 + 0xa0;
    local_d4 = __ptr_00;
    local_d0 = iVar2;
    local_cc = iVar2;
    blockadaptive(&local_bc,&local_d4);
    free(__ptr);
    free(__ptr_00);
  } while (iVar6 != 6);
LAB_0002ee58:
  iVar6 = -1;
  DAT_003af27c = 0xffffffff;
  bVar5 = false;
  OutRect._16_4_ = 0x500;
  OutRect._20_4_ = 0x2d0;
  OutRect._8_4_ = 0;
  OutRect._12_4_ = 0;
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  do {
    uVar4 = mui_ReadJoystick();
    if (uVar4 == 0x40) {
      if (!bVar5) break;
      iVar6 = iVar6 * 0x18;
      draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + *(int *)(m_statetab + iVar6),
                        (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                        *(int *)(m_statetab + iVar6 + 4),0);
      iVar6 = *(int *)(m_statetab + iVar6 + 0xc);
LAB_0002f0a4:
      draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + *(int *)(m_statetab + iVar6 * 0x18)
                        ,(gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                         *(int *)(m_statetab + iVar6 * 0x18 + 4),0xffff);
      SoundPlay(1,mui_Effect0);
LAB_0002f03c:
      DAT_003af274 = 1;
LAB_0002f044:
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      DAT_003af274 = 0;
    }
    else {
      if (uVar4 < 0x41) {
        if (uVar4 == 0x10) {
          if (!bVar5) {
            return 1;
          }
          iVar6 = iVar6 * 0x18;
          draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + *(int *)(m_statetab + iVar6),
                            (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                            *(int *)(m_statetab + iVar6 + 4),0);
          iVar6 = *(int *)(m_statetab + iVar6 + 8);
          goto LAB_0002f0a4;
        }
        if (uVar4 == 0x20) {
          if (!bVar5) {
            if ((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) <= (gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0xe))
            goto LAB_0002ef08;
            DAT_003af27c = 0xffffffff;
            draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + m_statetab._0_4_,
                              (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) + m_statetab._4_4_,0xffff)
            ;
            bVar5 = true;
            SoundPlay(1,mui_Effect1);
            iVar6 = 0;
            goto LAB_0002f03c;
          }
          iVar6 = iVar6 * 0x18;
          draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + *(int *)(m_statetab + iVar6),
                            (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                            *(int *)(m_statetab + iVar6 + 4),0);
          iVar6 = *(int *)(m_statetab + iVar6 + 0x14);
          goto joined_r0x0002f22c;
        }
      }
      else {
        if (uVar4 == 0x80) {
          if (bVar5) {
            iVar6 = iVar6 * 0x18;
            draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + *(int *)(m_statetab + iVar6),
                              (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                              *(int *)(m_statetab + iVar6 + 4),0);
            iVar6 = *(int *)(m_statetab + iVar6 + 0x10);
joined_r0x0002f22c:
            if (iVar6 < 0) {
              bVar5 = false;
              SoundPlay(1,mui_Effect1);
            }
            else {
              draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) +
                                *(int *)(m_statetab + iVar6 * 0x18),
                                (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                                *(int *)(m_statetab + iVar6 * 0x18 + 4),0xffff);
              SoundPlay(1,mui_Effect1);
            }
          }
          else {
            if ((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0xe) <= (gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e)) {
LAB_0002ef08:
              bVar5 = false;
              SoundPlay(1,mui_Effect1);
              goto LAB_0002ef1c;
            }
            iVar6 = 2;
            DAT_003af27c = 0xffffffff;
            draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + m_statetab._48_4_,
                              (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) + m_statetab._52_4_,0xffff
                             );
            bVar5 = true;
            SoundPlay(1,mui_Effect1);
          }
          goto LAB_0002f03c;
        }
        if (((uVar4 == 0x2000) && (bVar5)) && (local_a4[iVar6] == 1)) {
          uVar1 = GetWorkPath();
          iVar2 = gameType();
          sprintf(acStack_8c,"%sstates/%s/%s.sv%d",uVar1,*(gh_u4 *)(ArchivePath + iVar2 * 4),
                  RomName,iVar6);
          iVar2 = retro_load_state(acStack_8c);
          if (iVar2 != 0) {
            pause_ret = 0;
            return 0;
          }
        }
      }
LAB_0002ef1c:
      if (DAT_003af274 != 0) goto LAB_0002f044;
    }
    mui_WaitNMI();
  } while( true );
  iVar6 = mui_video_setting();
  if (iVar6 == 0) {
    return 0;
  }
  goto joined_r0x0002eb88;
}
