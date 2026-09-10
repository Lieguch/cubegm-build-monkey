/* ============================================================
 * mui_InitFont   @ 0x0001ecac   size=612B   callers=2
 * module: 02_mui_menu_ui
 * ============================================================ */

void mui_InitFont(void)

{
  int iVar1;
  undefined4 uVar2;
  FILE *__stream;
  size_t __size;
  undefined4 local_11c;
  char acStack_118 [260];
  
  iVar1 = strcmp(fontname,(char *)((&m_ui)[m_ui + 0x16] + 0x20));
  if (iVar1 != 0) {
    uVar2 = GetWorkPath();
    sprintf(acStack_118,"%s/%s",uVar2,(&m_ui)[m_ui + 0x16] + 0x20);
    res_hz = OpenZipU(acStack_118,0,2);
    if (res_hz != 0) {
      zr = FindZipItemA(res_hz,&DAT_002dcea4,1,&local_11c,ze);
      if (zr == 0) {
        if (fontbuffer != (void *)0x0) {
          free(fontbuffer);
        }
        fontbuffer = malloc(ze._296_4_);
        UnzipItem(res_hz,local_11c,fontbuffer,0,3);
        strcpy(fontname,(char *)((&m_ui)[m_ui + 0x16] + 0x20));
        CloseZipU(res_hz);
        goto LAB_0001ed0c;
      }
      RARCH_LOG("find font.ttf in %s fail\n",acStack_118);
      CloseZipU(res_hz);
    }
  }
  iVar1 = strcmp(fontname,"font.ttf");
  if (iVar1 != 0) {
    uVar2 = GetWorkPath();
    sprintf(acStack_118,"%s/font.ttf",uVar2);
    __stream = fopen(acStack_118,"rb");
    if (__stream == (FILE *)0x0) {
      RARCH_LOG("Open font file failed.");
      return;
    }
    fseek(__stream,0,2);
    __size = ftell(__stream);
    if (fontbuffer != (void *)0x0) {
      free(fontbuffer);
    }
    fontbuffer = malloc(__size);
    fseek(__stream,0,0);
    fread(fontbuffer,1,__size,__stream);
    fclose(__stream);
    fontname._0_4_ = 0x746e6f66;
    fontname._4_4_ = 0x6674742e;
    fontname[8] = 0;
  }
LAB_0001ed0c:
  stbtt_InitFont(font,fontbuffer,0);
  return;
}
