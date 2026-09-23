/* ============================================================
 * FBA_Load   @ 0x002b6c14   size=704B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 FBA_Load(char *param_1)

{
  int iVar1;
  gh_u4 uVar2;
  gh_code *pcVar3;
  char **ppcVar4;

  /* ★★★ 2026-09-23（GAP 16.99）：工厂在栈上是一个 **10 槽指针数组**（-0x150 … -0x12c，40 B 连续）。
   *
   * Ghidra 按**类型推断**把它拆成了 10 个独立局部量（Ghidra 名 -> 槽号 / 偏移）：
   *     local_150                                  -> core_path[0]   -0x150
   *     local_14c[0..3]                            -> core_path[1..4] -0x14c…-0x140
   *     uStack_13c / 138 / 134 / 130 / 12c         -> core_path[5..9] -0x13c…-0x12c
   * 而原指令是 `ppcVar4 = &local_150; ppcVar4 = ppcVar4 + 1;` —— **跨对象步进**。
   * 在 C 里「取局部标量的地址再 +1」是**未定义行为**：GCC/clang 允许假定越界指针不被解引用，
   * 于是把后续槽的**全部写入删除**（DCE）。
   *
   * 实测（单变量：同一份源、同一 zigcc / 同一 CFLAGS，只改优化级别）：
   *     -O0  .o 的 UNDEF 里工厂数据引用 = 11 个
   *            DAT_003b012c, DAT_003b0130, 0134, 0138, 013c, 0140, 0144, 0148, 014c, 0150, DAT_002dbcb4
   *     -Os  .o 的 UNDEF 里工厂数据引用 =  2 个（只剩 DAT_003b012c 与 DAT_002dbcb4）
   *   ⇒ **9 个引用被消除** ⇒ 原厂「10 条候选 core 路径」的链退化成 1 条 ⇒ 语义发散。
   *
   * 修法：按工厂**真实结构**还原成一个数组 —— 每个槽的偏移与总字节数逐字节不变，
   * 步进因此合法，10 条路径全部保留。槽名对照保留在赋值行的行尾注释里，便于与反汇编逐条核对。
   */
  char *core_path[10];      /* [0]=local_150 [1..4]=local_14c[0..3] [5..9]=uStack_13c..uStack_12c */
  char acStack_128 [260];
  
  core_path[0] = (char *)DAT_003b012c;   /* local_150   */
  core_path[1] = (char *)DAT_003b0130;   /* local_14c[0] */
  core_path[2] = (char *)DAT_003b0134;   /* local_14c[1] */
  core_path[3] = (char *)DAT_003b0138;   /* local_14c[2] */
  ppcVar4 = core_path;                   /* 原: ppcVar4 = &local_150; */
  core_path[4] = (char *)DAT_003b013c;   /* local_14c[3] */
  core_path[5] = (char *)DAT_003b0140;   /* uStack_13c  */
  core_path[6] = (char *)DAT_003b0144;   /* uStack_138  */
  core_path[7] = (char *)DAT_003b0148;   /* uStack_134  */
  core_path[8] = (char *)DAT_003b014c;   /* uStack_130  */
  core_path[9] = (char *)DAT_003b0150;   /* uStack_12c  */
  n_input_width = 0x140;
  n_input_height = 0xf0;
  n_input_visible_width = 0x140;
  n_input_visible_height = 0xf0;
  screen_w = 0x140;
  screen_x = 0;
  strcpy(fileName,param_1);
  if (*core_path[0] != '\0') {           /* 原: if (*local_150 != '\0') */
    do {
      while( true ) {
        sprintf(acStack_128,"%s/cores/%s",work_path);
        handle_emurun = dlopen(acStack_128,2);
        if (handle_emurun != 0) break;
        uVar2 = (gh_u4)dlerror();
        RARCH_LOG("open %s fail,%s \n",acStack_128,uVar2);
        ppcVar4 = ppcVar4 + 1;
        if (**ppcVar4 == '\0') {
          return 0;
        }
      }
      _retro_is_support = (gh_code *)dlsym(handle_emurun,"retro_is_support");
      if (((_retro_is_support != (gh_code *)0x0) && (iVar1 = (*_retro_is_support)(param_1), -1 < iVar1)
          ) && (iVar1 = Load_Proc1(DAT_002dbcb4), iVar1 != 0)) {
        run_process("retro_set_progress_callback",(gh_code *)progress);
        game_blob._0_4_ = fileName;
        game_blob._4_4_ = 0;
        game_blob._8_4_ = 0;
        progress_stepcount = 0;
        pcVar3 = (gh_code *)dlsym(handle_emurun,"retro_load_game");
        if ((pcVar3 != (gh_code *)0x0) && (iVar1 = (*pcVar3)(game), iVar1 != 0)) {
          RARCH_LOG("use %s to run %s\n",acStack_128,fileName);
          Load_Proc2();
          rotation = 0;
          if (soft_rotation == 0) {
            video_driver_set_rotation(0xff00);
          }
          else if (rotation_buff != (void *)0x0) {
            free(rotation_buff);
            rotation_buff = (void *)0x0;
          }
          video_driver_set_rotation(0xff00);
          RARCH_LOG("Exit fba here \n");
          return 0;
        }
        run_process("retro_unload_game",0);
        run_process("retro_deinit",0);
      }
      RARCH_LOG("%s unsupport.\n",acStack_128);
      dlclose(handle_emurun);
      ppcVar4 = ppcVar4 + 1;
    } while (**ppcVar4 != '\0');
  }
  return 0;
}
