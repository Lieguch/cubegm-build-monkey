/* ============================================================
 * mui_save_state   @ 0x0002f320   size=2704B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 mui_save_state(void)

{
  gh_u4 uVar1;
  int iVar2;
  FILE *pFVar3;
  long lVar4;
  void *pvVar5;
  void *__ptr;
  gh_uint uVar6;
  bool bVar7;
  int *piVar8;
  size_t __size;
  int iVar9;
  int local_dc;
  size_t local_d8;
  int local_d4 [6];
  void *local_bc;
  int local_b8;
  int local_b4;
  int local_b0;
  int local_ac;
  int local_a8;
  void *local_a4;
  gh_uint local_a0;
  gh_uint local_9c;
  gh_uint local_98;
  gh_uint local_94;
  int local_90;
  char acStack_8c [104];
  
  DAT_003af27c = 0;
  if (*(gh_ushort *)(DAT_003af2b8 + 0x1e) < *(gh_ushort *)(DAT_003af2b8 + 0xe)) {
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
joined_r0x0002f3e8:
  piVar8 = DAT_003af2b8;
  if (bimapFilebuffer == (void *)0x0) {
    bimapFilebuffer = malloc(DAT_003af828 * DAT_003af828 * 2);
  }
  if (piVar8 == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af2b8,"game.raw");
    piVar8 = DAT_003af2b8;
  }
  iVar9 = 0;
  memcpy(DAT_003af29c,(void *)((int)piVar8 + *piVar8),
         (gh_uint)*(gh_ushort *)((int)piVar8 + 6) * (gh_uint)*(gh_ushort *)(piVar8 + 1) * 2);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8,3);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8,7);
  local_b0 = DAT_003af828;
  local_a0 = DAT_003af820;
  local_9c = DAT_003af824;
  local_98 = DAT_003af820 + DAT_003af828;
  local_a8 = DAT_003af828 << 1;
  local_ac = DAT_003af82c;
  local_94 = DAT_003af824 + DAT_003af82c;
  local_a4 = DAT_003af29c;
  local_bc = bimapFilebuffer;
  local_90 = DAT_003af2a0 << 1;
  local_b8 = 0;
  local_b4 = 0;
  blockcopy(&local_a4,&local_bc);
  do {
    while( true ) {
      uVar1 = GetWorkPath();
      iVar2 = gameType();
      sprintf(acStack_8c,"%sstates/%s/%s.sv%d",uVar1,*(gh_u4 *)(ArchivePath + iVar2 * 4),
              RomName,iVar9);
      iVar2 = access(acStack_8c,0);
      if (iVar2 == 0) break;
      local_d4[iVar9] = 0;
LAB_0002f4e0:
      iVar9 = iVar9 + 1;
      if (iVar9 == 6) goto LAB_0002f6cc;
    }
    local_d4[iVar9] = 1;
    pFVar3 = fopen(acStack_8c,"rb");
    if (pFVar3 == (FILE *)0x0) goto LAB_0002f4e0;
    fseek(pFVar3,0,2);
    lVar4 = ftell(pFVar3);
    fseek(pFVar3,0,0);
    fread(&local_dc,1,4,pFVar3);
    __size = lVar4 - local_dc;
    pvVar5 = malloc(__size);
    local_d8 = DAT_003af82c * DAT_003af828 * 2;
    __ptr = malloc(local_d8);
    fseek(pFVar3,local_dc,1);
    fread(pvVar5,1,__size,pFVar3);
    fclose(pFVar3);
    uncompress(__ptr,&local_d8,pvVar5,__size);
    local_b0 = DAT_003af828;
    local_9c = (iVar9 / 3) * 0xa8 + *(gh_ushort *)((int)DAT_003af2b8 + 0x7a) + 4;
    local_a4 = DAT_003af29c;
    local_a0 = (iVar9 % 3) * 0xa8 + *(gh_ushort *)(DAT_003af2b8 + 0x1e) + 4;
    local_ac = DAT_003af82c;
    local_a8 = DAT_003af828 << 1;
    local_90 = DAT_003af2a0 << 1;
    iVar9 = iVar9 + 1;
    local_98 = local_a0 + 0xa0;
    local_94 = local_9c + 0xa0;
    local_bc = __ptr;
    local_b8 = iVar2;
    local_b4 = iVar2;
    blockadaptive(&local_a4,&local_bc);
    free(pvVar5);
    free(__ptr);
  } while (iVar9 != 6);
LAB_0002f6cc:
  iVar9 = -1;
  DAT_003af27c = 0xffffffff;
  bVar7 = false;
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
    uVar6 = mui_ReadJoystick();
    if (uVar6 == 0x40) {
      if (!bVar7) break;
      iVar9 = iVar9 * 0x18;
      draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + *(int *)(m_statetab + iVar9),
                        (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                        *(int *)(m_statetab + iVar9 + 4),0);
      iVar9 = *(int *)(m_statetab + iVar9 + 0xc);
LAB_0002fb44:
      draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + *(int *)(m_statetab + iVar9 * 0x18)
                        ,(gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                         *(int *)(m_statetab + iVar9 * 0x18 + 4),0xffff);
      SoundPlay(1,mui_Effect0);
LAB_0002fad8:
      DAT_003af274 = 1;
LAB_0002fae0:
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      DAT_003af274 = 0;
    }
    else {
      if (uVar6 < 0x41) {
        if (uVar6 == 0x10) {
          if (!bVar7) {
            return 1;
          }
          iVar9 = iVar9 * 0x18;
          draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + *(int *)(m_statetab + iVar9),
                            (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                            *(int *)(m_statetab + iVar9 + 4),0);
          iVar9 = *(int *)(m_statetab + iVar9 + 8);
          goto LAB_0002fb44;
        }
        if (uVar6 == 0x20) {
          if (!bVar7) {
            if ((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) <= (gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0xe))
            goto LAB_0002f780;
            DAT_003af27c = 0xffffffff;
            draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + m_statetab._0_4_,
                              (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) + m_statetab._4_4_,0xffff)
            ;
            bVar7 = true;
            SoundPlay(1,mui_Effect1);
            iVar9 = 0;
            goto LAB_0002fad8;
          }
          iVar9 = iVar9 * 0x18;
          draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + *(int *)(m_statetab + iVar9),
                            (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                            *(int *)(m_statetab + iVar9 + 4),0);
          iVar9 = *(int *)(m_statetab + iVar9 + 0x14);
          goto joined_r0x0002fcd4;
        }
      }
      else {
        if (uVar6 == 0x80) {
          if (bVar7) {
            iVar9 = iVar9 * 0x18;
            draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + *(int *)(m_statetab + iVar9),
                              (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                              *(int *)(m_statetab + iVar9 + 4),0);
            iVar9 = *(int *)(m_statetab + iVar9 + 0x10);
joined_r0x0002fcd4:
            if (iVar9 < 0) {
              bVar7 = false;
              SoundPlay(1,mui_Effect1);
            }
            else {
              draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) +
                                *(int *)(m_statetab + iVar9 * 0x18),
                                (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) +
                                *(int *)(m_statetab + iVar9 * 0x18 + 4),0xffff);
              SoundPlay(1,mui_Effect1);
            }
          }
          else {
            if ((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0xe) <= (gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e)) {
LAB_0002f780:
              bVar7 = false;
              SoundPlay(1,mui_Effect1);
              goto LAB_0002f794;
            }
            iVar9 = 2;
            DAT_003af27c = 0xffffffff;
            draw_state_select((gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x1e) + m_statetab._48_4_,
                              (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x7a) + m_statetab._52_4_,0xffff
                             );
            bVar7 = true;
            SoundPlay(1,mui_Effect1);
          }
          goto LAB_0002fad8;
        }
        if ((uVar6 == 0x2000) && (bVar7)) {
          if (local_d4[iVar9] != 0) {
            local_a0 = (gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x26);
            local_90 = DAT_003af2a0 << 1;
            local_a4 = (void *)((int)DAT_003af2b8 + DAT_003af2b8[0x24]);
            local_9c = (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x9a);
            local_98 = (gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x27);
            local_94 = (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 0x9e);
            popwindows(&local_a4);
            mui_ReadJoystick();
            diff_prev = 0;
            m_time0 = GetTicks();
            while (iVar2 = mui_ReadJoystick(), iVar2 != 0x2000) {
              if (iVar2 == 0x4000) {
                popoffwindows(&local_a4);
                goto LAB_0002f794;
              }
              mui_WaitNMI();
            }
            popoffwindows(&local_a4);
          }
          uVar1 = GetWorkPath();
          sprintf(acStack_8c,"%sstates",uVar1);
          iVar2 = access(acStack_8c,0);
          if (iVar2 != 0) {
            mkdir(acStack_8c,0x1ed);
          }
          uVar1 = GetWorkPath();
          iVar2 = gameType();
          sprintf(acStack_8c,"%sstates/%s",uVar1,*(gh_u4 *)(ArchivePath + iVar2 * 4));
          iVar2 = access(acStack_8c,0);
          if (iVar2 != 0) {
            mkdir(acStack_8c,0x1ed);
          }
          uVar1 = GetWorkPath();
          iVar2 = gameType();
          sprintf(acStack_8c,"%sstates/%s/%s.sv%d",uVar1,*(gh_u4 *)(ArchivePath + iVar2 * 4),
                  RomName,iVar9);
          iVar2 = retro_save_state(acStack_8c);
          if (iVar2 != 0) {
            pFVar3 = fopen(acStack_8c,"ab");
            if (pFVar3 != (FILE *)0x0) {
              fseek(pFVar3,0,2);
              local_d8 = 0x25800;
              pvVar5 = malloc(0x25800);
              compress(pvVar5,&local_d8,bimapFilebuffer,0x25800);
              fwrite(pvVar5,1,local_d8,pFVar3);
              fflush(pFVar3);
              iVar2 = fileno(pFVar3);
              fsync(iVar2);
              fclose(pFVar3);
              free(pvVar5);
              local_bc = bimapFilebuffer;
              local_b0 = DAT_003af828;
              local_a4 = DAT_003af29c;
              local_a0 = (iVar9 % 3) * 0xa8 + *(gh_ushort *)(DAT_003af2b8 + 0x1e) + 4;
              local_9c = (iVar9 / 3) * 0xa8 + *(gh_ushort *)((int)DAT_003af2b8 + 0x7a) + 4;
              local_ac = DAT_003af82c;
              local_90 = DAT_003af2a0 << 1;
              local_98 = local_a0 + 0xa0;
              local_a8 = DAT_003af828 << 1;
              local_94 = local_9c + 0xa0;
              local_b8 = 0;
              local_b4 = 0;
              blockadaptive(&local_a4,&local_bc);
            }
            pause_ret = 0;
            return 0;
          }
        }
      }
LAB_0002f794:
      if (DAT_003af274 != 0) goto LAB_0002fae0;
    }
    mui_WaitNMI();
  } while( true );
  iVar9 = mui_load_state();
  if (iVar9 == 0) {
    return 0;
  }
  goto joined_r0x0002f3e8;
}
