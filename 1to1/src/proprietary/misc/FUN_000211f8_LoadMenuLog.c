/* ============================================================
 * LoadMenuLog   @ 0x000211f8   size=356B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void LoadMenuLog(void)

{
  FILE *__stream;
  uint __c;
  char acStack_110 [256];
  
  sprintf(acStack_110,"%s/menu.log",work_path);
  __stream = fopen(acStack_110,"rb");
  if (__stream == (FILE *)0x0) {
    memset(m_menulog,0,0x1bc);
    m_menulog._292_4_ = 1;
    m_menulog._324_4_ = 1;
    m_menulog._304_4_ = 0xffffffff;
    m_menulog._332_4_ = 0xffffffff;
    return;
  }
  fread(m_menulog,1,0x1bc,__stream);
  fclose(__stream);
  if ((AutoRestoreKey & 1) == 0) {
    m_menulog._284_4_ = 0;
    m_menulog._288_4_ = 0;
  }
  if ((AutoRestoreKey & 2) == 0) {
    m_menulog._296_4_ = 0;
    m_menulog._300_4_ = 0;
    m_menulog._292_4_ = 1;
    m_menulog._304_4_ = 0xffffffff;
  }
  if ((AutoRestoreKey & 4) == 0) {
    m_menulog._312_4_ = 0;
    m_menulog._308_4_ = 0;
  }
  if ((AutoRestoreKey & 8) == 0) {
    m_menulog._320_4_ = 0;
    m_menulog._316_4_ = 0;
  }
  if ((AutoRestoreKey & 0x10) == 0) {
    __c = AutoRestoreKey & 0x10;
    m_menulog._324_4_ = 1;
    m_menulog._332_4_ = 0xffffffff;
    m_menulog._328_4_ = __c;
    memset(m_menulog + 0x150,__c,100);
    m_menulog._436_4_ = __c;
    m_menulog._440_4_ = __c;
    return;
  }
  return;
}
