/* ============================================================
 * mui_LoadConfig   @ 0x0001f580   size=6224B   callers=2
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* WARNING: Type propagation algorithm not settling */

void mui_LoadConfig(void)

{
  gh_u4 uVar1;
  gh_u4 uVar2;
  size_t sVar3;
  char *pcVar4;
  void *pvVar5;
  int iVar6;
  int iVar7;
  gh_u4 *puVar8;
  int iVar9;
  int *piVar10;
  char *pcVar11;
  int *piVar12;
  gh_u1 *puVar13;
  gh_u4 *puVar14;
  int iVar15;
  int local_1a4;
  int local_1a0;
  char *local_19c;
  gh_u4 *local_198;
  size_t local_194 [2];
  char acStack_18c [100];
  char local_128 [260];
  
  uVar1 = libiconv_open("utf-8","GB2312");
  uVar2 = (gh_u4)GetWorkPath();
  sprintf(acStack_18c,"%s/%s",uVar2,(&m_ui)[m_ui + 0x16] + 0x20);
  uVar2 = get_items_from_zipfile(acStack_18c,(char *)configitems);
  get_value_from_items("GameSum_rect",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af314 = 0x3d4;
    DAT_003af318 = 0xe;
    DAT_003af31c = 0x44c;
    DAT_003af320 = 0x36;
  }
  else {
    __isoc99_sscanf(local_128,"%d,%d,%d,%d",&DAT_003af314,&DAT_003af318,&DAT_003af31c,&DAT_003af320)
    ;
    DAT_003af31c = DAT_003af31c + DAT_003af314;
    DAT_003af320 = DAT_003af320 + DAT_003af318;
  }
  get_value_from_items("GameSum_fontsize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af324 = 0x20;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af324);
  }
  get_value_from_items("GameSum_fontcolor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af328 = 0xffff;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af328);
  }
  get_value_from_items("TypeName_Name",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    puVar8 = &DAT_003af328;
    puVar14 = (gh_u4 *)&mui_typename;
    pcVar11 = "ARCADE";
    while( true ) {
      if ((void *)puVar8[1] != (void *)0x0) {
        free((void *)puVar8[1]);
      }
      sVar3 = strlen(pcVar11);
      pcVar4 = malloc(sVar3 + 1);
      puVar8 = puVar8 + 1;
      *puVar8 = (gh_u4)pcVar4;
      strcpy(pcVar4,pcVar11);
      if (puVar8 == (gh_u4 *)0x3af34c) break;
      puVar14 = puVar14 + 1;
      pcVar11 = (char *)*puVar14;
    }
  }
  else {
    iVar15 = 0;
    puVar8 = &DAT_003af328;
    pcVar11 = local_128;
    while( true ) {
      pcVar4 = strchr(pcVar11,0x2c);
      if (pcVar4 == (char *)0x0) break;
      puVar8 = puVar8 + 1;
      pvVar5 = (void *)*puVar8;
      iVar15 = iVar15 + 1;
      *pcVar4 = '\0';
      if (pvVar5 != (void *)0x0) {
        free(pvVar5);
      }
      local_198 = calloc(0x20,1);
      *puVar8 = (gh_u4)local_198;
      local_19c = pcVar11;
      local_194[0] = strlen(pcVar11);
      local_194[1] = 0x20;
      libiconv(uVar1,&local_19c,local_194,&local_198,local_194 + 1);
      pcVar11 = pcVar4 + 1;
    }
    sVar3 = strlen(pcVar11);
    pvVar5 = malloc(sVar3 + 1);
    (&m_ui)[iVar15 + 0x32] = (int)pvVar5;
    memcpy(pvVar5,pcVar11,sVar3 + 1);
  }
  get_value_from_items("TypeName_rect",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af37c = 0x276;
    DAT_003af380 = 0xe;
    DAT_003af384 = 0x35c;
    DAT_003af388 = 0x36;
  }
  else {
    __isoc99_sscanf(local_128,"%d,%d,%d,%d",&DAT_003af37c,&DAT_003af380,&DAT_003af384,&DAT_003af388)
    ;
    DAT_003af384 = DAT_003af384 + DAT_003af37c;
    DAT_003af388 = DAT_003af388 + DAT_003af380;
  }
  get_value_from_items("TypeName_fontsize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af38c = 0x24;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af38c);
  }
  get_value_from_items("TypeName_fontcolor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af390 = 0xffff;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af390);
  }
  get_value_from_items("GameList_count",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af394 = 0xb;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af394);
  }
  get_value_from_items("GameList_fontsize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    local_1a4 = 0x20;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&local_1a4);
  }
  get_value_from_items("GameList_fontcolor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    local_1a0 = 0xffff;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&local_1a0);
  }
  if (0 < DAT_003af394) {
    iVar15 = 0;
    piVar12 = &mui_Rect;
    piVar10 = &DAT_003af3a0;
    do {
      iVar15 = iVar15 + 1;
      sprintf(local_128,"GameList_list_%d",iVar15);
      get_value_from_items(local_128,local_128,configitems,uVar2);
      if (local_128[0] == '\0') {
        iVar9 = *piVar12;
        iVar6 = piVar12[1];
        iVar7 = piVar12[3];
        *piVar10 = piVar12[2];
        piVar10[-1] = iVar6;
        piVar10[-2] = iVar9;
        piVar10[1] = iVar7;
      }
      else {
        __isoc99_sscanf(local_128,"%d,%d,%d,%d",piVar10 + -2,piVar10 + -1,piVar10,piVar10 + 1);
        *piVar10 = *piVar10 + piVar10[-2];
        piVar10[1] = piVar10[1] + piVar10[-1];
      }
      piVar12 = piVar12 + 4;
      piVar10[2] = local_1a4;
      piVar10[3] = local_1a0;
      piVar10 = piVar10 + 6;
    } while (iVar15 < DAT_003af394);
  }
  get_value_from_items("GameList_selectsize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af698 = 0x20;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af698);
  }
  get_value_from_items("GameList_selectcolor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af69c = 0x871c;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af69c);
  }
  get_value_from_items("GameList_starxoffset",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6a0 = 0xffffffea;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af6a0);
  }
  get_value_from_items("GameList_staryoffset",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6a4 = 0xfffffffa;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af6a4);
  }
  get_value_from_items("GameList_starsize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6a8 = 0x24;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af6a8);
  }
  get_value_from_items("GameList_starcolor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6ac = 0xffe0;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af6ac);
  }
  get_value_from_items("GameList_starcode",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6b0 = 0x8598e2;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af6b0);
  }
  get_value_from_items("Thumbnail_region",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6b8 = 0x2e0;
    DAT_003af6bc = 0xa0;
    DAT_003af6c0 = 0x1e0;
    DAT_003af6c4 = 0x140;
  }
  else {
    __isoc99_sscanf(local_128,"%d,%d,%d,%d",&DAT_003af6b8,&DAT_003af6bc,&DAT_003af6c0,&DAT_003af6c4)
    ;
  }
  get_value_from_items("SearchInput_rect",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6c8 = 0x2cc;
    DAT_003af6cc = 100;
    DAT_003af6d0 = 0x496;
    DAT_003af6d4 = 0x88;
  }
  else {
    __isoc99_sscanf(local_128,"%d,%d,%d,%d",&DAT_003af6c8,&DAT_003af6cc,&DAT_003af6d0,&DAT_003af6d4)
    ;
    DAT_003af6d0 = DAT_003af6d0 + DAT_003af6c8;
    DAT_003af6d4 = DAT_003af6d4 + DAT_003af6cc;
  }
  get_value_from_items("SearchInput_fontsize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6d8 = 0x20;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af6d8);
  }
  get_value_from_items("SearchInput_fontcolor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6dc = 0xffff;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af6dc);
  }
  get_value_from_items("SearchInput_CursorSize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6e0 = 0x20;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af6e0);
  }
  get_value_from_items("SearchInput_CursorColor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6e4 = 0x18df;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af6e4);
  }
  get_value_from_items("SearchInput_CursorCode",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6e8 = 0x49;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af6e8);
  }
  puVar13 = m_movetab;
  iVar15 = 0;
  do {
    while( true ) {
      iVar9 = iVar15 + 1;
      sprintf(local_128,"SearchInput_MoveTable_%d",iVar15);
      get_value_from_items(local_128,local_128,configitems,uVar2);
      iVar15 = iVar9;
      if (local_128[0] == '\0') break;
      __isoc99_sscanf(local_128,"%d,%d,%d,%d,%d",puVar13,puVar13 + 4,puVar13 + 8,puVar13 + 0xc,
                      puVar13 + 0x10);
      puVar13 = puVar13 + 0x14;
      if (iVar9 == 0x2d) goto LAB_0001fdc8;
    }
    puVar13 = puVar13 + 0x14;
  } while (iVar9 != 0x2d);
LAB_0001fdc8:
  get_value_from_items("Setting_CheckCode",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af708 = 0x8e97e2;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,(gh_byte *)&DAT_003af708);
  }
  get_value_from_items("Setting_UncheckCode",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af70f = 0x8b97e2;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,(gh_byte *)&DAT_003af70f);
  }
  get_value_from_items("Setting_CheckColor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af718 = 0xffff;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af718);
  }
  get_value_from_items("Setting_CheckSize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af71c = 0x36;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af71c);
  }
  get_value_from_items("Setting_LanguageRect",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af6f0 = 0x212;
    DAT_003af6f4 = 0x78;
    DAT_003af6f8 = 0x140;
    DAT_003af6fc = 0x2a;
  }
  else {
    __isoc99_sscanf(local_128,"%d,%d,%d,%d",&DAT_003af6f0,&DAT_003af6f4,&DAT_003af6f8,&DAT_003af6fc)
    ;
  }
  get_value_from_items("Setting_LanguageFontColor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af704 = 0xffff;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af704);
  }
  get_value_from_items("Setting_LanguageFontSize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af700 = 0x20;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af700);
  }
  get_value_from_items("Setting_FilelistRect",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af720 = 0x1fe;
    DAT_003af724 = 0x46;
    DAT_003af728 = 0x2ee;
    DAT_003af72c = 600;
  }
  else {
    __isoc99_sscanf(local_128,"%d,%d,%d,%d",&DAT_003af720,&DAT_003af724,&DAT_003af728,&DAT_003af72c)
    ;
  }
  get_value_from_items("Setting_FilelistFontSize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af730 = 0x2a;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af730);
  }
  get_value_from_items("Setting_FilelistFontColor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af734 = 0xffff;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af734);
  }
  get_value_from_items("Setting_FilelistSelectFontSize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af738 = 0x2a;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af738);
  }
  get_value_from_items("Setting_FilelistSelectFontColor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af73c = 0xffe0;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af73c);
  }
  get_value_from_items("Setting_FilelistPageLines",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af740 = 0xd;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af740);
  }
  get_value_from_items("Setting_FilelistLineHigh",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af744 = 0x2e;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af744);
  }
  get_value_from_items("Setting_RecoverRect",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af788 = 0x212;
    DAT_003af78c = 0x78;
    DAT_003af790 = 0x208;
    DAT_003af794 = 0x32;
  }
  else {
    __isoc99_sscanf(local_128,"%d,%d,%d,%d",&DAT_003af788,&DAT_003af78c,&DAT_003af790,&DAT_003af794)
    ;
  }
  get_value_from_items("Setting_RecoverFontSize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af798 = 0x20;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af798);
  }
  get_value_from_items("Setting_RecoverFontColor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af79c = 0xffff;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af79c);
  }
  get_value_from_items("Setting_RecoverInfo1",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    if (m_ui == 1) {
      DAT_003af7a0._0_1_ = -0x18;
      DAT_003af7a0._1_1_ = -0x53;
      DAT_003af7a0._2_1_ = -0x5a;
      DAT_003af7a0._3_1_ = -0x1b;
      DAT_003af7a4._0_1_ = -0x6f;
      DAT_003af7a4._1_1_ = -0x76;
      DAT_003af7a4._2_1_ = ':';
      DAT_003af7a4._3_1_ = -0x1a;
      DAT_003af7a8._0_1_ = -0x7f;
      DAT_003af7a8._1_1_ = -0x5e;
      DAT_003af7a8._2_1_ = -0x1b;
      DAT_003af7a8._3_1_ = -0x5c;
      DAT_003af7ac._0_1_ = -0x73;
      DAT_003af7ac._1_1_ = -0x17;
      DAT_003af7ac._2_1_ = -0x45;
      DAT_003af7ac._3_1_ = -0x68;
      DAT_003af7b0._0_1_ = -0x18;
      DAT_003af7b0._1_1_ = -0x52;
      DAT_003af7b0._2_1_ = -0x5c;
      DAT_003af7b0._3_1_ = -0x1a;
      DAT_003af7b4._0_1_ = -0x77;
      DAT_003af7b4._1_1_ = -0x80;
      DAT_003af7b4._2_1_ = -0x1a;
      DAT_003af7b4._3_1_ = -100;
      DAT_003af7b8._0_1_ = -0x77;
      DAT_003af7b8._1_1_ = -0x1a;
      DAT_003af7b8._2_1_ = -0x6b;
      DAT_003af7b8._3_1_ = -0x50;
      DAT_003af7bc._0_1_ = -0x1a;
      DAT_003af7bc._1_1_ = -0x73;
      DAT_003af7bc._2_1_ = -0x52;
      DAT_003af7bc._3_1_ = -0x1c;
      DAT_003af7c0._0_1_ = -0x44;
      DAT_003af7c0._1_1_ = -0x66;
      DAT_003af7c0._2_1_ = -0x18;
      DAT_003af7c0._3_1_ = -0x5e;
      DAT_003af7c4._0_1_ = -0x55;
      DAT_003af7c4._1_1_ = -0x1a;
      DAT_003af7c4._2_1_ = -0x48;
      DAT_003af7c4._3_1_ = -0x7b;
      DAT_003af7c8._0_1_ = -0x19;
      DAT_003af7c8._1_1_ = -0x57;
      DAT_003af7c8._2_1_ = -0x46;
      DAT_003af7c8._3_1_ = '!';
      DAT_003af7cc._u32 = DAT_003af7cc._u32 & 0xffffff00;
    }
    else {
      DAT_003af7a0._0_1_ = 'W';
      DAT_003af7a0._1_1_ = 'a';
      DAT_003af7a0._2_1_ = 'r';
      DAT_003af7a0._3_1_ = 'n';
      DAT_003af7a4._0_1_ = 'i';
      DAT_003af7a4._1_1_ = 'n';
      DAT_003af7a4._2_1_ = 'g';
      DAT_003af7a4._3_1_ = ':';
      DAT_003af7a8._0_1_ = 'R';
      DAT_003af7a8._1_1_ = 'e';
      DAT_003af7a8._2_1_ = 's';
      DAT_003af7a8._3_1_ = 't';
      DAT_003af7ac._0_1_ = 'o';
      DAT_003af7ac._1_1_ = 'r';
      DAT_003af7ac._2_1_ = 'e';
      DAT_003af7ac._3_1_ = ' ';
      DAT_003af7b0._0_1_ = 't';
      DAT_003af7b0._1_1_ = 'h';
      DAT_003af7b0._2_1_ = 'e';
      DAT_003af7b0._3_1_ = ' ';
      DAT_003af7b4._0_1_ = 'd';
      DAT_003af7b4._1_1_ = 'e';
      DAT_003af7b4._2_1_ = 'f';
      DAT_003af7b4._3_1_ = 'a';
      DAT_003af7b8._0_1_ = 'u';
      DAT_003af7b8._1_1_ = 'l';
      DAT_003af7b8._2_1_ = 't';
      DAT_003af7b8._3_1_ = ' ';
      DAT_003af7bc._0_1_ = 'a';
      DAT_003af7bc._1_1_ = 'n';
      DAT_003af7bc._2_1_ = 'd';
      DAT_003af7bc._3_1_ = ' ';
      DAT_003af7c0._0_1_ = 'a';
      DAT_003af7c0._1_1_ = 'l';
      DAT_003af7c0._2_1_ = 'l';
      DAT_003af7c0._3_1_ = ' ';
      DAT_003af7c4._0_1_ = 'd';
      DAT_003af7c4._1_1_ = 'a';
      DAT_003af7c4._2_1_ = 't';
      DAT_003af7c4._3_1_ = 'a';
      DAT_003af7c8._0_1_ = ' ';
      DAT_003af7c8._1_1_ = 'w';
      DAT_003af7c8._2_1_ = 'i';
      DAT_003af7c8._3_1_ = 'l';
      DAT_003af7cc._0_1_ = 'l';
      DAT_003af7cc._1_1_ = ' ';
      DAT_003af7cc._2_1_ = 'b';
      DAT_003af7cc._3_1_ = 'e';
      DAT_003af7d0._0_1_ = ' ';
      DAT_003af7d0._1_1_ = 'c';
      DAT_003af7d0._2_1_ = 'l';
      DAT_003af7d0._3_1_ = 'e';
      DAT_003af7d4._0_1_ = 'a';
      DAT_003af7d4._1_1_ = 'r';
      DAT_003af7d4._2_1_ = 'e';
      DAT_003af7d4._3_1_ = 'd';
      DAT_003af7d8 = 0x21;
    }
  }
  else {
    local_198 = (gh_u4 *)&DAT_003af7a0;
    local_19c = local_128;
    local_194[0] = strlen(local_128);
    local_194[1] = 0x40;
    libiconv(uVar1,&local_19c,local_194,&local_198,local_194 + 1);
  }
  get_value_from_items("Setting_RecoverInfo2",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    if (m_ui == 1) {
      DAT_003af7e0._0_1_ = -0x1a;
      DAT_003af7e0._1_1_ = -0x74;
      DAT_003af7e0._2_1_ = -0x77;
      DAT_003af7e0._3_1_ = 'A';
      DAT_003af7e4._0_1_ = -0x17;
      DAT_003af7e4._1_1_ = -0x6c;
      DAT_003af7e4._2_1_ = -0x52;
      DAT_003af7e4._3_1_ = -0x19;
      DAT_003af7e8._0_1_ = -0x5f;
      DAT_003af7e8._1_1_ = -0x52;
      DAT_003af7e8._2_1_ = -0x18;
      DAT_003af7e8._3_1_ = -0x52;
      DAT_003af7ec._0_1_ = -0x5c;
      DAT_003af7ec._1_1_ = -0x1a;
      DAT_003af7ec._2_1_ = -0x77;
      DAT_003af7ec._3_1_ = -0x59;
      DAT_003af7f0._0_1_ = -0x18;
      DAT_003af7f0._1_1_ = -0x5f;
      DAT_003af7f0._2_1_ = -0x74;
      DAT_003af7f0._3_1_ = -0x1a;
      DAT_003af7f4._0_1_ = -0x7f;
      DAT_003af7f4._1_1_ = -0x5e;
      DAT_003af7f4._2_1_ = -0x1b;
      DAT_003af7f4._3_1_ = -0x5c;
      DAT_003af7f8._0_1_ = -0x73;
      DAT_003af7f8._1_1_ = -0x17;
      DAT_003af7f8._2_1_ = -0x45;
      DAT_003af7f8._3_1_ = -0x68;
      DAT_003af7fc._0_1_ = -0x18;
      DAT_003af7fc._1_1_ = -0x52;
      DAT_003af7fc._2_1_ = -0x5c;
      DAT_003af7fc._3_1_ = '\0';
    }
    else {
      DAT_003af7e0._0_1_ = 'C';
      DAT_003af7e0._1_1_ = 'o';
      DAT_003af7e0._2_1_ = 'n';
      DAT_003af7e0._3_1_ = 'f';
      DAT_003af7e4._0_1_ = 'i';
      DAT_003af7e4._1_1_ = 'r';
      DAT_003af7e4._2_1_ = 'm';
      DAT_003af7e4._3_1_ = ' ';
      DAT_003af7e8._0_1_ = 't';
      DAT_003af7e8._1_1_ = 'o';
      DAT_003af7e8._2_1_ = ' ';
      DAT_003af7e8._3_1_ = 'p';
      DAT_003af7ec._0_1_ = 'r';
      DAT_003af7ec._1_1_ = 'e';
      DAT_003af7ec._2_1_ = 's';
      DAT_003af7ec._3_1_ = 's';
      DAT_003af7f0._0_1_ = ' ';
      DAT_003af7f0._1_1_ = 'A';
      DAT_003af7f0._2_1_ = ' ';
      DAT_003af7f0._3_1_ = 't';
      DAT_003af7f4._0_1_ = 'o';
      DAT_003af7f4._1_1_ = ' ';
      DAT_003af7f4._2_1_ = 'r';
      DAT_003af7f4._3_1_ = 'e';
      DAT_003af7f8._0_1_ = 's';
      DAT_003af7f8._1_1_ = 't';
      DAT_003af7f8._2_1_ = 'o';
      DAT_003af7f8._3_1_ = 'r';
      DAT_003af7fc._0_1_ = 'e';
      DAT_003af7fc._1_1_ = ' ';
      DAT_003af7fc._2_1_ = 't';
      DAT_003af7fc._3_1_ = 'h';
      DAT_003af800._0_1_ = 'e';
      DAT_003af800._1_1_ = ' ';
      DAT_003af800._2_1_ = 'd';
      DAT_003af800._3_1_ = 'e';
      DAT_003af804._0_1_ = 'f';
      DAT_003af804._1_1_ = 'a';
      DAT_003af804._2_1_ = 'u';
      DAT_003af804._3_1_ = 'l';
      DAT_003af808 = 0x74;
    }
  }
  else {
    local_198 = (gh_u4 *)&DAT_003af7e0;
    local_19c = local_128;
    local_194[0] = strlen(local_128);
    local_194[1] = 0x40;
    libiconv(uVar1,&local_19c,local_194,&local_198,local_194 + 1);
  }
  get_value_from_items("Game_ThumbnailRect",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af820 = 700;
    DAT_003af824 = 0x50;
    DAT_003af828 = 0x140;
    DAT_003af82c = 0xf0;
  }
  else {
    __isoc99_sscanf(local_128,"%d,%d,%d,%d",&DAT_003af820,&DAT_003af824,&DAT_003af828,&DAT_003af82c)
    ;
  }
  get_value_from_items("Game_VideoRect",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af830 = 0x212;
    DAT_003af834 = 0x1a4;
    DAT_003af838 = 0x140;
    DAT_003af83c = 0x2a;
  }
  else {
    __isoc99_sscanf(local_128,"%d,%d,%d,%d",&DAT_003af830,&DAT_003af834,&DAT_003af838,&DAT_003af83c)
    ;
  }
  get_value_from_items("Game_VideoFontSize",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af840 = 0x20;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af840);
  }
  get_value_from_items("Game_VideoFontColor",local_128,configitems,uVar2);
  if (local_128[0] == '\0') {
    DAT_003af844 = 0xffff;
  }
  else {
    __isoc99_sscanf(local_128,DAT_002dcf4c,&DAT_003af844);
  }
  piVar10 = (int *)(m_joysticktab + 0x6c);
  iVar15 = 0;
  do {
    while( true ) {
      iVar9 = iVar15 + 1;
      sprintf(local_128,"Game_JoystickTab%d",iVar15);
      get_value_from_items(local_128,local_128,configitems,uVar2);
      iVar15 = iVar9;
      if (local_128[0] == '\0') break;
      __isoc99_sscanf(local_128,"%d,%d,%d,%d,%d,%d,%d,%d",piVar10 + -2,piVar10 + -1,piVar10,
                      piVar10 + 1,piVar10 + 2,piVar10 + 3,piVar10 + 4,piVar10 + 5);
      *piVar10 = *piVar10 + piVar10[-2];
      piVar10[1] = piVar10[1] + piVar10[-1];
      piVar10 = piVar10 + 0x21;
      if (iVar9 == 7) goto LAB_000204ec;
    }
    piVar10 = piVar10 + 0x21;
  } while (iVar9 != 7);
LAB_000204ec:
  libiconv_close((void *)uVar1);
  return;
}
