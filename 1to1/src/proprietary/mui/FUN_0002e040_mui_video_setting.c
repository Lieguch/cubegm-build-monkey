/* ============================================================
 * mui_video_setting   @ 0x0002e040   size=2552B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 mui_video_setting(void)

{
  gh_uint uVar1;
  int iVar2;
  gh_u4 uVar3;
  gh_u4 uVar4;
  gh_u4 uVar5;
  gh_uint uVar6;
  gh_u4 *puVar7;
  gh_uint uVar8;
  gh_uint uVar9;
  gh_uint uVar10;
  const char *pcVar11;
  const char *pcVar12;
  /* R179 根修：-0xb8..-0x8c 是 blockcopy(param_2,param_1) 的 12 个连续 int 参数槽
   * （与 joystick 同构）。数组化让 &blk[6] 逃逸覆盖 param_1、&blk[0] 覆盖 param_2，
   * -Os 不再消除 af820/24/28/2c 写入。 */
  int blk[12];   /* [0..5]=param_2(local_b8..a4)  [6..11]=param_1(local_a0..8c) */
  int local_88 [4];
  int local_78;
  int local_74;
  int local_70;
  int local_6c;
  /* 证据（第 157 轮）：工厂 0x2e0848..0x2e0888 是一张物理相邻、16B 对齐的菜单表
     「"FULL SCREEN"(16B) + pad(16B) + "4:3"(16B) + pad(16B)」，终止项 01 紧随其后
     （工厂 .rodata 逐字节，见 build/_r157_probe.py）。Ghidra 把它还原成「散装字符串
     字面量 + 指针比较扫描循环」，依赖 .rodata 物理相邻这一 GCC 6.2 的排布产物；
     重建编译器的字符串池合并把 "FULL SCREEN" 与终止项拉开了 ~9.6KB（三份重建 ELF
     实测："FULL SCREEN" 落在公共字符串池、紧邻 retro_set_audio_sample_batch，"4:3"
     根本不在相邻位置）⇒ vst1.32 循环按 16B 步进把本应 64B 的写入堆成数千字节、
     写爆栈（第 156 轮 diff_exec 死亡点 W!@0x7e040000，202 条指令、无外部调用、
     无 data-write ⇒ 死在循环内、连循环后第一条 DAT_003af27c=0 都没执行）。
     修法：① 把表显式化成 const 数组（物理相邻由语言保证，终止用数组边界而非
     指针比较）；② 把 Ghidra 拆成两个局部（local_68[8] / auStack_48[36]）的 64B
     菜单文本缓冲区合并为一个对象，64B 拷贝落在同一对象内（同族于铁律 45/75）。 */
  static const char _video_menu_tbl[4][16] = { "FULL SCREEN", "", "4:3", "" };
  struct { gh_u4 item0[8]; gh_u1 item1[36]; } _menu;
  
  puVar7 = _menu.item0;
  pcVar11 = &_video_menu_tbl[0][0];
  do {
    pcVar12 = pcVar11 + 0x10;
    uVar3 = *(gh_u4 *)(pcVar11 + 4);
    uVar4 = *(gh_u4 *)(pcVar11 + 8);
    uVar5 = *(gh_u4 *)(pcVar11 + 0xc);
    *puVar7 = *(gh_u4 *)pcVar11;
    puVar7[1] = uVar3;
    puVar7[2] = uVar4;
    puVar7[3] = uVar5;
    puVar7 = puVar7 + 4;
    pcVar11 = pcVar12;
  } while (pcVar12 != &_video_menu_tbl[4][0]);
  DAT_003af27c = 0;
  /* ★ 第 158 轮取证：工厂 0x2e0b0-0x2e0c0 先加载 PTR_DisplayZoomFlag_003b1e5c
     （.bss 指针，沙箱中为 0），再解引用取实际值。直接访问 DisplayZoomFlag
     会跳过这次解引用，导致 O 侧不在此处死亡而继续走到 m_ui+1484。
     恢复指针间接寻址以 1:1 匹配工厂指令序列。 */
  uVar10 = *(gh_uint *)PTR_DisplayZoomFlag_003b1e5c >> 8;
  while ((DisplayThumbnailflag & 8) != 0) {
    usleep(1000);
  }
  local_88[1] = DAT_003af834;
  local_88[0] = DAT_003af830;
  local_74 = DAT_003af83c + 10 + DAT_003af834;
  local_6c = local_74 + DAT_003af83c;
  local_88[3] = DAT_003af83c + DAT_003af834;
  local_88[2] = DAT_003af830 + DAT_003af838;
  DisplayThumbnailflag = 1;
  local_78 = local_88[0];
  local_70 = local_88[2];
LAB_0002e19c:
  if (DAT_003af2b8 == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af2b8,"game.raw");
  }
  memcpy(DAT_003af29c,(void *)((int)DAT_003af2b8 + *DAT_003af2b8),
         (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 6) * (gh_uint)*(gh_ushort *)(DAT_003af2b8 + 1) * 2);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8,5);
  /* R179 根修：12 槽数组化，槽名→blk 索引（见声明处注释） */
  blk[4]  = DAT_003af82c;                  /* local_a8 = param_2[4] */
  blk[7]  = DAT_003af820;                  /* local_9c = param_1[1] */
  blk[3]  = DAT_003af828;                  /* local_ac = param_2[3] */
  blk[8]  = DAT_003af824;                  /* local_98 = param_1[2] */
  blk[9]  = DAT_003af820 + DAT_003af828;   /* local_94 = param_1[3] */
  blk[10] = DAT_003af824 + DAT_003af82c;   /* local_90 = param_1[4] */
  blk[5]  = DAT_003af828 << 1;             /* local_a4 = param_2[5] */
  blk[0]  = (int)bimapFilebuffer;          /* local_b8 = param_2[0]（源基址）*/
  blk[6]  = (int)DAT_003af29c;             /* local_a0 = param_1[0]（目标基址）*/
  blk[11] = DAT_003af2a0 << 1;             /* local_8c = param_1[5] */
  blk[1]  = 0;                             /* local_b4 = param_2[1] */
  blk[2]  = 0;                             /* local_b0 = param_2[2] */
  blockcopy(&blk[6],&blk[0]);
  OutRect._8_4_ = 0;
  OutRect._16_4_ = 0x500;
  OutRect._12_4_ = 0;
  OutRect._20_4_ = 0x2d0;
  mui_outputxy_t(DAT_003af29c,local_88[0] + 8,local_88[1] + 6,(gh_u1)DAT_003af840,DAT_003af844,
                 (gh_byte *)(_menu.item0));
  if (uVar10 == 0) {
    mui_outputxy_t(DAT_003af29c,local_88[0] + 0x120,local_88[1] + -10,(gh_u1)DAT_003af71c,
                   DAT_003af718,(gh_byte *)&DAT_003af70f);
    mui_outputxy_t(DAT_003af29c,local_78 + 8,local_74 + 6,(gh_u1)DAT_003af840,DAT_003af844,
                   _menu.item1);
    mui_outputxy_t(DAT_003af29c,local_78 + 0x120,local_74 + -6,(gh_u1)DAT_003af71c,DAT_003af718
                   ,(gh_byte *)&DAT_003af708);
  }
  else {
    mui_outputxy_t(DAT_003af29c,local_88[0] + 0x120,local_88[1] + -6,(gh_u1)DAT_003af71c,
                   DAT_003af718,(gh_byte *)&DAT_003af708);
    mui_outputxy_t(DAT_003af29c,local_78 + 8,local_74 + 6,(gh_u1)DAT_003af840,DAT_003af844,
                   _menu.item1);
    mui_outputxy_t(DAT_003af29c,local_78 + 0x120,local_74 + -10,(gh_u1)DAT_003af71c,
                   DAT_003af718,(gh_byte *)&DAT_003af70f);
  }
  uVar8 = 0;
  uVar6 = 0xffffffff;
  DAT_003af27c = 0xffffffff;
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  do {
    uVar1 = mui_ReadJoystick();
    uVar9 = DAT_003af27c;
    if (uVar1 == 0x40) {
      if (uVar8 == 0) break;
      if ((int)uVar6 < 1) {
        uVar6 = uVar6 + 1;
      }
      SoundPlay(1,(int *)mui_Effect0);
      if (uVar6 == DAT_003af27c) goto LAB_0002e5ac;
LAB_0002e400:
      if (-1 < (int)DAT_003af27c) {
        UnDrawSelectBar(local_88 + DAT_003af27c * 4,(int)DAT_003af2b8,0);
        mui_outputxy_t(DAT_003af29c,local_88[DAT_003af27c * 4] + 8,
                       local_88[DAT_003af27c * 4 + 1] + 6,(gh_u1)DAT_003af840,DAT_003af844,
                       (gh_byte *)(_menu.item0 + DAT_003af27c * 8));
        if (DAT_003af27c == uVar10) {
          mui_outputxy_t(DAT_003af29c,local_88[uVar10 * 4] + 0x120,local_88[uVar10 * 4 + 1] + -10,
                         (gh_u1)DAT_003af71c,DAT_003af718,(gh_byte *)&DAT_003af70f);
        }
        else {
          mui_outputxy_t(DAT_003af29c,local_88[DAT_003af27c * 4] + 0x120,
                         local_88[DAT_003af27c * 4 + 1] + -6,(gh_u1)DAT_003af71c,DAT_003af718,
                         (gh_byte *)&DAT_003af708);
        }
      }
      uVar9 = uVar6;
      if (-1 < (int)uVar6) {
        DrawSelectBar(local_88 + uVar6 * 4);
        mui_outputxy_t(DAT_003af29c,local_88[uVar6 * 4] + 8,local_88[uVar6 * 4 + 1] + 6,
                       (gh_u1)DAT_003af840,DAT_003af844,(gh_byte *)(_menu.item0 + uVar6 * 8));
        if (uVar6 == uVar10) {
          mui_outputxy_t(DAT_003af29c,local_88[uVar6 * 4] + 0x120,local_88[uVar6 * 4 + 1] + -10,
                         (gh_u1)DAT_003af71c,DAT_003af718,(gh_byte *)&DAT_003af70f);
        }
        else {
          mui_outputxy_t(DAT_003af29c,local_88[uVar6 * 4] + 0x120,local_88[uVar6 * 4 + 1] + -6,
                         (gh_u1)DAT_003af71c,DAT_003af718,(gh_byte *)&DAT_003af708);
        }
      }
LAB_0002e534:
      DAT_003af27c = uVar9;
      DAT_003af274 = 1;
LAB_0002e544:
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      DAT_003af274 = 0;
    }
    else {
      if (0x40 < uVar1) {
        if (uVar1 == 0x80) {
          uVar9 = uVar8;
          if (uVar8 == 0) {
            if (DAT_003af830 < (int)(gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x16)) {
              uVar9 = 1;
              DAT_003af27c = 0xffffffff;
              uVar6 = uVar8;
            }
          }
          else if ((int)(gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x16) < DAT_003af830) {
            uVar6 = 0xffffffff;
            uVar9 = 0;
          }
          SoundPlay(1,(int *)mui_Effect1);
          uVar8 = uVar9;
          if (uVar6 == DAT_003af27c) goto LAB_0002e5ac;
          goto LAB_0002e400;
        }
        if ((uVar1 != 0x2000) || (uVar8 == 0)) goto joined_r0x0002e5a8;
        UnDrawSelectBar(local_88,(int)DAT_003af2b8,0);
        UnDrawSelectBar(local_88 + 4,(int)DAT_003af2b8,0);
        uVar10 = (gh_uint)(uVar9 == 0);
        DrawSelectBar(local_88 + DAT_003af27c * 4);
        mui_outputxy_t(DAT_003af29c,local_88[0] + 8,local_88[1] + 6,(gh_u1)DAT_003af840,
                       DAT_003af844,(gh_byte *)(_menu.item0));
        if (uVar9 == 0) {
          mui_outputxy_t(DAT_003af29c,local_88[0] + 0x120,local_88[1] + -6,(gh_u1)DAT_003af71c,
                         DAT_003af718,(gh_byte *)&DAT_003af708);
          mui_outputxy_t(DAT_003af29c,local_78 + 8,local_74 + 6,(gh_u1)DAT_003af840,
                         DAT_003af844,_menu.item1);
          mui_outputxy_t(DAT_003af29c,local_78 + 0x120,local_74 + -10,(gh_u1)DAT_003af71c,
                         DAT_003af718,(gh_byte *)&DAT_003af70f);
        }
        else {
          mui_outputxy_t(DAT_003af29c,local_88[0] + 0x120,local_88[1] + -10,(gh_u1)DAT_003af71c
                         ,DAT_003af718,(gh_byte *)&DAT_003af70f);
          mui_outputxy_t(DAT_003af29c,local_78 + 8,local_74 + 6,(gh_u1)DAT_003af840,
                         DAT_003af844,_menu.item1);
          mui_outputxy_t(DAT_003af29c,local_78 + 0x120,local_74 + -6,(gh_u1)DAT_003af71c,
                         DAT_003af718,(gh_byte *)&DAT_003af708);
        }
        RARCH_LOG("VideoFull:%d\n",uVar10);
        uVar9 = DAT_003af27c;
        if (uVar6 != DAT_003af27c) goto LAB_0002e400;
        goto LAB_0002e534;
      }
      if (uVar1 == 0x10) {
        if (uVar8 == 0) {
          if (uVar10 != DisplayZoomFlag >> 8) {
            if (uVar10 == 0) {
              DisplayZoomFlag = DisplayZoomFlag & 0xfeff;
            }
            else {
              DisplayZoomFlag = DisplayZoomFlag | 0x100;
            }
            ChangeSeting = 1;
            return 1;
          }
          return 1;
        }
        if (uVar6 != 0) {
          uVar6 = uVar6 - 1;
        }
        SoundPlay(1,(int *)mui_Effect0);
        if (uVar6 != DAT_003af27c) goto LAB_0002e400;
      }
      else if (uVar1 == 0x20) {
        if (uVar8 == 0) {
          if ((int)(gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x16) < DAT_003af830) {
            DAT_003af27c = 0xffffffff;
            uVar6 = uVar8;
            uVar8 = 1;
          }
        }
        else if (DAT_003af830 < (int)(gh_uint)*(gh_ushort *)(DAT_003af2b8 + 0x16)) {
          uVar8 = 0;
          uVar6 = 0xffffffff;
        }
        SoundPlay(1,(int *)mui_Effect1);
        if (uVar6 != DAT_003af27c) goto LAB_0002e400;
      }
      else {
joined_r0x0002e5a8:
        if (uVar6 != DAT_003af27c) goto LAB_0002e400;
      }
LAB_0002e5ac:
      if (DAT_003af274 != 0) goto LAB_0002e544;
    }
    mui_WaitNMI();
  } while( true );
  iVar2 = mui_joystick_setting();
  if (iVar2 == 0) {
    if (uVar10 != DisplayZoomFlag >> 8) {
      if (uVar10 == 0) {
        DisplayZoomFlag = DisplayZoomFlag & 0xfeff;
      }
      else {
        DisplayZoomFlag = DisplayZoomFlag | 0x100;
      }
      ChangeSeting = 1;
    }
    return 0;
  }
  goto LAB_0002e19c;
}
