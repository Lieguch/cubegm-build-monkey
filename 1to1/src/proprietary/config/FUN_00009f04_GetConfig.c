/* ============================================================
 * GetConfig   @ 0x00009f04   size=1204B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void GetConfig(void)

{
  FILE *__stream;
  undefined4 uVar1;
  int iVar2;
  char *pcVar3;
  char local_1020 [4100];
  
  sprintf(local_1020,"%s/setting.xml",work_path);
  __stream = fopen(local_1020,"r");
  if (__stream == (FILE *)0x0) {
    puts("open config.xml fail!");
    return;
  }
  uVar1 = mxmlLoadFile(0,__stream);
  fclose(__stream);
  iVar2 = mxmlFindElement(uVar1,uVar1,"displayfps",0,0,1);
  if (iVar2 != 0) {
    displayfps = strtol(*(char **)(*(int *)(iVar2 + 0x10) + 0x1c),(char **)0x0,10);
  }
  printf("displayfps:%d\n",displayfps);
  iVar2 = mxmlFindElement(uVar1,uVar1,"displaythread",0,0,1);
  if (iVar2 != 0) {
    DisplayThread = strtol(*(char **)(*(int *)(iVar2 + 0x10) + 0x1c),(char **)0x0,10);
  }
  iVar2 = mxmlFindElement(uVar1,uVar1,"softrotation",0,0,1);
  if (iVar2 != 0) {
    soft_rotation = strtol(*(char **)(*(int *)(iVar2 + 0x10) + 0x1c),(char **)0x0,10);
  }
  iVar2 = mxmlFindElement(uVar1,uVar1,"logfile",0,0,1);
  if (iVar2 != 0) {
    pcVar3 = *(char **)(*(int *)(iVar2 + 0x10) + 0x1c);
    if (*pcVar3 == '/') {
      strcpy(local_1020,pcVar3);
    }
    else {
      sprintf(local_1020,"%s%s",work_path);
    }
    if (log_file_initialized == '\0') {
      log_file_fp = stderr;
      log_file_fp = fopen(local_1020,"wb");
      if (log_file_fp == (FILE *)0x0) {
        printf("%s creat fail\n",local_1020);
        log_file_fp = stderr;
      }
      else {
        printf("%s creat\n",local_1020);
        log_file_initialized = '\x01';
      }
    }
  }
  iVar2 = mxmlFindElement(uVar1,uVar1,"savestatehotkey",0,0,1);
  if (iVar2 == 0) {
    SaveDefaultStateKey = -1;
  }
  else {
    SaveDefaultStateKey = strtol(*(char **)(*(int *)(iVar2 + 0x10) + 0x1c),(char **)0x0,10);
  }
  iVar2 = mxmlFindElement(uVar1,uVar1,"autorestore",0,0,1);
  if (iVar2 == 0) {
    AutoRestoreKey = 0;
  }
  else {
    AutoRestoreKey = strtol(*(char **)(*(int *)(iVar2 + 0x10) + 0x1c),(char **)0x0,10);
  }
  iVar2 = mxmlFindElement(uVar1,uVar1,"gamemenuhotkey",0,0,1);
  if (iVar2 == 0) {
    GameMenuHotKey = 9;
  }
  else {
    GameMenuHotKey = strtol(*(char **)(*(int *)(iVar2 + 0x10) + 0x1c),(char **)0x0,10);
  }
  if ((autorunfile[0] == '\0') && (iVar2 = mxmlFindElement(uVar1,uVar1,"autorun",0,0,1), iVar2 != 0)
     ) {
    pcVar3 = (char *)mxmlElementGetAttr(iVar2,&DAT_002dbd74);
    pcVar3 = stpcpy(local_1020,pcVar3);
    if (local_1020[0] != '\0') {
      if (local_1020[0] == '/') {
        memcpy(autorunfile,local_1020,(size_t)(pcVar3 + (1 - (int)local_1020)));
      }
      else {
        sprintf(autorunfile,"%s%s",work_path,local_1020);
      }
      pcVar3 = (char *)mxmlElementGetAttr(iVar2,"driver");
      pcVar3 = stpcpy(local_1020,pcVar3);
      if (local_1020[0] == '\0') {
        autorundriver[0] = 0;
      }
      else if (local_1020[0] == '/') {
        memcpy(autorundriver,local_1020,(size_t)(pcVar3 + (1 - (int)local_1020)));
      }
      else {
        sprintf(autorundriver,"%s%s",work_path,local_1020);
      }
    }
  }
  mxmlDelete(uVar1);
  return;
}
