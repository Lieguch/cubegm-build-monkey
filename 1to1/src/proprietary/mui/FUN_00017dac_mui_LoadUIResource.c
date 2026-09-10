/* ============================================================
 * mui_LoadUIResource   @ 0x00017dac   size=296B   callers=12
 * module: 02_mui_menu_ui
 * ============================================================ */

undefined4 mui_LoadUIResource(undefined4 *param_1,undefined4 param_2)

{
  int iVar1;
  undefined4 uVar2;
  void *pvVar3;
  undefined4 local_9c;
  char acStack_98 [128];
  
  uVar2 = GetWorkPath();
  sprintf(acStack_98,"%s/%s",uVar2,(&m_ui)[m_ui + 0x16] + 0x20);
  res_hz = OpenZipU(acStack_98,0,2);
  if (res_hz != 0) {
    zr = FindZipItemA(res_hz,param_2,1,&local_9c,ze);
    if (zr == 0) {
      if ((void *)*param_1 != (void *)0x0) {
        free((void *)*param_1);
      }
      uVar2 = 1;
      pvVar3 = malloc(ze._296_4_);
      iVar1 = res_hz;
      *param_1 = pvVar3;
      UnzipItem(iVar1,local_9c,pvVar3,0,3);
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
