/* ============================================================
 * UpdateROM   @ 0x0000ac44   size=912B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void UpdateROM(char *param_1)

{
  FILE *__stream;
  int *__ptr;
  gh_u4 *iVar1;
  int iVar2;
  void *__s;
  gh_u4 uVar3;
  /* ★ 2026-09-29：`unaff_r7` = Ghidra 的"未被赋值寄存器 r7"。它**只在 `GetZipItemA`
   *   成功分支里被赋值**（0x4000 起步、按 `local_30` 倍增至 ≥ 需求），而在**失败分支**
   *   工厂是把**残留的 r7** 原样传给 `UpdateROMProc(NULL, r7)` —— 那个值在 C 里不可表达。
   *   原本声明为**未初始化** ⇒ 又一处 UB。此处显式置 0：成功路径逐字不变（两分支都会写），
   *   失败路径从"不可复现的残留值"变成**确定性 0**（这是**受控偏离**，已在行为尺上核对）。 */
  size_t unaff_r7 = 0;
  gh_bool bVar4;
  /* ★★ 2026-09-27 根修（UB #2，真根因）：这三个名字其实是**同一块 3 字节缓冲**的
   *   三个字节（Ghidra 把一块缓冲拆成了三个独立 `char`）。拆开之后，源码里只有
   *   `local_15c` 被 `fread` 写过，`local_15b`/`local_15a` 在编译器看来**从未被写**
   *   ⇒ 读未初始化值 = **UB** ⇒ clang 可任意取值，实测它选了"条件恒真"
   *   ⇒ **把 fread 之后的整段函数体删掉**（-O0=2660B 完整 / -Os=112B / 工厂 976B）。
   *   修法：恢复成一块真正的 3 字节缓冲并按字节读。 */
  char local_magic[3];
  /* ★★ 2026-09-27 根修（UB）：Ghidra 把这块栈缓冲写成 `[4]`（**假尺寸**），
   *   而函数体 `memset(auStack_158, 0, 0x130)` 实际写 304 字节 ⇒ **越界 = UB** ⇒
   *   clang 在任何 `-O1` 及以上**判定其后代码不可达并删掉整段**：
   *     实测 UpdateROM 尺寸 -O0=2660B（完整） / -O1=116B / -Os=112B / -O2=116B，
   *     工厂（GCC 6.2 优化） = **976B** ⇒ 闪写 + CRC 校验 + 安全区写 + sync/reboot **约 864B 被删**。
   *   证据链：`tools/ub_census.py`（编译器原话 `'memset' will always overflow; destination
   *   buffer has size 4, but size argument is 304`）+ `tools/size_coverage_gate.py`（0.115x）。
   *   修法：把声明恢复到**真实对象尺寸**（0x130），UB 消失 ⇒ 优化器无从删代码。 */
  /* ★★★ 2026-09-29 根修（UB #4，真根因；与 §0.32-D `popwindows` **同族、方向相反**）：
   *   `GetZipItemA` 把 **ZIPENTRY 整块对象**写进栈里，而 Ghidra 把这块对象**拆成了
   *   5 个互不相干的局部变量**（`auStack_158` / `auStack_154` / `local_48` /
   *   `local_30` / `local_2c`）。在 C 语言层面只有 `auStack_158` 被 `memset` 写过，
   *   其余 4 个**只读不写** ⇒ **读未初始化对象 = UB**。实测 `clang -Os` 借此把
   *   `GetZipItemA` **成功分支整段搬到函数尾部并截断**：
   *     `UpdateROM` 我方 **680B** / 工厂 **976B**（0.697）；
   *     调用序列 我方 **28 次** / 工厂 **40 次** —— 少的正是 `UnzipItem`、`puts`、
   *     `malloc(r7)`+`memset(0xff,r7)`、`spi_printf("… UPDATE TO …")` 与 `malloc(0x3fc00)`。
   *   症状同时出现在 CI 的 s27（`UpdateROM -> UpdateROMProc 未设 r1`、
   *   `UpdateROM -> DateToTmuDate 未设 r0`）与 s21 的体量覆盖门禁。
   *
   *   ★ 证据（**工厂反汇编**，`GetZipItemA` 第三参数 = 结构体基址）：
   *       `memset` 基址 = `sp+0x18`（`00ad4c: add r5,sp,#0x18` → `00ad78: bl memset`，长度 0x130）；
   *       `name`  = base + 0x04（`00adb8` 把 `sp+0x1c` 交给 `%s`）；
   *       `date`  = base + 0x30（`sp+0x48` → `DateToTmuDate` 的实参）；
   *       `size`  = base + 0x128（`00adb4: ldr r2,[sp,#0x140]`，`%08X` 的第一实参）；
   *       `crc`   = base + 0x12c（`00adb0: ldr r3,[sp,#0x144]`，`%08X` 的第二实参）。
   *
   *   ★ 修法：**恢复成一块真实对象**（宏别名把 5 个名字落回同一对象）⇒ 编译器必须假定
   *     `GetZipItemA` 会写它 ⇒ 那些读取**有定义** ⇒ UB 消失，整段逻辑得以保留。
   *     **不得用 `volatile`**：那会连带改掉访存次数与顺序，只是用另一个偏差盖住原偏差。 */
  gh_u1 zipent[0x130];                 /* GetZipItemA 填充的 ZIPENTRY（真实对象，与工厂同尺寸） */
#define auStack_158 zipent
#define auStack_154 ((char *)(zipent + 0x04))
#define local_48    (*(int *)(zipent + 0x30))
#define local_30    (*(int *)(zipent + 0x128))
#define local_2c    (*(int *)(zipent + 0x12c))
  __stream = fopen(param_1,"r+b");
  if (__stream == (FILE *)0x0) {
    printf("Load %s fail!\n",param_1);
    return;
  }
  fread(local_magic,1,3,__stream);
  fclose(__stream);
  if (((local_magic[0] != 'W') || (local_magic[1] != 'Q')) || (local_magic[2] != 'W')) {
    printf("%s format error!\n",param_1);
    return;
  }
  scr_h_size = 0x1e0;
  scr_v_size = 0x110;
  scr_data = malloc(0x3fc00);
  if (scr_data != (void *)0x0) {
    memset(scr_data,0,scr_v_size * scr_h_size * 2);
  }
  output_x = 0x14;
  output_y = 0x12;
  __ptr = malloc(0x10000);
  if (spi_id[0] == '\v') {
    uVar3 = 0x100;
  }
  else {
    uVar3 = 0x2000;
  }
  sflash_read_security_data(__ptr,uVar3);
  memset(auStack_158,0,0x130);
  iVar1 = OpenZipU(param_1,0,2);
  if (iVar1 == 0) {
    printf("%s openzip error!\n",param_1);
    __s = (void *)0x0;
  }
  else {
    iVar2 = GetZipItemA(iVar1,0,auStack_158);
    if (iVar2 == 0) {
      printf("%s,size:%08X,crc:%08X ",auStack_154,local_30,local_2c);
      printf("time:");
      DateToTmuDate(local_48);
      if (local_2c == *__ptr) {
        CloseZipU(iVar1);
        __s = (void *)0x0;
        goto LAB_0000af00;
      }
      if (local_30 < 0x4001) {
        unaff_r7 = 0x4000;
      }
      else {
        unaff_r7 = 0x4000;
        do {
          unaff_r7 = unaff_r7 * 2;
        } while ((int)unaff_r7 < local_30);
      }
      __s = malloc(unaff_r7);
      if (__s == (void *)0x0) {
        puts("Alloc memory fail!");
        return;
      }
      memset(__s,0xff,unaff_r7);
      UnzipItem(iVar1,0,__s,0,3);
      spi_printf("%08X UPDATE TO %08X\n",*__ptr,local_2c);
    }
    else {
      __s = (void *)0x0;
    }
    CloseZipU(iVar1);
    iVar1 = (gh_u4 *)UpdateROMProc((int)__s,unaff_r7);
    if (iVar1 != 0) {
      if (spi_id[0] == '\v') {
        sflash_read_security_data(__ptr + 0x40,0);
        sflash_erase_security_data(0);
      }
      else {
        sflash_erase_security_data(0x2000);
      }
      memset(__ptr,0xff,0x100);
      bVar4 = spi_id[0] == '\v';
      *__ptr = local_2c;
      __ptr[1] = local_48;
      if (bVar4) {
        sflash_write_security_data(__ptr + 0x40,0);
        sflash_write_security_data(__ptr,0x100);
      }
      else {
        sflash_write_security_data(__ptr,0x2000);
      }
      spi_printf("REBOOT...           ");
      putchar(10);
      dispFlip(scr_data,scr_h_size,scr_v_size,scr_h_size << 1);
      free(__ptr);
      sync();
                    /* WARNING: Subroutine does not return */
      reboot(0x1234567);
    }
  }
LAB_0000af00:
  scr_h_size = 0x500;
  scr_v_size = 0x2d0;
  if (scr_data != (void *)0x0) {
    free(scr_data);
  }
  if (__ptr != (int *)0x0) {
    free(__ptr);
  }
  if (__s != (void *)0x0) {
    free(__s);
  }
  return;
}

#undef auStack_158
#undef auStack_154
#undef local_48
#undef local_30
#undef local_2c
