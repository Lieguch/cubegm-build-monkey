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

      /* ★ 运行期证据探针（`CGM_DBGUNZ=1`，默认关；只在场景 E 启用）：
       *   目的 = 证明 `TUnzip::Unzip` 的 memory 路**真的把数据写进了目标缓冲** ——
       *   第 46 轮修掉"零拷贝"后，机器码已核对，但**运行期**尚未验证。
       *   打点：条目名 / 声明大小 / 前 64 KiB 字节和 / 非零字节数 / 首 8 字节。
       *   判读：修复前 sum=0 且 nz=0（缓冲从未被写）；修复后 sum>0 且 nz 远大于 0。
       *   ★ 探针只在重建侧 stdout 出现 ⇒ 必须 env 门控，
       *     且**不得**在硬门禁场景（A/B/C）启用，否则污染行为门禁。 */
      if (getenv("CGM_DBGUNZ") != 0) {
        unsigned char *bp = (unsigned char *)pvVar3;
        unsigned lit = (unsigned)((ze_blob)._296_4_);
        unsigned lim = lit < 65536u ? lit : 65536u;
        unsigned long sum = 0; unsigned nz = 0; unsigned k2;
        for (k2 = 0; k2 < lim; k2++) { sum += bp[k2]; if (bp[k2] != 0) nz++; }
        RARCH_LOG("DBGUNZ req=%s size=%u sum=%lu nz=%u head=%02x %02x %02x %02x %02x %02x %02x %02x\n",
                  param_2, lit, sum, nz,
                  lim > 0 ? bp[0] : 0, lim > 1 ? bp[1] : 0, lim > 2 ? bp[2] : 0, lim > 3 ? bp[3] : 0,
                  lim > 4 ? bp[4] : 0, lim > 5 ? bp[5] : 0, lim > 6 ? bp[6] : 0, lim > 7 ? bp[7] : 0);
      }
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
