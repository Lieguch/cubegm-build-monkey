/* ============================================================
 * environment   @ 0x002b4f98   size=476B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 environment(int param_1,uint *param_2)

{
  undefined2 uVar1;
  char *pcVar2;
  char *pcVar3;
  undefined4 uVar4;
  undefined1 *puVar5;
  
  if (param_1 == 10) {
    use_rgb_8888 = 0;
    if (*param_2 == 2) {
      use_rgb_8888 = 0;
      return 1;
    }
    if (*param_2 == 1) {
      use_rgb_8888 = 1;
      video_driver_set_colormode(1);
      return 1;
    }
LAB_002b4fe0:
    uVar4 = 0;
  }
  else {
    if (param_1 == 0x1b) {
      *param_2 = (uint)log_dummy;
      return 1;
    }
    if (param_1 == 1) {
      rotation = *param_2;
      if ((rotation != 0) && (soft_rotation != 0)) {
        if (rotation_buff != (void *)0x0) {
          free(rotation_buff);
        }
        rotation_buff = malloc(0x96000);
        return 1;
      }
      video_driver_set_rotation(rotation | 0xff00);
      return 1;
    }
    if (param_1 == 0x25) {
      param_2[8] = 0;
      param_2[9] = 0x40e58880;
      return 1;
    }
    if (param_1 == 9) {
      puVar5 = &system_directory;
      pcVar2 = stpcpy(&system_directory,work_path);
      pcVar3 = "cores";
    }
    else {
      if (param_1 != 0x1f) {
        if (((param_1 == 0xf) && (corecfg[0] != '\0')) &&
           (get_value_from_items(*param_2,environment_str,corecfg,0x40), environment_str[0] != '\0')
           ) {
          param_2[1] = (uint)environment_str;
          return 1;
        }
        goto LAB_002b4fe0;
      }
      puVar5 = save_directory;
      pcVar2 = stpcpy(save_directory,work_path);
      pcVar3 = "saves";
    }
    uVar4 = 1;
    uVar1 = *(undefined2 *)(pcVar3 + 4);
    *(undefined4 *)pcVar2 = *(undefined4 *)pcVar3;
    *(undefined2 *)(pcVar2 + 4) = uVar1;
    *param_2 = (uint)puVar5;
  }
  return uVar4;
}
