/* ============================================================
 * ShareMemCreat   @ 0x0000a774   size=132B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 * ShareMemCreat(void)

{
  undefined4 *puVar1;
  
  shmid = shmget(0x4d2,8,0x3b6);
  if (shmid == -1) {
    puts("shmget failed");
  }
  else {
    puVar1 = shmat(shmid,(void *)0x0,0);
    shm = puVar1;
    if (puVar1 != (undefined4 *)0xffffffff) {
      *puVar1 = 1;
      puVar1[1] = 0;
      return puVar1;
    }
    puts("shmat failed");
  }
  return (undefined4 *)0xffffffff;
}
