/* ============================================================
 * mui_type_file_list   @ 0x00018c08   size=992B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

int mui_type_file_list(int param_1,byte *param_2)

{
  byte *pbVar1;
  undefined4 uVar2;
  byte bVar3;
  undefined1 *puVar4;
  int iVar5;
  int iVar6;
  int iVar7;
  int iVar8;
  char *local_100;
  byte *local_fc;
  undefined1 *local_f8;
  undefined1 *local_f4;
  byte local_f0 [100];
  undefined4 local_8c [26];
  
  uVar2 = libiconv_open("utf-8","GB2312");
  if (0 < DAT_003af394) {
    puVar4 = &file_info_list;
    iVar6 = DAT_003af394 * 0x404;
    do {
      *puVar4 = 0;
      *(undefined4 *)(puVar4 + 0x100) = 0;
      puVar4[0x104] = 0;
      puVar4[0x184] = 0;
      puVar4[0x204] = 0;
      puVar4[0x284] = 0;
      puVar4 = puVar4 + 0x404;
    } while (puVar4 != &file_info_list + iVar6);
  }
  iVar6 = 0;
  bVar3 = *param_2;
  iVar7 = 0;
  iVar8 = 0;
  pbVar1 = local_f0;
joined_r0x00018cbc:
  while( true ) {
    while (bVar3 == 0xd) {
      param_2 = param_2 + 1;
      bVar3 = *param_2;
    }
    if (0xd < bVar3) break;
    if ((bVar3 == 0) || (bVar3 == 10)) goto LAB_00018cfc;
LAB_00018cd4:
    *pbVar1 = bVar3;
    param_2 = param_2 + 1;
    bVar3 = *param_2;
    pbVar1 = pbVar1 + 1;
  }
  if ((bVar3 != 0x2c) && (bVar3 != 0x3b)) goto LAB_00018cd4;
LAB_00018cfc:
  if ((iVar7 < param_1) || (DAT_003af394 <= iVar8)) {
LAB_00018dc0:
    if (bVar3 == 10) {
      iVar7 = iVar7 + 1;
      iVar6 = 0;
      param_2 = param_2 + 1;
      bVar3 = *param_2;
      pbVar1 = local_f0;
      goto joined_r0x00018cbc;
    }
  }
  else if (iVar6 == 0) {
    if (local_f0 < pbVar1) {
      *pbVar1 = 0;
      sprintf((char *)local_8c,"%03d/%s",DAT_003af270,local_f0);
      local_f8 = (undefined1 *)0x64;
      local_f4 = (undefined1 *)0x100;
      local_100 = (char *)local_8c;
      local_fc = &file_info_list + iVar8 * 0x404;
      libiconv(uVar2,&local_100,&local_f8,&local_fc,&local_f4);
      (&DAT_003b2320)[iVar8 * 0x101] = DAT_003af270;
      iVar5 = IsShoucang(&file_info_list + iVar8 * 0x404);
      if (iVar5 != 0) {
        (&DAT_003b2320)[iVar8 * 0x101] = (&DAT_003b2320)[iVar8 * 0x101] | 0x80;
      }
LAB_00018e44:
      bVar3 = *param_2;
    }
    else {
      (&file_info_list)[iVar8 * 0x404] = 0;
      bVar3 = *param_2;
    }
LAB_00018d38:
    if (bVar3 == 10) {
      if ((&DAT_003b2324)[iVar8 * 0x404] == '\0') {
LAB_00018f18:
        mui_extract_basename(&DAT_003b2324 + iVar8 * 0x404,&file_info_list + iVar8 * 0x404,0x80);
      }
      iVar5 = iVar8 * 0x404;
      if ((&DAT_003b23a4)[iVar5] == '\0') {
        strcpy(&DAT_003b23a4 + iVar5,&DAT_003b2324 + iVar5);
      }
      iVar8 = iVar8 + 1;
      if ((mui_fast_lsit == 0) || (iVar8 < DAT_003af394)) {
        bVar3 = *param_2;
        goto LAB_00018dc0;
      }
      goto LAB_00018e00;
    }
  }
  else {
    if (iVar6 != 1) {
      if (iVar6 == 2) {
        if (pbVar1 <= local_f0) {
          (&DAT_003b23a4)[iVar8 * 0x404] = 0;
          goto LAB_00018e44;
        }
        local_f8 = &DAT_003b23a4 + iVar8 * 0x404;
        goto LAB_00018f8c;
      }
      goto LAB_00018d38;
    }
    if (local_f0 < pbVar1) {
      local_f8 = &DAT_003b2324 + iVar8 * 0x404;
LAB_00018f8c:
      *pbVar1 = 0;
      local_f4 = (undefined1 *)0x64;
      local_8c[0] = 0x80;
      local_fc = local_f0;
      libiconv(uVar2,&local_fc,&local_f4,&local_f8,local_8c);
      bVar3 = *param_2;
      goto LAB_00018d38;
    }
    (&DAT_003b2324)[iVar8 * 0x404] = 0;
    bVar3 = *param_2;
    if (bVar3 == 10) goto LAB_00018f18;
  }
  if (bVar3 == 0x2c || bVar3 == 0x3b) {
    iVar6 = iVar6 + 1;
    param_2 = param_2 + 1;
    bVar3 = *param_2;
    pbVar1 = local_f0;
  }
  else if (bVar3 == 0) {
    if ((&file_info_list)[iVar8 * 0x404] != '\0') {
      iVar7 = iVar7 + 1;
    }
LAB_00018e00:
    libiconv_close(uVar2);
    return iVar7;
  }
  goto joined_r0x00018cbc;
}
