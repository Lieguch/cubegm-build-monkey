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
      UnzipItem(iVar1,local_9c,pvVar3,0,3);

      /* ★ 这里曾有 `CGM_DBGUNZ` 运行期探针（打点 UnzipItem 写入缓冲的字节和）。
       *   已撤除 —— 探针不该长期留在重建源码里（纪律：探针用完即撤）。
       *   等价观测改用**零源码改动**的方式：`tools/gdb_globals.sh`（qemu -g + gdb
       *   直接读内存/缓冲），既能看到同样的量，又不会让"重建产物"与"出厂语义"
       *   之间多出一段只在调试期存在的代码。 */
    }
    else {
      uVar2 = 0;
      RARCH_LOG("find %s fail\n",param_2);
    }
    CloseZipU(res_hz);
    return uVar2;
  }
  RARCH_LOG("open %s fail\n",acStack_98);
  return 0;
}
