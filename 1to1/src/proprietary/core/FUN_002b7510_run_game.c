/* ============================================================
 * run_game   @ 0x002b7510   size=1260B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 run_game(char *param_1, ...)   /* R284：变参原型（工厂 mui_run_game 传 2 参）；.text 与非变参一致 */

{
  char *pcVar1;
  int iVar2;
  FILE *__stream;
  gh_u4 *iVar3;
  int iVar4;
  size_t sVar5;
  gh_uint uVar6;
  char acStack_160 [8];
  /* 根修（UB）：这是**一块 0x130 字节栈缓冲**（Ghidra 误声明为 4 字节 int）。
     `memset(&local_158,0,sizeof(local_158))` / `GetZipItemA(...,&local_158)` /
     `extract_basepath((char*)&local_158,...)` 都按缓冲用 ⇒ 原声明使 memset 越界 = UB。
     ★★★ R305 根修（真机 SIGSEGV 归因 · Rule A 同族）：缓冲改用 R284 基建 `ze_t`
     （304B = 0x130、对齐 4、含 `_296_4_`），并删除**声明后从未赋值**的 `size_t local_30;`
     —— 原 `malloc(local_30 + 0x10)` 实参是栈垃圾 ⇒ 分配尺寸与真实解压后尺寸无关
     ⇒ TUnzip::Unzip 的 16KB 块循环越界写 ⇒ 堆破坏 ⇒ inflate 野指针 ⇒ SIGSEGV
     （真机 crash.txt：si_addr=0x10001000 不在任何映射区）。
     【工厂真相 · tool/factory_t1.txt run_game 指令 277-281】
       277: `ldr r2,[sp,#320]` = ZIPENTRY(sp+24) + 296 = **unc_size**
       279: `add r0,r2,#16`      ⇒ malloc(unc_size + 16)
       280: `str r2,[r8]`        ⇒ ZIP_BUF_SIZE = unc_size
     【回退】还原 `gh_u1 local_158[0x130]` + `size_t local_30` + 原始两行即可。 */
  ze_t local_158;
  char acStack_154 [4];
  char acStack_150 [288];
  
  ZIP_BUF = (void *)0x0;
  ZIP_BUF_SIZE = 0;
  pcVar1 = (char *)GetFilenameExt(param_1);
  strcpy(acStack_160,pcVar1);
  strupr(acStack_160);
  RARCH_LOG("run_game %s,%s\n",param_1,acStack_160);
  Filetype = 0;
  iVar2 = GetCoreIndex(acStack_160);
  uVar6 = Filetype;
  if (0xffff < Filetype) {
    pcVar1 = strstr(param_1,"/000/");
    if (pcVar1 != (char *)0x0) {
      Filetype = uVar6 | 1;
      FBA_Load(param_1);
      return 1;
    }
    memset(&local_158,0,sizeof(local_158));   /* R305：ze_t 304B（= 0x130），与工厂 memset(r0,#304) 一致 */
    iVar3 = OpenZipU(param_1,0,2);
    if (iVar3 != 0) {
      GetZipItemA(iVar3,0xffffffff,(ZIPENTRY *)&local_158);   /* R284：ZIPENTRY* cast（304B 缓冲） */
      iVar4 = GetZipItemA(iVar3,0,(ZIPENTRY *)&local_158);   /* R284：同上 */
      if (iVar4 == 0) {
        strupr(acStack_154);
        pcVar1 = (char *)GetFilenameExt(acStack_154);
        strcpy(acStack_160,pcVar1);
        if (1 < (int)local_158._0_4_) {   /* R305：count = ZIPENTRY+0（工厂 ldr fp,[sp,#24]）；工厂 cmp fp,#1; ble ⇒ count>1 走 FBA 分支 */
          Filetype = Filetype | 1;
          CloseZipU(iVar3);
          FBA_Load(param_1,Filetype);   /* R284：恢复工厂调用点（语料 run_game.c:50 = 2 参）；FBA_Load 为变参原型 */
          return 1;
        }
        iVar2 = GetCoreIndex(acStack_160);
        if ((short)Filetype == 0x10) {
          CloseZipU(iVar3);
          Gpsp_Load(param_1,Filetype);
          return 1;
        }
        ZIP_BUF_SIZE = local_158._296_4_;         /* R305：= unc_size（工厂指令 280 `str r2,[r8]`） */
        ZIP_BUF = malloc(ZIP_BUF_SIZE + 0x10);    /* R305：工厂指令 279 `add r0,r2,#16` ⇒ malloc(unc_size+16) */
        if (ZIP_BUF == (void *)0x0) {
          CloseZipU(iVar3);
          return 0;
        }
        iVar4 = UnzipItem(iVar3,0,ZIP_BUF,0,3);
        if (iVar4 == 0) {
          CloseZipU(iVar3);
        }
      }
    }
LAB_002b7664:
    uVar6 = Filetype & 0xffff;
    if (uVar6 == 4) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if (uVar6 == 8) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if (uVar6 == 2) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if (uVar6 == 0x400) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if ((uVar6 - 0x20 & 0xffffffdf) == 0) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if (uVar6 == 0x100) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if (uVar6 == 0x200) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
    }
    if (ZIP_BUF != (void *)0x0) {
      free(ZIP_BUF);
    }
    ZIP_BUF_SIZE = 0;
    ZIP_BUF = (void *)0x0;
    return 1;
  }
  if (Filetype == 0x10) {
    Gpsp_Load(param_1,0x10);
    return 1;
  }
  if (Filetype != 0x80) {
    if (Filetype != 0x800) {
      __stream = fopen(param_1,"rb");
      if (__stream == (FILE *)0x0) {
        RARCH_LOG("%s open fail\r\n",param_1);
        return 0xffffffff;
      }
      fseek(__stream,0,2);
      ZIP_BUF_SIZE = ftell(__stream);
      fseek(__stream,0,0);
      ZIP_BUF_SIZE = ZIP_BUF_SIZE + 3 & 0xfffffffc;
      ZIP_BUF = malloc(ZIP_BUF_SIZE + 4);
      if (ZIP_BUF == (void *)0x0) {
        fclose(__stream);
      }
      fread(ZIP_BUF,1,ZIP_BUF_SIZE,__stream);
      fclose(__stream);
      goto LAB_002b7664;
    }
    extract_basepath((char *)&local_158,param_1,100);
    sVar5 = strlen((char *)&local_158);
    builtin_strncpy((char *)((int)&local_158 + sVar5),"/gam",4);
    builtin_strncpy(acStack_154 + sVar5,"e.cf",4);
    (acStack_150 + sVar5)[0] = 'g';
    (acStack_150 + sVar5)[1] = '\0';
    get_items_from_file((char *)&local_158,items);
  }
  Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
  return 1;
}
