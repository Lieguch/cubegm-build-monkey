/* ============================================================
 * FilePreEmu   @ 0x00016f08   size=676B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 FilePreEmu(char *param_1)

{
  char *pcVar1;
  gh_u4 uVar2;
  FILE *__stream;
  gh_u4 *iVar3;
  int iVar4;
  gh_uint uVar5;
  /* 根修（UB）：同 run_game.c —— 这是 0x130 字节栈缓冲，非 4 字节 int。 */
  /* ★★★ R305 根修（真机 SIGSEGV 归因 · Rule A 同族）：本地 ZIPENTRY 缓冲改用
   * R284 基建 `ze_t`（304B、对齐 4、含 `_296_4_`），并删除**声明后从未赋值**的
   * `int local_30;`。
   * 【机制】`malloc(local_30 + 0x10)` 的实参是栈垃圾 ⇒ 分配尺寸与真实解压后尺寸
   *   无关 ⇒ TUnzip::Unzip 的 16KB 块循环越界写 ⇒ 堆破坏 ⇒ inflate 内部野指针
   *   ⇒ SIGSEGV（真机 crash.txt：si_addr=0x10001000 不在任何映射区）。
   * 【工厂真相 · tool/factory_t1.txt FilePreEmu 指令 143-151】
   *   144: `ldr r2,[sp,#304]` = ZIPENTRY(sp+8) + 296 = **unc_size**
   *   146: `add r0,r2,#16`      ⇒ malloc(unc_size + 16)
   *   147: `str r2,[r4]`        ⇒ ZIP_BUF_SIZE = unc_size
   *   ⇒ 工厂语义 = `ZIP_BUF_SIZE = unc_size; ZIP_BUF = malloc(unc_size + 0x10);`
   * 【回退】还原 `gh_u1 local_158[0x130]` + `int local_30` + 原始两行即可。 */
  ze_t local_158;
  gh_u1 auStack_154 [292];
  
  pcVar1 = (char *)GetFilenameExt(param_1);
  /* ★★★ 2026-10-04（第 132 轮）T09 根修：`(ze + 184)` 是 **Ghidra 重建的错误基址**。
   *
   * 取证链（算术自证，非推断）：
   *   工厂 FilePreEmu @0x16f08 前 10 条（golden/factory.funcs.json + pyelftools 实读）：
   *       4  ldr r4, [pc, #0x28c]     ; 字面量 @0x171ac = 0x003a52cc
   *       7  add r4, pc, r4           ; ARM PC = 指令地址+8 = 0x16f2c
   *   9  add r4, r4, #0xc8        ; +200
   *   ⇒ r4 = (0x16f2c + 0x3a52cc) + 0xc8 = 0x3bc1f8 + 0xc8 = **0x3bc2c0**
   *   而 0x3bc2c0 = `FilenameExt`（`src/compat/globals.h:4602` 已按工厂地址声明）。
   *
   *   另一条独立验算：`file_info_list` @0x3b2220 size **0xa0a0**，
   *   0x3b2220 + 0xa0a0 = **0x3bc2c0** ⇒ `FilenameExt` 就是 `file_info_list`
   *   数组的**紧邻后继**（`&file_info_list[0xa0a0]`），两条路径指向同一地址 ✓
   *
   * 错在哪：Ghidra 把 0x3bc2c0 识别成 `ze + 184`（`ze` @0x3bc2d0，0x3bc2d0+0xb8=0x3bc388），
   *   与真地址 0x3bc2c0 **相差 0xC8(200) 字节** ⇒ 差分实测工厂读 FilenameExt、
   *   我方读 ze+184（`tools/diff_exec.py` 报「仅F=FilenameExt+0@0x3bc2c0
   *   仅O=ze+184@0x3bc388」）。
   * 为何必须改而不是登记豁免：`FilenameExt` 与 `file_info_list` 在工厂 `.bss` 里
   *   **相邻**，绑错基址 = 真机读到**另一个对象的内存**（同 dup_sym_gate 文档里
   *   `ArchivePath` 的真缺陷族）⇒ 是真缺陷，不是等价实现。
   * 为何不用 `&file_info_list[0xa0a0]` 表达式：语义上等价，但 `FilenameExt`
   *   已在 globals.h 按工厂地址声明、且 `SeletEmuCore.c:139` 已在用它 ⇒ 用符号更可读。
   * 回退：git checkout src/proprietary/core/FUN_00016f08_FilePreEmu.c
   */
  strcpy((char *)&FilenameExt,pcVar1);
  strupr((char *)&FilenameExt);
  Filetype = 0;
  GetCoreIndex((char *)&FilenameExt);
  RARCH_LOG("Filetype %d\n",Filetype);
  uVar5 = Filetype;
  if (Filetype < 0x10000) {
    __stream = fopen(param_1,"rb");
    if (__stream != (FILE *)0x0) {
    RARCH_LOG("FilePreEmu: open file SUCCESS\n");
      fseek(__stream,0,2);
      ZIP_BUF_SIZE = ftell(__stream);
      fseek(__stream,0,0);
      uVar5 = ZIP_BUF_SIZE + 3 & 0xfffffffc;
      ZIP_BUF_SIZE = uVar5;
      ZIP_BUF = malloc(uVar5 + 4);
      if (ZIP_BUF == (void *)0x0) {
        ZIP_BUF_SIZE = 0;
      }
      else {
        fread(ZIP_BUF,1,uVar5,__stream);
      }
      fclose(__stream);
      RARCH_LOG("FilePreEmu: return 1\n");
      return 1;
    }
    RARCH_LOG("FilePreEmu: file open FAIL\n");
    uVar2 = 0;
  }
  else {
    pcVar1 = strstr(param_1,"000/");
    if (pcVar1 == (char *)0x0) {
      memset(&local_158,0,sizeof(local_158));   /* R305：ze_t 304B（= 0x130），与工厂 memset(r0,#304) 一致 */
      iVar3 = OpenZipU(param_1,0,2);
    if (iVar3 == 0) {
    RARCH_LOG("FilePreEmu: OpenZipU FAIL\n");
      RARCH_LOG("open %s fail!\n",param_1);
      uVar2 = 0;
    }
    else {
    RARCH_LOG("FilePreEmu: OpenZipU OK\n");
        GetZipItemA(iVar3,0xffffffff,(ZIPENTRY *)&local_158);   /* R284：304B 缓冲（=sizeof(ZIPENTRY)）；cast 对齐严格原型 */
        RARCH_LOG("zipcount %d\n",(int)local_158._0_4_);   /* R305：count = ZIPENTRY+0（工厂 ldr r8,[sp,#8]） */
        /* ★ R305 根修（Rule B：数组 vs 数值的指针比较 = UB）：原 `local_158 < 2`
         * 是把栈数组退化后的**指针**与 2 比较 ⇒ 恒为 false ⇒ 解压分支永不可达。
         * 【工厂真相】tool/factory_t1.txt FilePreEmu 指令 97-98：
         *     97: `cmp r8,#1`  98: `ble @FilePreEmu+0x1d8`
         *   0x1d8 = 指令 118（每条 4 字节）= `mov r2,sl; mov r1,fp; mov r0,r7;
         *   bl @GetZipItemA`（第二次 Get，index=0）⇒ **count ≤ 1 时走解压分支**；
         *   count > 1 时走指令 99-105（Filetype |= 1; CloseZipU; return 1 = FBA 分支）。
         * ⇒ 等价 C = `count < 2` ⇒ 解压分支；count > 1 ⇒ FBA 分支。
         *   与 run_game.c 同族（R284 已用 `1 < *(int*)(void*)local_158` 修好，
         *   工厂 run_game 指令 145-146 `cmp fp,#1; ble +0x438` 语义一致）。
         * 【回退】还原 `if (local_158 < 2)` 即可（会退回恒假的 UB 比较）。 */
        if (2 > (int)local_158._0_4_) {
          iVar4 = GetZipItemA(iVar3,0,(ZIPENTRY *)&local_158);   /* R284：同上 */
          RARCH_LOG("FilePreEmu: GetZipItemA0 result=%d\n",iVar4);
          if (iVar4 == 0) {
            strupr(auStack_154);
            pcVar1 = (char *)GetFilenameExt(auStack_154);
            strcpy((char *)&FilenameExt,pcVar1);
            strupr((char *)&FilenameExt);
            RARCH_LOG("FilenameExt %s\n",(char *)&FilenameExt);
            GetCoreIndex((char *)&FilenameExt);
            RARCH_LOG("Filetype %d\n",Filetype);
            ZIP_BUF_SIZE = local_158._296_4_;         /* R305：= unc_size（工厂指令 147 `str r2,[r4]`） */
            ZIP_BUF = malloc(ZIP_BUF_SIZE + 0x10);    /* R305：工厂指令 146 `add r0,r2,#16` ⇒ malloc(unc_size+16) */
            if (ZIP_BUF == (void *)0x0) {
              ZIP_BUF_SIZE = 0;
            }
            else {
              iVar4 = UnzipItem(iVar3,0,ZIP_BUF,0,3);
              if (iVar4 != 0) {
                free(ZIP_BUF);
                ZIP_BUF = (void *)0x0;
                ZIP_BUF_SIZE = 0;
              }
            }
          }
        }
        else {
          Filetype = Filetype | 1;
        }
        CloseZipU(iVar3);
        RARCH_LOG("FilePreEmu: return 1\n");
        uVar2 = 1;
      }
    }
    else {
      uVar2 = 1;
      Filetype = uVar5 | 1;
    }
  }
  return uVar2;
}
