/* ============================================================
 * mui_DisplayThumbnail   @ 0x00014f84   size=568B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_DisplayThumbnail(void)

{
  gh_u4 *iVar1;
  int iVar2;
  void *__ptr;
  int iVar3;
  gh_u1 *puVar4;
  gh_u4 local_38c;
  /* ★ R180 根修（GAP 18.02，与 R173 FBA_Load / R179 八条同构）：
   * -0x388..-0x35c 是 mui_blockcopy(param_1=&local_370, param_2=&local_388) 的
   * **连续 12 个 int 参数槽**。Ghidra 把它们拆成 12 个独立标量，于是 C 层
   * `&local_370` / `&local_388` 只让**首元素**的地址逃逸；`mui_blockcopy` 却按
   * `int*` 索引 param_1[1..5] / param_2[1..5]（= local_36c..35c / local_384..374）。
   * 按 C 标准这是跨对象访问（UB）⇒ `-Os` 判定后 11 个槽为死存储并整段删除。
   * 实测铁证（云机 arm-linux-gnueabihf-gcc 14.2）：
   *   -O0：`bl mui_blockcopy` 前 13 条栈 str（12 槽全写）
   *   -Os：调用前仅 2 条 str（`str r4,[r1]`=param_2[0]、`str r3,[sp,#20]`=param_1[0]）
   *        ⇒ 其余 10 槽是栈垃圾 ⇒ 缩略图 blit 用错 stride/src/dst，行为发散。
   * 集合级 Δ 门禁**放行了本条**：af29c/af2a0/af6b8/af6bc/af6c0/af6c4 在本函数
   * 的 memcpy 循环里仍被引用 ⇒ 符号未消失 ⇒ Δ=[]（GAP 18.01 盲区，已由
   * dce_ref_diff.py --count 出现次数级判据堵住）。
   * 数组化让地址逃逸覆盖整段：mui_blockcopy(&blk[6],&blk[0]) 后
   * [6..11] 收 param_1、[0..5] 收 param_2，-Os 不再消除任何一个槽。
   * 回退：本段整体还原为 12 个标量声明 + 原调用即可。 */
  int blk[12];
  gh_u1 auStack_358 [128];
  gh_u1 auStack_2d8 [128];
  char acStack_258 [128];
  char acStack_1d8 [128];
  /* ★★★ R305 根修（真机 SIGSEGV 归因 · ZIPENTRY 尺寸/取址族 · 本轮真机实证）：
   *
   * 【症状】真机 0.2-0.4s 闪重启；crash.txt = SIGSEGV si_code=1(MAPERR)
   *   si_addr=0x10001000（不在 /proc/self/maps 任何区 ⇒ 野指针），ms=5868；
   *   调用链 UnzipItem → TUnzip::Unzip → unzReadCurrentFile → inflate
   *   → inflate_blocks → inflate_codes（pc=0x60d7d4 落在 inflate_codes sym@0x60d404+2384 内）。
   *   寄存器 r3=0x10001000（= si_addr）、r2=0xb2f116d8（合法映射）⇒ 解压中读到坏指针。
   *
   * 【机制 · 我方 ELF 机器码实锤】本函数 `size_t local_30;` **声明后从未赋值**
   *   ⇒ -Os 下 r0 残留 ⇒ `malloc(local_30)` 实为 **malloc(0)**（实测机器码 0x4e558c
   *   `bl 0x4015d0`，其前 r0 的最后写入 = FindZipItemA 的返回值 0）。
   *   随后 `UnzipItem(iVar1,local_38c,__ptr,0,3)` 走 ZIP_MEMORY 路径：工厂
   *   TUnzip::Unzip 以 16KB 为块循环填满 dst（unzReadCurrentFile(uf,out,16384);
   *   out += 16384;）⇒ dst 尺寸不足 ⇒ 连续越界写 ⇒ 堆破坏 ⇒ inflate 内部
   *   解引用坏指针 ⇒ SIGSEGV ⇒ 设备重启（0.2-0.4s 闪重启即此因）。
   *
   * 【工厂真相 · 权威源 tool/factory_t1.txt（835 函数带符号反汇编）+ 字节指纹校准】
   *   - 本函数工厂真实基址 = 0x14f84 - 0xb474 = **0x9B10**
   *     （校准方式：`sub sp,sp,#884`（e24ddfdd）在 factory_text.bin 全 blob 唯一命中
   *      @0xb478，且 +32 处 `mov r2,#128` 恰为 idx9 ⇒ 偏移 0xb474 对应 Ghidra 0x14f84）
   *   - 工厂把 ZIPENTRY 放栈上：`add r9,sp,#576`（= sp+144*4）
   *   - 工厂 malloc 尺寸 = `LDR r0,[sp,#872]` = ZIPENTRY + 296 = **unc_size**
   *     （原始字 @0x15080 `e59d0368` = LDR r0,[sp,#872]；@0x15084 `ebffd1ac` = BL malloc）
   *   ⇒ 工厂语义 = `malloc(unc_size)`，与 Find → Get 填充的
   *      `ze->unc_size = ufi.uncompressed_size`（src/upstream/xunzip/unzip.cpp:3959）精确对应。
   *
   * 【布局】ZIPENTRY sizeof = **304**（工厂 `memset(r0,#304)` + Get 的 304B memcpy 自洽；
   *   unc_size@296、额外字段@300）。原声明 **296B 少 4 字节** ⇒ unc_size 落在缓冲外。
   *
   * 【修复】本地 ZIPENTRY 改用 R284 基建 `ze_t`（304B、对齐 4、含 `_296_4_`），
   *   malloc 实参 = `auStack_158._296_4_`（= unc_size），删除未赋值的 local_30。
   *   顺带消除原 `gh_u1[296]` 的非对齐 int 访问隐患（改后偏移 296 处按对齐 4 访问）。
   *
   * 【回退】本段整体还原为 `gh_u1 auStack_158[296]` + `size_t local_30` +
   *   `__ptr = malloc(local_30);` 即可（但会重新引入 malloc(0) 崩溃）。 */
  ze_t auStack_158;
  
  puVar4 = auStack_358;
  mui_extract_basepath(puVar4,&file_info_list + DAT_003af27c * 0x404,0x80);
  mui_extract_basename(auStack_2d8,&file_info_list + DAT_003af27c * 0x404,0x80);
  sprintf(acStack_258,"%s/%s/%s.dat",root_path,puVar4,puVar4);
  iVar1 = OpenZipU(acStack_258,0,2);
  if (iVar1 == 0) {
    RARCH_LOG("open %s fail\n",acStack_258);
  }
  else {
    while( true ) {
      sprintf(acStack_1d8,"%s_%03d.raw",auStack_2d8,DAT_003af280,puVar4);
      puVar4 = (gh_u1 *)&auStack_158;   /* R305：auStack_158 改 ze_t union，需显式取字节址 */
      /* 证据：15028 add r9,sp,#0x240 + 15060 str r9,[sp]（AAPCS 第 5 参经栈传递）
         → 原厂此处传了 ZIPENTRY 输出缓冲；Ghidra C 漏参并留下死赋值 puVar4 = auStack_158 */
      iVar2 = FindZipItemA(iVar1,acStack_1d8,1,&local_38c,(ZIPENTRY *)&auStack_158);   /* R305：ze_t 304B 缓冲（对齐 4） */
      if (iVar2 == 0) break;
      if (DAT_003af280 == 0) {
        iVar2 = 0;
        if (0 < DAT_003af6c4) {
          do {
            iVar3 = iVar2 + DAT_003af6bc;
            iVar2 = iVar2 + 1;
            iVar3 = DAT_003af2a0 * 2 * iVar3;
            memcpy((void *)(DAT_003af29c + iVar3 + DAT_003af6b8 * 2),
                   (void *)((int)DAT_003af28c + DAT_003af6b8 * 2 + *DAT_003af28c + iVar3),
                   DAT_003af6c0 << 1);
          } while (iVar2 < DAT_003af6c4);
        }
        goto LAB_00015128;
      }
      DAT_003af280 = 0;
    }
    __ptr = malloc(auStack_158._296_4_);   /* R305：= unc_size（工厂 LDR r0,[sp,#872] = ZIPENTRY+296）；原为 malloc(local_30) = malloc(0) ⇒ 越界写堆 ⇒ SIGSEGV */
    UnzipItem(iVar1,local_38c,__ptr,0,3);
    blk[3] = DAT_003af6c0;                 /* local_37c = param_2[3] 源高 */
    blk[7] = DAT_003af6b8;                 /* local_36c = param_1[1] 目标左 */
    blk[4] = DAT_003af6c4;                 /* local_378 = param_2[4] 源行数 */
    blk[8] = DAT_003af6bc;                 /* local_368 = param_1[2] 目标上 */
    blk[9] = DAT_003af6b8 + DAT_003af6c0;  /* local_364 = param_1[3] */
    blk[5] = DAT_003af6c0 << 1;            /* local_374 = param_2[5] 源 stride */
    blk[10] = DAT_003af6bc + DAT_003af6c4; /* local_360 = param_1[4] */
    blk[6] = (int)DAT_003af29c;            /* local_370 = param_1[0] 目标基址 */
    blk[11] = DAT_003af2a0 << 1;           /* local_35c = param_1[5] 目标 stride */
    blk[0] = (int)__ptr;                   /* local_388 = param_2[0] 源基址 */
    blk[1] = iVar2;                        /* local_384 = param_2[1] 源左 */
    blk[2] = iVar2;                        /* local_380 = param_2[2] 源上 */
    mui_blockcopy(&blk[6],&blk[0]);
    free(__ptr);
    DAT_003af280 = DAT_003af280 + 1;
LAB_00015128:
    CloseZipU(iVar1);
  }
  return;
}
