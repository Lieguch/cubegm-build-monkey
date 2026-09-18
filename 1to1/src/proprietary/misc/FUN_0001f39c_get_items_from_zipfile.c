/* ============================================================
 * get_items_from_zipfile   @ 0x0001f39c   size=360B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int get_items_from_zipfile(char *param_1,char *param_2)

{
  char cVar1;
  int iVar2;
  char *__ptr;
  char *pcVar3;
  int iVar4;
  char *pcVar5;
  gh_u4 local_424;
  char acStack_420 [1024];
  
  res_hz = OpenZipU((void *)param_1,0,2);
  if (res_hz == 0) {
    RARCH_LOG("open %s fail\n",param_1);
    return 0;
  }
  zr = FindZipItemA(res_hz,"ui.cfg",1,&local_424,ze);
  /* ================= ★★ 临时诊断（第 42 轮，跑完即撤） =================
   * 目的：定位「工厂 FindZipItemA("ui.cfg") 返回非 0（失败）、我们返回 0（成功）」。
   *   两侧源码**完全相同**（硬编码 "ui.cfg"、标志 1）⇒ 差异在运行期。
   * 打点内容：
   *   tag   = HZIP->[0]（FindZipItemA 要求 == 1，否则返回 0x80000）
   *   n     = unz->[4]（中央目录里的条目总数）
   *   cur   = unz->[16]（当前条目索引）
   *   f24   = unz->[24]（"已有文件列表"标志）
   *   idx   = &local_424（FindZipItemA 写回的索引）
   *   name4 = ZIPENTRY 里的条目名（偏移 4）
   * 判读：若 zr==0 且 name4 不是 "ui.cfg"，说明我们**匹配到了错误的条目**；
   *       若 n==0，说明中央目录没被正确解析（条目数 0 ⇒ 任何名字都查不到）。
   * ==================================================================== */
  {
    unsigned char *hz_ = (unsigned char *)res_hz;
    unsigned char *tz_ = (unsigned char *)(*(gh_u4 *)(hz_ + 4));
    unsigned char *uz_ = (unsigned char *)(*(gh_u4 *)tz_);
    RARCH_LOG("DBGZIP p=%s zr=%d idx=%d tag=%d n=%d cur=%d f24=%d name4='%s'%s",
              param_1, zr, local_424, *(int *)hz_, *(int *)(uz_ + 4),
              *(int *)(uz_ + 0x10), *(int *)(uz_ + 0x18),
              (char *)((unsigned char *)ze + 4), "\n");
  }
  if (zr != 0) {
    RARCH_LOG("find ui.cfg in %s fail\n",param_1);
    CloseZipU(res_hz);
    return 0;
  }
  __ptr = malloc((ze_blob)._296_4_);
  UnzipItem(res_hz,local_424,__ptr,0,3);
  CloseZipU(res_hz);
  if (__ptr == (char *)0x0) {
    iVar4 = 0;
LAB_0001f4a8:
    free(__ptr);
    return iVar4;
  }
  iVar4 = 0;
  pcVar3 = acStack_420;
  pcVar5 = __ptr;
LAB_0001f448:
  do {
    cVar1 = *pcVar5;
    while (pcVar5 = pcVar5 + 1, cVar1 != '\n') {
      if (cVar1 == '\r') goto LAB_0001f448;
      if (cVar1 == '\0') {
        *pcVar3 = '\0';
        get_item_from_line(acStack_420,iVar4 * 0xfa + param_2);
        iVar4 = iVar4 + 1;
        goto LAB_0001f4a8;
      }
      *pcVar3 = cVar1;
      pcVar3 = pcVar3 + 1;
      cVar1 = *pcVar5;
    }
    iVar2 = iVar4 * 0xfa;
    *pcVar3 = '\0';
    iVar4 = iVar4 + 1;
    get_item_from_line(acStack_420,iVar2 + param_2);
    pcVar3 = acStack_420;
  } while( true );
}
