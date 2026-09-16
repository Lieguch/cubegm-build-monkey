/* ============================================================
 * spi_driver_init   @ 0x002c4044   size=836B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 spi_driver_init(void)

{
  gh_byte bVar1;
  gh_byte bVar2;
  gh_byte *pbVar3;
  gh_byte *pbVar4;
  gh_u4 uVar5;
  gh_uint uVar6;
  gh_byte *pbVar7;
  int iVar8;
  int iVar9;
  gh_u1 uVar10;
  gh_u4 cmd[2];  /* ★★ 原厂：命令行是**连续的 2 个字**（cmd[0]=命令，cmd[1]=参数，sfc_request 会对 cmd[1] 置 bit1）。
   *    必须写成数组：拆成两个相邻标量时，编译器可以按任意顺序摆放，`cmd[0]+4` 就可能越出这对
   *    标量、砸到帧里别的东西 —— 实测把调用者保存的 fp 打成了 fp|2，导致上层 `sub sp,fp,#28`
   *    算出错帧、`pop {…,pc}` 跳到坏地址。工厂原版是 `str lr,[sp]` + `str lr,[sp,#4]`，即帧内 8B 数组。 */
  /* ★★ 原厂这里是**同一块安全数据缓冲的前两个字**（Ghidra 把它拆成了两个独立标量）：
   *    · `sflash_read_security_data(&sb.sec[0], 0x2000)` ⇒ 把安全数据整块读进 &buf[0]；
   *    · `printf("… CRC32:%04X ", …, sb.sec[0])` ⇒ 打印 buf[0]；
   *    · `DateToTmuDate(sb.sec[1]._u32)`            ⇒ 用 buf[1] 解出 "Update time"。
   *   ⇒ 必须表达成**相邻数组**：若写成两个独立标量，编译器可以把 buf[1] 放到那次
   *     0x100 字节写入的范围之外，于是读到链上残留值 —— 实测症状就是
   *     `Update time:1980-0-0 0:0:0`（原厂） vs `…0:0:24`（重建）。
   *   ⇒ 数组保证 buf[0]/buf[1] 相邻、并被同一次写入覆盖。
   *   （证据：工厂反汇编 `str ip,[sp]`/`str ip,[sp,#4]` 之后 `strb 0x9f,[sp]`，
   *     再 `bl sfc_request(sp, 0, r5=sp+8, 3)`；buf 起点 = sp+8。） */

  /* ★★ 帧内那 0x104 字节必须表达成**一个对象**（两轮实测逼出来的结论）。 */
  /* 工厂帧的硬事实（反汇编直读，不是推断）：
   *   `push {r4,r5,r6,r7,lr}` + `sub sp, sp, #0x10C`  ⇒ 保存寄存器区在 sp+0x10C 之上；
   *   缓冲区起点 = sp+8（`add r5, sp, #8`）；
   *   `sflash_read_security_data()` 内部最终 `sfc_request(&cmd, addr, buf, 0x100)`
   *     ⇒ **一次写入 0x100 = 256 字节**，覆盖 sp+8 .. sp+0x108 —— 恰好停在保存区前 4 字节。
   *   所以 sp+8 .. sp+0x10C 这 0x104 = 260 字节在原厂里是**一整块**；
   *   Ghidra 只是把它切成了 local_118 / local_114 / local_110 / local_fc / local_f8 / local_58。
   *
   * 为什么必须是一个对象（两种错法都实测过）：
   *   ① 首两个字拆成独立标量 ⇒ 编译器可把第二个字排到写入范围外 ⇒ 读到链上残留值；
   *   ② 只把「死局部」单独声明（哪怕加空 asm 保活）⇒ 编译器把它们排到缓冲区**之前**，
   *      那 256 字节便向上冲进保存寄存器区 ⇒ `pop {…,pc}` 取到被清零的返回地址
   *      ⇒ 返回瞬间 SIGSEGV（实测：重建侧崩在 `pop {…,pc}`，比原厂早两行）。
   *   ⇒ 用一个 struct（C 保证字段顺序与相邻），256 字节写入**完全落在自己对象内**。
   *
   * 内部偏移（工厂反汇编直读）：
   *   local_110 = buf+0x08  ← `add r0, sp, #0x10`（复制循环的上界，拷 8 字节 → UniqueID）
   *   local_fc  = buf+0x1c  ← `add r2, sp, #0x27` 即 local_fc+3、`add r0, sp, #0x25` 即 local_fc+1
   *   local_f8  = buf+0x20  ← = local_fc + 4
   *   local_58  = buf+0xc0  ← 校验循环里的 `pbVar4[0xc0]`（代码中无独立引用）
   *   ★ 首版我按「相对 buf」写偏移时忘了 `dead` 已从 buf+8 起算，四个值整体偏了 ⇒
   *     复制循环多拷 8 字节（16 而非 8）、XOR 键取自错误位置。已按上表修正。 */
  struct {
      gh_u32_bytes_t sec[2];   /* buf+0x00：原 local_118（CRC32）/ local_114（Update time） */
      gh_byte buf[0xFC];       /* buf+0x08..buf+0x103：0x104 - 8，补齐到保存区之前 */
  } sb;
  gh_byte *local_110 = (gh_byte *)&sb.sec[0] + 0x08;
  gh_byte *local_fc  = (gh_byte *)&sb.sec[0] + 0x1c;
  gh_byte *local_f8  = (gh_byte *)&sb.sec[0] + 0x20;
  gh_byte *local_58  = (gh_byte *)&sb.sec[0] + 0xc0;   /* 仅文档用途（代码经 pbVar4[0xc0] 访问） */
  
  cmd[1] = 0;
  cmd[0] = 0x9f;
  sfc_request(cmd,0,&sb.sec[0]._u32,3);
  uVar6 = sb.sec[0]._u32 & 0xff;
  (spi_id_blob)._0_1_ = (gh_byte)sb.sec[0]._u32;
  (spi_id_blob)._1_1_ = sb.sec[0]._1_1_;
  (spi_id_blob)._2_1_ = sb.sec[0]._2_1_;
  if (uVar6 == 0x85 || (uVar6 == 0xb || ((sb.sec[0]._u32 & 0xef) == 200 || uVar6 == 0x20))) {
    if (sb.sec[0]._2_1_ == '\x18') {
      FlashSize = 0x1000000;
LAB_002c41fc:
      if (uVar6 == 0xb) goto LAB_002c4360;
      if (0x400000 < FlashSize) {
        uVar5 = 0;
        uVar10 = 0x4b;
        goto LAB_002c4220;
      }
LAB_002c42cc:
      cmd[1] = 0;
      cmd[0] = 0x484b;
      sfc_request(cmd,0,&sb.sec[0]._u32,8);
      pbVar4 = (gh_byte *)&UniqueID;
      pbVar3 = (gh_byte *)&sb.sec[0];
      do {
        pbVar7 = pbVar3 + 1;
        *pbVar4 = *pbVar3;
        pbVar4 = pbVar4 + 1;
        pbVar3 = pbVar7;
      } while (pbVar7 != local_110);
    }
    else {
      if (sb.sec[0]._2_1_ == '\x17') {
        FlashSize = 0x800000;
        goto LAB_002c41fc;
      }
      if (sb.sec[0]._2_1_ == '\x16') {
        FlashSize = 0x400000;
        goto LAB_002c41fc;
      }
      if (sb.sec[0]._2_1_ == '\x15') {
        FlashSize = 0x200000;
        if (uVar6 == 0xb) goto LAB_002c4360;
        goto LAB_002c42cc;
      }
      if (sb.sec[0]._2_1_ == '\x14') {
        FlashSize = 0x100000;
      }
      else {
        if (sb.sec[0]._2_1_ != '\x13') goto LAB_002c41fc;
        FlashSize = 0x80000;
      }
      if (uVar6 != 0xb) goto LAB_002c42cc;
LAB_002c4360:
      uVar5 = 0x194;
      uVar10 = 0x5a;
LAB_002c4220:
      cmd[1] = 0;
      cmd[0] = (gh_uint)CONCAT11(0x48,uVar10);
      sfc_request(cmd,uVar5,&sb.sec[0]._u32,0x10);
      pbVar4 = (gh_byte *)&UniqueID;
      pbVar3 = (gh_byte *)&sb.sec[0];
      do {
        pbVar7 = pbVar3 + 1;
        *pbVar4 = *pbVar3 ^ pbVar3[8];
        pbVar4 = pbVar4 + 1;
        pbVar3 = pbVar7;
      } while (pbVar7 != local_110);
    }
    /* ★★ 原厂这里是 `ldrb r3,[r6]`（r6 = &spi_id）＝**读 spi_id 的第一个字节**。
     *   Ghidra 渲染成 `(gh_byte)spi_id` —— 在「spi_id 是数组」的声明下，那变成
     *   **指针→字节的转换**（取地址最低字节）！
     *   实测代价：本函数两处判断全部走错分支（重建侧读到 0xc8 而非 0x0b）
     *   ⇒ `spi_driver_init()` 返回 0 ⇒ main() 不去 main_Menu()，观测窗口少 4 行。
     *   这是 P5 深窗口抓到的**第二个真实语义分歧**（证据：shim 打印的 SFC 命令序列 ——
     *   原厂 `0x4848@0x100 / @0x000`，重建侧 `0x4848@0x2000 / @0x1000`）。 */
    if (spi_id[0] == 0xb) {
      sflash_read_security_data(&sb.sec[0]._u32,0x100);
      goto LAB_002c40e0;
    }
  }
  sflash_read_security_data(&sb.sec[0]._u32,0x2000);
LAB_002c40e0:
  printf("ROM Size:%08X CRC32:%04X ",FlashSize,sb.sec[0]);
  printf("Update time:");
  DateToTmuDate(sb.sec[1]._u32);
  if (spi_id[0] == 0xb) {
    uVar5 = 0;
  }
  else {
    uVar5 = 0x1000;
  }
  sflash_read_security_data(&sb.sec[0]._u32,uVar5);
  iVar9 = 0;
  pbVar3 = &DAT_002dee30;
  iVar8 = 0;
  pbVar4 = (gh_byte *)&sb.sec[0];
  do {
    bVar1 = *pbVar3;
    pbVar3 = pbVar3 + 1;
    if (iVar8 < 8) {
      bVar2 = *(gh_byte *)((int)&UniqueID + iVar8);
    }
    else {
      bVar2 = pbVar4[-8];
    }
    iVar8 = iVar8 + 1;
    if (*pbVar4 != (gh_byte)((bVar1 ^ bVar2) + pbVar4[0xc0])) {
      iVar9 = iVar9 + 1;
    }
    pbVar4 = pbVar4 + 1;
  } while (iVar8 != 0x18);
  if (iVar9 == 0) {
    pbVar7 = local_fc + 3;
    pbVar4 = local_fc + 1;
    pbVar3 = GamePath + 0x1b;
    do {
      pbVar7 = pbVar7 + 1;
      pbVar4 = pbVar4 + -1;
      pbVar3 = pbVar3 + 1;
      *pbVar3 = *pbVar7 ^ *pbVar4;
    } while (local_f8 + 0x1b != pbVar7);
    uVar5 = 1;
  }
  else {
    uVar5 = 0;
  }
  return uVar5;
}
