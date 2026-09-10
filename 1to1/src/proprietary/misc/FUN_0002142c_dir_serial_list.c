/* ============================================================
 * dir_serial_list   @ 0x0002142c   size=576B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int dir_serial_list(int param_1)

{
  char cVar1;
  int iVar2;
  int iVar3;
  char *pcVar4;
  int iVar5;
  dirent **ppdVar6;
  dirent **ppdVar7;
  dirent *pdVar8;
  int iVar9;
  int iVar10;
  int iVar11;
  dirent **local_2c [2];
  
  iVar2 = scandir(path,local_2c,(__selector *)0x0,alphasort);
  ppdVar6 = local_2c[0];
  if (iVar2 < 0) {
    iVar10 = -1;
  }
  else {
    if (iVar2 == 0) {
      iVar10 = 0;
    }
    else {
      iVar11 = 0;
      iVar3 = 0;
      ppdVar7 = local_2c[0];
      iVar9 = 0;
      do {
        while (iVar5 = iVar3, pdVar8 = *ppdVar7, iVar10 = iVar9, (pdVar8->d_type & 4) == 0) {
LAB_000214b8:
          ppdVar7 = ppdVar7 + 1;
          iVar3 = iVar5 + 1;
          iVar9 = iVar10;
          if (iVar2 == iVar5 + 1) goto LAB_0002155c;
        }
        if (pdVar8->d_name[0] == '.') {
          cVar1 = pdVar8->d_name[1];
          if ((cVar1 != '\0') &&
             (iVar3 = strcmp(pdVar8->d_name,"System Volume Information"), iVar3 != 0)) {
            if ((cVar1 != '.') || (pdVar8->d_name[2] != '\0')) goto LAB_00021500;
            iVar3 = strcmp(path,root_path);
            if ((iVar3 != 0) && (iVar10 = iVar9 + 1, param_1 < iVar10)) goto LAB_0002150c;
          }
          goto LAB_000214b8;
        }
        iVar3 = strcmp(pdVar8->d_name,"System Volume Information");
        if (iVar3 == 0) goto LAB_000214b8;
LAB_00021500:
        iVar10 = iVar9 + 1;
        if (iVar9 + 1 <= param_1) goto LAB_000214b8;
LAB_0002150c:
        iVar10 = iVar9 + 1;
        if (DAT_003af394 <= iVar11) goto LAB_000214b8;
        iVar3 = iVar11 * 0x404;
        iVar11 = iVar11 + 1;
        pcVar4 = strcpy(&file_info_list + iVar3,pdVar8->d_name);
        *(uint *)(pcVar4 + 0x100) = (uint)(*ppdVar7)->d_type;
        iVar3 = iVar5 + 1;
        ppdVar7 = ppdVar7 + 1;
        iVar9 = iVar10;
      } while (iVar2 != iVar5 + 1);
LAB_0002155c:
      iVar2 = 0;
      do {
        pdVar8 = ppdVar6[iVar2];
        ppdVar6 = ppdVar6 + iVar2;
        iVar2 = iVar2 + 1;
        if ((((pdVar8->d_type & 4) == 0) && (iVar10 = iVar10 + 1, param_1 < iVar10)) &&
           (iVar11 < DAT_003af394)) {
          iVar3 = iVar11 * 0x404;
          iVar11 = iVar11 + 1;
          pcVar4 = strcpy(&file_info_list + iVar3,pdVar8->d_name);
          pdVar8 = *ppdVar6;
          *(uint *)(pcVar4 + 0x100) = (uint)pdVar8->d_type;
        }
        free(pdVar8);
        ppdVar6 = local_2c[0];
      } while (iVar5 + 1 != iVar2);
    }
    free(local_2c[0]);
  }
  return iVar10;
}
