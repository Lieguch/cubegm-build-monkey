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
  gh_u4 local_120;
  gh_u4 local_11c;
  /* ★★ 原厂这里是**同一块安全数据缓冲的前两个字**（Ghidra 把它拆成了两个独立标量）：
   *    · `sflash_read_security_data(&sec_buf[0], 0x2000)` ⇒ 把安全数据整块读进 &buf[0]；
   *    · `printf("… CRC32:%04X ", …, sec_buf[0])` ⇒ 打印 buf[0]；
   *    · `DateToTmuDate(sec_buf[1]._u32)`            ⇒ 用 buf[1] 解出 "Update time"。
   *   ⇒ 必须表达成**相邻数组**：若写成两个独立标量，编译器可以把 buf[1] 放到那次
   *     0x100 字节写入的范围之外，于是读到链上残留值 —— 实测症状就是
   *     `Update time:1980-0-0 0:0:0`（原厂） vs `…0:0:24`（重建）。
   *   ⇒ 数组保证 buf[0]/buf[1] 相邻、并被同一次写入覆盖。
   *   （证据：工厂反汇编 `str ip,[sp]`/`str ip,[sp,#4]` 之后 `strb 0x9f,[sp]`，
   *     再 `bl sfc_request(sp, 0, r5=sp+8, 3)`；buf 起点 = sp+8。） */
  gh_u32_bytes_t sec_buf[2];  /* [0] = 原 local_118（CRC32）；[1] = 原 local_114（Update time） */

  /* ★★ 保持与原厂一致的**栈帧形状**（这一条是被行为差分逼出来的）：
   *   原厂帧 = `sub sp, sp, #0x10C`（268 B），安全数据缓冲区之后还排着
   *   local_110(20) / local_fc(4) / local_f8(160) / local_58(68) 共 252 B。
   *   它们在本重建里没有别的引用，于是编译器把整帧压到 ~36 B ⇒
   *   `sflash_read_security_data(&sec_buf[0], 0x2000)` 那 **0x100=256 字节写入**
   *   就会越过本帧、**破坏调用者的局部**（原厂帧够大，写在自己帧内）。
   *   ⇒ 用一条空 asm 强制这四个对象的地址被取用，把它们保留在帧里。
   *     空 asm 无运行期效果、不改任何数据；只是阻止"未使用即删除"的优化。 */
  gh_byte local_110 [20];
  gh_byte local_fc [4];
  gh_byte local_f8 [160];
  gh_byte local_58 [68];
  __asm__ __volatile__("" :: "r"(&local_110[0]), "r"(&local_fc[0]),
                            "r"(&local_f8[0]), "r"(&local_58[0]));
  
  local_11c = 0;
  local_120 = 0x9f;
  sfc_request(&local_120,0,&sec_buf[0]._u32,3);
  uVar6 = sec_buf[0]._u32 & 0xff;
  (spi_id_blob)._0_1_ = (gh_byte)sec_buf[0]._u32;
  (spi_id_blob)._1_1_ = sec_buf[0]._1_1_;
  (spi_id_blob)._2_1_ = sec_buf[0]._2_1_;
  if (uVar6 == 0x85 || (uVar6 == 0xb || ((sec_buf[0]._u32 & 0xef) == 200 || uVar6 == 0x20))) {
    if (sec_buf[0]._2_1_ == '\x18') {
      FlashSize = 0x1000000;
LAB_002c41fc:
      if (uVar6 == 0xb) goto LAB_002c4360;
      if (0x400000 < FlashSize) {
        uVar5 = 0;
        uVar10 = 0x4b;
        goto LAB_002c4220;
      }
LAB_002c42cc:
      local_11c = 0;
      local_120 = 0x484b;
      sfc_request(&local_120,0,&sec_buf[0]._u32,8);
      pbVar4 = (gh_byte *)&UniqueID;
      pbVar3 = (gh_byte *)&sec_buf[0];
      do {
        pbVar7 = pbVar3 + 1;
        *pbVar4 = *pbVar3;
        pbVar4 = pbVar4 + 1;
        pbVar3 = pbVar7;
      } while (pbVar7 != local_110);
    }
    else {
      if (sec_buf[0]._2_1_ == '\x17') {
        FlashSize = 0x800000;
        goto LAB_002c41fc;
      }
      if (sec_buf[0]._2_1_ == '\x16') {
        FlashSize = 0x400000;
        goto LAB_002c41fc;
      }
      if (sec_buf[0]._2_1_ == '\x15') {
        FlashSize = 0x200000;
        if (uVar6 == 0xb) goto LAB_002c4360;
        goto LAB_002c42cc;
      }
      if (sec_buf[0]._2_1_ == '\x14') {
        FlashSize = 0x100000;
      }
      else {
        if (sec_buf[0]._2_1_ != '\x13') goto LAB_002c41fc;
        FlashSize = 0x80000;
      }
      if (uVar6 != 0xb) goto LAB_002c42cc;
LAB_002c4360:
      uVar5 = 0x194;
      uVar10 = 0x5a;
LAB_002c4220:
      local_11c = 0;
      local_120 = (gh_uint)CONCAT11(0x48,uVar10);
      sfc_request(&local_120,uVar5,&sec_buf[0]._u32,0x10);
      pbVar4 = (gh_byte *)&UniqueID;
      pbVar3 = (gh_byte *)&sec_buf[0];
      do {
        pbVar7 = pbVar3 + 1;
        *pbVar4 = *pbVar3 ^ pbVar3[8];
        pbVar4 = pbVar4 + 1;
        pbVar3 = pbVar7;
      } while (pbVar7 != local_110);
    }
    if ((gh_byte)spi_id == 0xb) {
      sflash_read_security_data(&sec_buf[0]._u32,0x100);
      goto LAB_002c40e0;
    }
  }
  sflash_read_security_data(&sec_buf[0]._u32,0x2000);
LAB_002c40e0:
  printf("ROM Size:%08X CRC32:%04X ",FlashSize,sec_buf[0]);
  printf("Update time:");
  DateToTmuDate(sec_buf[1]._u32);
  if ((gh_byte)spi_id == 0xb) {
    uVar5 = 0;
  }
  else {
    uVar5 = 0x1000;
  }
  sflash_read_security_data(&sec_buf[0]._u32,uVar5);
  iVar9 = 0;
  pbVar3 = &DAT_002dee30;
  iVar8 = 0;
  pbVar4 = (gh_byte *)&sec_buf[0];
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
