/* ============================================================
 * mui_shoucang   @ 0x00028a74   size=3600B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_shoucang(void)

{
  gh_bool bVar1;
  gh_uint uVar2;
  gh_uint uVar3;
  char *pcVar4;
  gh_u4 uVar5;
  FILE *pFVar6;
  size_t __n;
  int iVar7;
  gh_uint uVar8;
  int iVar9;
  gh_uint uVar10;
  gh_uint uVar11;
  gh_uint uVar12;
  gh_uint local_4cc;
  int local_4c0;
  pthread_t pStack_4ac;
  /* ★ R180 根修（GAP 18.04，与 R179/R180 其余 11 条同构）：
   * -0x4a8..-0x490 是 popwindows/popoffwindows 的**连续 6 个 int 参数槽**
   * （Ghidra 拆成 local_4a8/4a4/4a0/49c/498/494 六个标量，下一个就是 acStack_490）。
   * popwindows 读 param_1[0..4]，C 层 `&local_4a8` 只让**首元素**地址逃逸
   * ⇒ 对其余 5 个标量的索引访问是 UB ⇒ `-Os` 判死存储并**整段删除**。
   * 实测铁证（云机 arm-linux-gnueabihf-gcc 14.2）：
   *   -Os：`add r0, sp, #20` 后只有 `str r3, [sp, #20]` **一条**存储
   *        ⇒ popwindows 读到的 x/y/w/h/stride 五个字段全是栈垃圾。
   * 集合级 Δ 同样放行：这些槽都引用 DAT_003af28c/DAT_003af2a0，符号在场 ⇒ Δ=[]。
   * 数组化后地址逃逸覆盖整段，-Os 不再消除任何一个槽。
   * 回退：还原为 6 个标量声明 + `popwindows(&local_4a8)` 即可。
   * 注意：本文件的 `local_32c`（DAT_003b2320）是 R179 已定性的**真·合法 DCE**
   *       （工厂反汇编该槽只 str 一次、无 ldr 读回），**不要**动它。 */
  int blk[6];
  char acStack_490 [100];
  char acStack_42c [256];
  gh_u4 local_32c;
  char acStack_128 [260];
  
  local_4c0 = 0;
  local_4cc = 0;
  bVar1 = false;
  uVar10 = (m_menulog_blob)._320_4_;
  uVar11 = 0;
  uVar12 = (m_menulog_blob)._316_4_;
  DAT_003af278 = (m_menulog_blob)._316_4_;
  DAT_003af27c = (m_menulog_blob)._320_4_;
  (m_menulog_blob)._0_4_ = DAT_003af26c;
joined_r0x00028b18:
  if (DAT_003af2b4 == (gh_u1 *)0x0) {
    uVar5 = (gh_u4)GetWorkPath();
    sprintf(acStack_490,"%s/favorites.lst",uVar5);
    pFVar6 = fopen(acStack_490,"rb");
    if (pFVar6 == (FILE *)0x0) {
      pFVar6 = fopen(acStack_490,"w+b");
      fputc(0,pFVar6);
      fflush(pFVar6);
      iVar7 = fileno(pFVar6);
      fsync(iVar7);
      fclose(pFVar6);
      DAT_003af2b4 = malloc(1);
      *DAT_003af2b4 = 0;
    }
    else {
      fseek(pFVar6,0,2);
      __n = ftell(pFVar6);
      DAT_003af2b4 = malloc(__n + 1);
      fseek(pFVar6,0,0);
      fread(DAT_003af2b4,1,__n,pFVar6);
      DAT_003af2b4[__n] = 0;
      fclose(pFVar6);
    }
  }
  if (DAT_003af28c == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af28c,"menu.raw");
  }
  memcpy(DAT_003af29c,(void *)((int)DAT_003af28c + *DAT_003af28c),
         (gh_uint)*(gh_ushort *)((int)DAT_003af28c + 6) * (gh_uint)*(gh_ushort *)(DAT_003af28c + 1) * 2);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 8);
  mui_fast_lsit = 0;
  uVar2 = mui_do_file_list(uVar12,DAT_003af2b4);
  mui_fast_lsit = 1;
  DAT_003af288 = uVar2;
  mui_DisplayGameSum();
  if (DAT_003af288 != 0) {
    DisplayThumbnailflag = 3;
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af27c + 1);
    uVar8 = DAT_003af27c;
    uVar11 = DAT_003af278;
    if ((0 < DAT_003af394) && (uVar2 != DAT_003af278)) {
      iVar7 = 0;
      do {
        iVar9 = iVar7 + 1;
        mui_DisplayLine_t(iVar7,uVar8,0);
        if (DAT_003af394 <= iVar9) break;
        iVar7 = iVar9;
      } while (uVar2 != uVar11 + iVar9);
    }
    uVar11 = DAT_003af284 >> 0x1f;
  }
  uVar8 = 0;
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  if ((joy_key_blob._0_4_ & 0x8000) != 0) goto LAB_00028db0;
LAB_00028c20:
  if (uVar8 == 0) {
    uVar8 = mui_ReadJoystick();
  }
  else {
    bVar1 = true;
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
    uVar8 = mui_ReadJoystick();
  }
  if (uVar8 != 0x108) goto LAB_00028c34;
  goto LAB_00028eac;
LAB_00028c34:
  if (uVar8 < 0x108) {
    if (uVar8 == 0x10) {
      if ((int)uVar10 < 1) {
        if (uVar12 != 0) {
          uVar12 = uVar12 - 1;
          uVar10 = 0;
          mui_do_file_list(uVar12,DAT_003af2b4);
        }
      }
      else {
        uVar10 = uVar10 - 1;
      }
    }
    else {
      if (uVar8 < 0x11) {
        if (uVar8 == 1) {
          uVar10 = 0;
          shoucang(&file_info_list + DAT_003af27c * 0x404);
          DAT_003af278 = 0;
          DAT_003af27c = 0;
          uVar11 = uVar10;
          uVar12 = uVar10;
          goto joined_r0x00028b18;
        }
        if (uVar8 != 8) goto LAB_00028c5c;
        goto LAB_000293d4;
      }
      if (uVar8 != 0x40) {
        if (uVar8 == 0x80) {
          if ((int)uVar12 < DAT_003af394) {
            uVar10 = 0;
            mui_do_file_list(0,DAT_003af2b4);
            uVar12 = 0;
          }
          else {
            uVar12 = uVar12 - DAT_003af394;
            mui_do_file_list(uVar12,DAT_003af2b4);
          }
        }
        else {
          if (uVar8 != 0x20) goto LAB_00028c5c;
          if ((int)(uVar12 + uVar10 + DAT_003af394) < (int)uVar2) {
            uVar12 = uVar12 + DAT_003af394;
            mui_do_file_list(uVar12,DAT_003af2b4);
          }
          else {
            uVar8 = uVar12 + DAT_003af394;
            if ((int)uVar8 < (int)uVar2) {
              uVar10 = (uVar2 - 1) - uVar8;
              mui_do_file_list(uVar8,DAT_003af2b4);
              uVar12 = uVar8;
            }
          }
        }
        SoundPlay(1,(int *)mui_Effect1);
        goto LAB_00028c5c;
      }
      if ((int)uVar10 < DAT_003af394 + -1) {
        if (((int)uVar2 < 0) || ((int)(uVar12 + uVar10) < (int)(uVar2 - 1))) {
          uVar10 = uVar10 + 1;
        }
      }
      else if ((int)(uVar12 + uVar10) < (int)(uVar2 - 1)) {
        uVar12 = uVar12 + 1;
        mui_do_file_list(uVar12,DAT_003af2b4);
      }
    }
    SoundPlay(1,(int *)mui_Effect0);
    goto LAB_00028c5c;
  }
  if (uVar8 == 0x1000) {
    while ((DisplayThumbnailflag & 8) != 0) {
      usleep(1000);
    }
    DisplayThumbnailflag = DisplayThumbnailflag & 0xfffffffd;
    iVar7 = DAT_003af394 + 0xb;
    blk[0] = (int)DAT_003af28c + DAT_003af28c[iVar7 * 4];   /* local_4a8 = param_1[0] 基址 */
    blk[1] = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar7 * 4 + 2);   /* local_4a4 = [1] x */
    blk[5] = DAT_003af2a0 << 1;                                    /* local_494 = [5] stride */
    blk[2] = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar7 * 0x10 + 10);  /* local_4a0 = [2] y */
    blk[3] = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar7 * 4 + 3);   /* local_49c = [3] w */
    blk[4] = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar7 * 0x10 + 0xe);  /* local_498 = [4] h */
    popwindows((gh_u4 *)blk);
    mui_ReadJoystick();
    diff_prev = 0;
    m_time0 = GetTicks();
    while( true ) {
      iVar7 = mui_ReadJoystick();
      if (iVar7 == 0x2000) {
        uVar5 = (gh_u4)GetWorkPath();
        sprintf(acStack_490,"%s/favorites.lst",uVar5);
        pFVar6 = fopen(acStack_490,"wb");
        if (pFVar6 != (FILE *)0x0) {
          fputc(0,pFVar6);
          fflush(pFVar6);
          iVar7 = fileno(pFVar6);
          fsync(iVar7);
          fclose(pFVar6);
        }
        if (DAT_003af2b4 != (gh_u1 *)0x0) {
          free(DAT_003af2b4);
          DAT_003af2b4 = (gh_u1 *)0x0;
        }
        uVar11 = 0;
        popoffwindows((gh_u4 *)blk);
        uVar10 = 0;
        uVar12 = 0;
        DAT_003af278 = 0;
        DisplayThumbnailflag = DisplayThumbnailflag | 2;
        DAT_003af27c = 0;
        goto joined_r0x00028b18;
      }
      if (iVar7 == 0x4000) break;
      mui_WaitNMI();
    }
    popoffwindows((gh_u4 *)blk);
    DisplayThumbnailflag = DisplayThumbnailflag | 2;
    goto LAB_00028c5c;
  }
  if (uVar8 < 0x1001) {
    if (uVar8 == 0x400) {
LAB_00029470:
      DAT_003af26c = 2;
      SoundPlay(1,(int *)mui_Effect1);
      if ((AutoRestoreKey & 8) != 0) {
        (m_menulog_blob)._316_4_ = uVar12;
        (m_menulog_blob)._320_4_ = uVar10;
        return;
      }
    }
    else {
      if (uVar8 != 0x800) goto LAB_00028c5c;
LAB_00028e28:
      DAT_003af26c = 4;
      SoundPlay(1,(int *)mui_Effect1);
      if ((AutoRestoreKey & 8) != 0) {
        (m_menulog_blob)._316_4_ = uVar12;
        (m_menulog_blob)._320_4_ = uVar10;
      }
    }
    return;
  }
  if (uVar8 == 0x2100) {
LAB_00028eac:
    DisplayThumbnailflag = DisplayThumbnailflag & 0xfe;
    while (DisplayThumbnailflag != 0) {
      usleep(1000);
    }
    pcVar4 = stpcpy(acStack_42c,root_path);
    uVar2 = DAT_003af27c;
    iVar7 = DAT_003af27c * 0x404;
    pcVar4[0] = '/';
    pcVar4[1] = '\0';
    strcpy(pcVar4 + 1,&file_info_list + iVar7);
    local_32c = (&DAT_003b2320)[uVar2 * 0x101];
    pcVar4 = (char *)SeletEmuCore(acStack_42c);
    if (pcVar4 == (char *)0x0) {
      DisplayThumbnailflag = 1;
      pthread_create(&pStack_4ac,(pthread_attr_t *)0x0,(void *(*)(void *))mui_DisplayThumbnailThread,(void *)0x0);
    }
    else {
      if ((AutoRestoreKey & 8) != 0) {
        (m_menulog_blob)._316_4_ = uVar12;
        (m_menulog_blob)._320_4_ = uVar10;
        SaveMenuLog();
      }
      strcpy(acStack_128,pcVar4);
      filelist_run_game(acStack_42c);
    }
    if (ZIP_BUF != (void *)0x0) {
      free(ZIP_BUF);
    }
    ZIP_BUF = (void *)0x0;
    ZIP_BUF_SIZE = 0;
    if ((AutoRestoreKey & 8) != 0) {
      uVar10 = (m_menulog_blob)._320_4_;
      uVar12 = (m_menulog_blob)._316_4_;
    }
    DAT_003af278 = 0;
    DAT_003af27c = 0;
  }
  else {
    if (uVar8 == 0x4000) {
      while ((DisplayThumbnailflag & 8) != 0) {
        usleep(1000);
      }
      DisplayThumbnailflag = DisplayThumbnailflag & 0xfffffffd;
      iVar7 = DAT_003af394 + 10;
      blk[0] = (int)DAT_003af28c + DAT_003af28c[iVar7 * 4];   /* local_4a8 = param_1[0] 基址 */
      blk[1] = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar7 * 4 + 2);   /* local_4a4 = [1] x */
      blk[5] = DAT_003af2a0 << 1;                                    /* local_494 = [5] stride */
      blk[2] = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar7 * 0x10 + 10);  /* local_4a0 = [2] y */
      blk[3] = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar7 * 4 + 3);   /* local_49c = [3] w */
      blk[4] = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar7 * 0x10 + 0xe);  /* local_498 = [4] h */
      popwindows((gh_u4 *)blk);
      mui_ReadJoystick();
      diff_prev = 0;
      m_time0 = GetTicks();
      while( true ) {
        iVar7 = mui_ReadJoystick();
        if (iVar7 == 0x2000) {
          uVar11 = 0;
          uVar10 = 0;
          uVar12 = 0;
          shoucang(&file_info_list + DAT_003af27c * 0x404);
          popoffwindows((gh_u4 *)blk);
          DAT_003af278 = 0;
          DAT_003af27c = 0;
          DisplayThumbnailflag = DisplayThumbnailflag | 2;
          goto joined_r0x00028b18;
        }
        if (iVar7 == 0x4000) break;
        mui_WaitNMI();
      }
      popoffwindows((gh_u4 *)blk);
      DisplayThumbnailflag = DisplayThumbnailflag | 2;
LAB_00028c5c:
      if (uVar12 == DAT_003af278) {
        if (uVar10 == DAT_003af27c) {
          local_4cc = local_4cc + 1;
          uVar3 = uVar11;
          if (((uVar11 == 0) || ((int)local_4cc < 0x65)) || (uVar3 = local_4cc & 1, uVar3 != 0)) {
            uVar8 = 0;
            uVar11 = uVar3;
            goto LAB_000290e4;
          }
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar10 + 1);
          mui_DisplayLine_t(uVar10,uVar10,local_4c0);
          if ((int)DAT_003af284 < 0x82) {
            local_4c0 = local_4c0 + -1;
          }
          else {
            local_4c0 = 0;
          }
          uVar8 = 0;
        }
        else {
          uVar8 = 0;
          local_4c0 = 0;
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af27c + 1);
          mui_DisplayLine_t(DAT_003af27c,uVar10,0);
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar10 + 1);
          mui_DisplayLine_t(uVar10,uVar10,0);
          uVar11 = DAT_003af284 >> 0x1f;
          DisplayThumbnailflag = 3;
          local_4cc = 0;
          DAT_003af27c = uVar10;
          DAT_003af288 = uVar2;
          mui_DisplayGameSum();
        }
      }
      else {
        if (0 < DAT_003af394) {
          iVar7 = 1;
          do {
            if (uVar10 != iVar7 - 1U) {
              mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar7);
            }
            bVar1 = iVar7 < DAT_003af394;
            iVar7 = iVar7 + 1;
          } while (bVar1);
        }
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar10 + 1);
        DAT_003af27c = uVar10;
        if ((0 < DAT_003af394) && (uVar12 != uVar2)) {
          iVar7 = 0;
          do {
            iVar9 = iVar7 + 1;
            mui_DisplayLine_t(iVar7,uVar10,0);
            if (DAT_003af394 <= iVar9) break;
            iVar7 = iVar9;
          } while (uVar2 != uVar12 + iVar9);
        }
        uVar8 = 0;
        local_4c0 = 0;
        local_4cc = 0;
        uVar11 = DAT_003af284 >> 0x1f;
        DisplayThumbnailflag = 3;
        DAT_003af278 = uVar12;
        DAT_003af288 = uVar2;
        mui_DisplayGameSum();
      }
LAB_00028d5c:
      DAT_003af274 = 1;
      do {
        ForceFlashCount = 0;
        dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
        DAT_003af274 = 0;
        do {
          mui_WaitNMI();
          bVar1 = false;
          if ((joy_key_blob._0_4_ & 0x8000) == 0) goto LAB_00028c20;
LAB_00028db0:
          uVar3 = mui_ReadJoystick();
          if ((uVar3 & 0xffff7fff) == 0x20) goto LAB_00028e28;
          if ((uVar3 & 0xffff7fff) == 0x80) goto LAB_00029470;
          uVar8 = uVar8 + 1;
          if ((uVar8 & 0xf) == 0) {
            if ((uVar8 & 0x10) == 0) {
              mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,
                            DAT_003af394 + 1 + DAT_003af26c);
            }
            else {
              mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,
                              DAT_003af394 + 1 + DAT_003af26c);
            }
            goto LAB_00028d5c;
          }
LAB_000290e4:
          if (bVar1) goto LAB_00028d5c;
        } while (DAT_003af274 == 0);
      } while( true );
    }
    if (uVar8 != 0x2000) goto LAB_00028c5c;
LAB_000293d4:
    if ((AutoRestoreKey & 8) != 0) {
      (m_menulog_blob)._316_4_ = uVar12;
      (m_menulog_blob)._320_4_ = uVar10;
      SaveMenuLog();
    }
    mui_run_game(&file_info_list + DAT_003af27c * 0x404);
    if ((AutoRestoreKey & 8) != 0) {
      uVar10 = (m_menulog_blob)._320_4_;
      uVar12 = (m_menulog_blob)._316_4_;
    }
    DAT_003af278 = 0;
    DAT_003af27c = 0;
  }
  goto joined_r0x00028b18;
}
