/* ============================================================
 * mui_LoadSetting   @ 0x000171f8   size=2684B   callers=2
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_LoadSetting(void)

{
  undefined4 uVar1;
  FILE *pFVar2;
  int iVar3;
  char *pcVar4;
  int iVar5;
  undefined4 uVar6;
  size_t sVar7;
  long lVar8;
  long lVar9;
  long lVar10;
  int iVar11;
  char *__src;
  undefined4 *puVar12;
  int iVar13;
  undefined1 auStack_154 [22];
  ushort local_13e;
  undefined4 local_13c;
  ushort local_132;
  size_t local_12c;
  char acStack_128 [260];
  
  uVar1 = GetWorkPath();
  sprintf(acStack_128,"%s/setting.xml",uVar1);
  pFVar2 = fopen(acStack_128,"r");
  if (pFVar2 == (FILE *)0x0) {
    RARCH_LOG("open setting.xml fail!\n");
    tree = 0;
  }
  else {
    tree = mxmlLoadFile(0,pFVar2);
    fclose(pFVar2);
    if (tree != 0) {
      iVar3 = mxmlFindElement(tree,tree,"config",0,0,1);
      if (iVar3 == 0) {
        m_ui = 0;
        DAT_003af268 = 8;
      }
      else {
        pcVar4 = (char *)mxmlElementGetAttr(iVar3,"language");
        m_ui = strtol(pcVar4,(char **)0x0,10);
        pcVar4 = (char *)mxmlElementGetAttr(iVar3,"volume");
        DAT_003af268 = strtol(pcVar4,(char **)0x0,10);
      }
      iVar3 = mxmlFindElement(tree,tree,"defaultlanguage",0,0,1);
      if (iVar3 == 0) {
        DAT_003af310 = 0;
      }
      else {
        DAT_003af310 = strtol(*(char **)(*(int *)(iVar3 + 0x10) + 0x1c),(char **)0x0,10);
      }
      if (tree != 0) {
        iVar3 = mxmlFindElement(tree,tree,"sound",0,0,1);
        if (iVar3 != 0) {
          iVar5 = mxmlFindElement(iVar3,tree,&DAT_002dccf4,0,0,1);
          if (iVar5 != 0) {
            uVar1 = GetWorkPath();
            uVar6 = mxmlElementGetAttr(iVar5,&DAT_002dbd74);
            sprintf(acStack_128,"%s/%s",uVar1,uVar6);
            pFVar2 = fopen(acStack_128,"rb");
            if (pFVar2 != (FILE *)0x0) {
              fseek(pFVar2,0,2);
              sVar7 = ftell(pFVar2);
              rewind(pFVar2);
              mui_MenuMusic._0_4_ = malloc(sVar7 + 1);
              fread((void *)mui_MenuMusic._0_4_,sVar7,1,pFVar2);
              fclose(pFVar2);
              mui_MenuMusic._28_4_ = sVar7 + mui_MenuMusic._0_4_;
              mui_MenuMusic._4_4_ = 1;
              mui_MenuMusic._8_4_ = 1;
              mui_MenuMusic._32_4_ = 0;
              mui_MenuMusic._12_4_ = 1;
              mui_MenuMusic._20_4_ = 1;
              mui_MenuMusic._16_4_ = 0x5622;
              mui_MenuMusic._24_4_ = mui_MenuMusic._0_4_;
            }
          }
          iVar5 = mxmlFindElement(iVar3,tree,"effect0",0,0,1);
          if (iVar5 != 0) {
            uVar1 = GetWorkPath();
            uVar6 = mxmlElementGetAttr(iVar5,&DAT_002dbd74);
            sprintf(acStack_128,"%s/%s",uVar1,uVar6);
            pFVar2 = fopen(acStack_128,"rb");
            if (pFVar2 != (FILE *)0x0) {
              fread(auStack_154,1,0x2c,pFVar2);
              sVar7 = local_12c;
              mui_Effect0._0_4_ = malloc(local_12c + 1);
              fread((void *)mui_Effect0._0_4_,sVar7,1,pFVar2);
              fclose(pFVar2);
              mui_Effect0._32_4_ = 0;
              mui_Effect0._8_4_ = (local_132 >> 3) - 1;
              mui_Effect0._12_4_ = local_13e - 1;
              mui_Effect0._4_4_ = 0;
              mui_Effect0._28_4_ = local_12c + mui_Effect0._0_4_;
              mui_Effect0._20_4_ = 0;
              mui_Effect0._16_4_ = local_13c;
              mui_Effect0._24_4_ = mui_Effect0._0_4_;
            }
          }
          iVar3 = mxmlFindElement(iVar3,tree,"effect1",0,0,1);
          if (iVar3 != 0) {
            uVar1 = GetWorkPath();
            uVar6 = mxmlElementGetAttr(iVar3,&DAT_002dbd74);
            sprintf(acStack_128,"%s/%s",uVar1,uVar6);
            pFVar2 = fopen(acStack_128,"rb");
            if (pFVar2 != (FILE *)0x0) {
              fread(auStack_154,1,0x2c,pFVar2);
              sVar7 = local_12c;
              mui_Effect1._0_4_ = malloc(local_12c + 1);
              fread((void *)mui_Effect1._0_4_,sVar7,1,pFVar2);
              fclose(pFVar2);
              mui_Effect1._32_4_ = 0;
              mui_Effect1._8_4_ = (local_132 >> 3) - 1;
              mui_Effect1._12_4_ = local_13e - 1;
              mui_Effect1._4_4_ = 0;
              mui_Effect1._28_4_ = local_12c + mui_Effect1._0_4_;
              mui_Effect1._20_4_ = 0;
              mui_Effect1._16_4_ = local_13c;
              mui_Effect1._24_4_ = mui_Effect1._0_4_;
            }
          }
        }
        DAT_003af30c = 0;
        memset(&DAT_003af2bc,0,0x50);
        iVar3 = mxmlFindElement(tree,tree,"filebrowser",0,0,1);
        if (iVar3 == 0) {
          DAT_003af748 = 0x6d6f722f;
          DAT_003af74c = 0x73;
        }
        else {
          strcpy((char *)&DAT_003af748,*(char **)(*(int *)(iVar3 + 0x10) + 0x1c));
        }
        for (iVar3 = mxmlFindElement(tree,tree,"joystick",0,0,1); iVar3 != 0;
            iVar3 = mxmlFindElement(iVar3,iVar5,"joystick",0,0,1)) {
          pcVar4 = (char *)mxmlElementGetAttr(iVar3,"index");
          lVar8 = strtol(pcVar4,(char **)0x0,10);
          pcVar4 = (char *)mxmlElementGetAttr(iVar3,"button");
          lVar9 = strtol(pcVar4,(char **)0x0,10);
          pcVar4 = (char *)mxmlElementGetAttr(iVar3,"value");
          lVar10 = strtol(pcVar4,(char **)0x0,10);
          iVar5 = tree;
          *(long *)(USB_Table + (lVar8 * 0x14 + lVar9) * 4) = lVar10;
        }
        for (iVar3 = mxmlFindElement(tree,tree,"cores",0,0,1); iVar3 != 0;
            iVar3 = mxmlFindElement(iVar3,tree,"cores",0,0,1)) {
          pcVar4 = (char *)mxmlElementGetAttr(iVar3,"extname");
          iVar13 = 0;
          iVar5 = 0;
          while ((&default_core_list)[iVar13] != '\0') {
            iVar11 = strcmp(&default_core_list + iVar13,pcVar4);
            if (iVar11 == 0) {
              pcVar4 = (char *)mxmlElementGetAttr(iVar3,&DAT_002dcd5c);
              if (pcVar4 != (char *)0x0) {
                lVar8 = strtol(pcVar4,(char **)0x0,10);
                *(long *)(&DAT_003b0274 + iVar5 * 0x44) = lVar8;
                pcVar4 = (char *)mxmlElementGetAttr(iVar3,"corename");
                strcpy(&DAT_003b0278 + iVar13,pcVar4);
              }
              goto LAB_000178ec;
            }
            iVar5 = iVar5 + 1;
            iVar13 = iVar13 + 0x44;
            if (iVar5 == 100) goto LAB_000178ec;
          }
          iVar13 = iVar5 * 0x44;
          strcpy(&default_core_list + iVar13,pcVar4);
          pcVar4 = (char *)mxmlElementGetAttr(iVar3,&DAT_002dcd5c);
          if (pcVar4 != (char *)0x0) {
            lVar8 = strtol(pcVar4,(char **)0x0,10);
            *(long *)(&DAT_003b0274 + iVar13) = lVar8;
            pcVar4 = (char *)mxmlElementGetAttr(iVar3,"corename");
            strcpy(&DAT_003b0278 + iVar13,pcVar4);
          }
          iVar5 = iVar5 * 0x44;
          (&DAT_003b0298)[iVar5] = 0;
          *(undefined4 *)(&DAT_003b02b8 + iVar5) = 0;
          (&DAT_003b02bc)[iVar5] = 0;
LAB_000178ec:
        }
        iVar3 = mxmlFindElement(tree,tree,&DAT_002dcd50,0,0,1);
        iVar5 = DAT_003af30c;
        iVar13 = tree;
        while (DAT_003af30c = iVar5, tree = iVar13, iVar3 != 0) {
          pcVar4 = malloc(0x44);
          (&m_ui)[iVar5 + 0x16] = (long)pcVar4;
          __src = (char *)mxmlElementGetAttr(iVar3,&DAT_002dcd70);
          strcpy(pcVar4,__src);
          iVar5 = (&m_ui)[DAT_003af30c + 0x16];
          pcVar4 = (char *)mxmlElementGetAttr(iVar3,"filename");
          strcpy((char *)(iVar5 + 0x20),pcVar4);
          iVar13 = (&m_ui)[DAT_003af30c + 0x16];
          pcVar4 = (char *)mxmlElementGetAttr(iVar3,"gamelist");
          lVar8 = strtol(pcVar4,(char **)0x0,10);
          iVar5 = tree;
          DAT_003af30c = DAT_003af30c + 1;
          *(long *)(iVar13 + 0x40) = lVar8;
          iVar3 = mxmlFindElement(iVar3,iVar5,&DAT_002dcd50,0,0,1);
          iVar5 = DAT_003af30c;
          iVar13 = tree;
        }
        if (iVar5 == 0) {
          puVar12 = malloc(0x44);
          DAT_003af2bc = puVar12;
          *puVar12 = 0xe480aee7;
          puVar12[1] = 0xb8e493bd;
          puVar12[2] = 0x8796e6ad;
          *(undefined1 *)(puVar12 + 3) = 0;
          puVar12[8] = 0x635f6975;
          puVar12[9] = 0x697a2e6e;
          *(undefined2 *)(puVar12 + 10) = 0x70;
          pcVar4 = malloc(0x44);
          puVar12[0x10] = 0;
          iVar13 = tree;
          DAT_003af30c = 2;
          DAT_003af2c0 = pcVar4;
          builtin_strncpy(pcVar4,"ENGLISH",8);
          builtin_strncpy(pcVar4 + 0x20,"ui_en.zip",10);
        }
        if (iVar13 != 0) {
          mxmlDelete(iVar13);
          tree = 0;
        }
      }
    }
  }
  pcVar4 = stpcpy(acStack_128,work_path);
  builtin_strncpy(pcVar4,"cores/filelist.xml",0x13);
  pFVar2 = fopen(acStack_128,"r");
  if (pFVar2 != (FILE *)0x0) {
    filelist_tree = mxmlLoadFile(0,pFVar2);
    fclose(pFVar2);
    return;
  }
  RARCH_LOG("open cores/filelist.xml fail!\n");
  filelist_tree = 0;
  return;
}
