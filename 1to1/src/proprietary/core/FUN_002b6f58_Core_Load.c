/* ============================================================
 * Core_Load   @ 0x002b6f58   size=900B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 Core_Load(char *param_1,undefined4 param_2)

{
  int iVar1;
  code *pcVar2;
  long lVar3;
  char local_184 [100];
  char acStack_120 [256];
  
  n_input_width = 0x140;
  n_input_height = 0xe0;
  n_input_visible_width = 0x100;
  n_input_visible_height = 0xe0;
  screen_w = 0x100;
  screen_x = 0;
  RARCH_LOG("with cores:%s\n");
  sprintf(acStack_120,"%s/cores/%s.cfg",work_path,param_2);
  memset(corecfg,0,16000);
  get_items_from_file(acStack_120,corecfg);
  sprintf(acStack_120,"%s/cores/%s",work_path,param_2);
  handle = dlopen(acStack_120,2);
  if (handle == 0) {
    RARCH_LOG("open %s fail\n",acStack_120);
    return 0;
  }
  _retro_is_support = (code *)dlsym(handle,"retro_is_support");
  if (_retro_is_support != (code *)0x0) {
    iVar1 = (*_retro_is_support)(param_1);
    if (iVar1 < 0) {
      RARCH_LOG("unsupport this game rom\n");
      dlclose(handle);
      return 0;
    }
    RARCH_LOG("support this game rom\n");
  }
  iVar1 = Load_Proc1(&DAT_002dbcb4);
  if (iVar1 == 0) {
    return 0;
  }
  run_process("retro_set_progress_callback",progress);
  strcpy(fileName,param_1);
  if ((short)Filetype == 0x800) {
    _retro_set_device = (code *)dlsym(handle,"retro_set_controller_port_device");
    if (_retro_set_device == (code *)0x0) {
      RARCH_LOG("find retro_set_controller_port_device process fail \n");
    }
    else {
      get_value_from_items("device0_type",local_184,items,0x40);
      pcVar2 = _retro_set_device;
      if (local_184[0] != '\0') {
        lVar3 = strtol(local_184,(char **)0x0,10);
        (*pcVar2)(0,lVar3);
      }
      get_value_from_items("device1_type",local_184,items,0x40);
      pcVar2 = _retro_set_device;
      if (local_184[0] != '\0') {
        lVar3 = strtol(local_184,(char **)0x0,10);
        (*pcVar2)(1,lVar3);
      }
    }
  }
  game._0_4_ = fileName;
  game._4_4_ = ZIP_BUF;
  game._8_4_ = ZIP_BUF_SIZE;
  pcVar2 = (code *)dlsym(handle,"retro_load_game");
  if (pcVar2 == (code *)0x0) {
    RARCH_LOG("find retro_load_game process fail \n");
  }
  else {
    iVar1 = (*pcVar2)(game);
    RARCH_LOG("retcode:%d\n",iVar1);
    if (iVar1 == 0) {
      run_process("retro_unload_game",0);
      run_process("retro_deinit",0);
      dlclose(handle);
    }
    else {
      Load_Proc2();
      video_driver_set_rotation(0xff00);
    }
  }
  video_driver_set_colormode(0);
  RARCH_LOG(&DAT_002ddd74);
  return 0;
}
