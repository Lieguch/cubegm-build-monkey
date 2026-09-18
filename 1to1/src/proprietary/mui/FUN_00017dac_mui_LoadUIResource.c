/* ============================================================
 * mui_LoadUIResource   @ 0x00017dac   size=296B   callers=12
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 mui_LoadUIResource(gh_u4 **param_1,char *param_2)

{
  gh_u4 *iVar1;
  gh_u4 uVar2;
  void *pvVar3;
  gh_u4 local_9c;
  char acStack_98 [128];
  
  uVar2 = (gh_u4)GetWorkPath();
  sprintf(acStack_98,"%s/%s",uVar2,(&m_ui)[m_ui + 0x16] + 0x20);
  /* ================= ★★ 临时诊断（第 44 轮，跑完即撤）=================
   * 目的：场景 E 里工厂打印了 `find setting.raw fail`、我们**一条都没打印**，
   *   而两侧 `mui_LoadUIResource` 源码**逐行相同**、且都"被执行"。
   *   ⇒ 差异只可能在**请求了哪些资源名 / 哪个包路径**。
   * 打点：请求名 req、打开的包路径 zip、查找结果 zr（0=命中）。
   * ==================================================================== */
  RARCH_LOG("DBGUI2 req=%s zip=%s\n", param_2, acStack_98);
  res_hz = OpenZipU(acStack_98,0,2);
  if (res_hz != 0) {
    zr = FindZipItemA(res_hz,param_2,1,&local_9c,ze);
    if (zr == 0) {
      if ((void *)*param_1 != (void *)0x0) {
        free((void *)*param_1);
      }
      uVar2 = 1;
      pvVar3 = malloc((ze_blob)._296_4_);
      iVar1 = res_hz;
      *param_1 = pvVar3;
      RARCH_LOG("DBGUI2 req=%s zr=0 HIT size=%u\n", param_2,
                (unsigned)(ze_blob)._296_4_);
      UnzipItem(iVar1,local_9c,pvVar3,0,3);
    }
    else {
      uVar2 = 0;
      RARCH_LOG("DBGUI2 req=%s zr=%ld MISS\n", param_2, (long)zr);
      RARCH_LOG("find %s fail\n",param_2);
    }
    CloseZipU(res_hz);
    return uVar2;
  }
  RARCH_LOG("open %s fail\n",acStack_98);
  return 0;
}
