/* ============================================================
 * host_zip_test.cpp —— 主机端验证 XUnzip 的"CD 名解密"链路
 *
 * 为什么需要（R261）：
 *   真机证据已经给出三件事：① 包里 CD 名是密文（XOR 0xE5）；
 *   ② 工厂用 key2[24] 当密钥（指令级：GOT 槽 0x3b1e10 → &key2，`ldrb r1,[r0,#24]`）；
 *   ③ 我方真机上 key2[0..15] 有值（WQW 魔数表）、尾部 12 字节为 0 ⇒ 解密不生效。
 *   本程序把同一份 unzip.cpp 编到主机上，**只切换 key2 尾部**：
 *       tail=zero   → 复现真机现状（预期：Find 失败，6 个名字全不匹配）
 *       tail=vendor → 补齐厂商尾部（预期：Find 成功、Unzip 出正确长度）
 *   这样"修复是否有效"在 PC 上就能证死，不必再烧一轮真机。
 *
 * 编译/运行见 tools/host_zip_test.sh
 * ============================================================ */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <windows.h>
#include <tchar.h>
#include "unzip.h"

/* ZIP_FILENAME 定义在 unzip.cpp 内部（#define），头文件不导出 ⇒ 测试侧本地等价常量 */
#define ZIP_FILENAME 2

/* 工厂 .bss @0x3E190C 的 28 字节密钥表；前 16 字节在真机上已被写入（实测值） */
unsigned char key2[28];
ZRESULT zopenerror asm("_ZL10zopenerror") = 0;
ZRESULT lasterrorU = 0;



/* 主机测试用的 ucrc32（ARM 产物里由 src/proprietary/misc/FUN_0000fff4_ucrc32.c 提供） */
extern "C" unsigned int ucrc32(unsigned int crc, unsigned char *buf, unsigned int len)
{
    static unsigned int T[256]; static int init = 0;
    if (!init) { for (unsigned int i = 0; i < 256; i++) {
            unsigned int c = i;
            for (int k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
            T[i] = c; }
        init = 1; }
    unsigned int c = crc ^ 0xffffffffu;
    for (unsigned int i = 0; i < len; i++) c = T[(c ^ buf[i]) & 0xff] ^ (c >> 8);
    return (c ^ 0xffffffffu);
}
/* C++ 异常展开桩：测试路径不会真正抛异常，仅为满足链接 */
extern "C" void _Unwind_Resume(void *) { }
extern "C" int __gxx_personality_seh0(...) { return 0; }

/* 主机测试用的最小 C++ 运行期（ARM 产物里由 libstdc++.so.6 提供） */
void *operator new(size_t n)            { return malloc(n); }
void  operator delete(void *p)          { free(p); }
void *operator new[](size_t n)          { return malloc(n); }
void  operator delete[](void *p)        { free(p); }
void  operator delete(void *p, size_t)  { free(p); }
void  operator delete[](void *p, size_t){ free(p); }

int main(int argc, char **argv)
{
    if (argc < 4) {
        printf("usage: %s <zip> <zero|vendor> <item>\n", argv[0]);
        return 2;
    }
    static const unsigned char head[16] = {
        0x50, 0x4b, 0x05, 0x06,   /* PK\5\6  EoCD(标准)  */
        0x57, 0x51, 0x57, 0x01,   /* WQW\1   EoCD(厂商)  */
        0x50, 0x4b, 0x01, 0x02,   /* PK\1\2  CD(标准)    */
        0x57, 0x51, 0x57, 0x02    /* WQW\2   CD(厂商)    */
    };
    memcpy(key2, head, 16);
    if (!strcmp(argv[2], "vendor")) {
        key2[16] = 0x50; key2[17] = 0x4b; key2[18] = 0x03; key2[19] = 0x04; /* PK\3\4 LFH(标准) */
        key2[20] = 0x57; key2[21] = 0x51; key2[22] = 0x57; key2[23] = 0x03; /* WQW\3  LFH(厂商) */
        key2[24] = 0xE5; key2[25] = 0xE5; key2[26] = 0xE5; key2[27] = 0xE5; /* 文件名 XOR 密钥（实测） */
    }

    printf("key2 =");
    for (int i = 0; i < 28; i++) printf(" %02x", key2[i]);
    printf("\n");

    HZIP hz = OpenZipU((const TCHAR *)argv[1], (const char *)0);  /* 2 参重载 = ZIP_FILENAME 路径 */
    printf("OpenZipU  = %p  (0 = 失败)\n", (void *)hz);
    if (!hz) return 1;

    ZIPENTRY ze;
    int idx = -1;
    ZRESULT zr = FindZipItem(hz, argv[3], true, &idx, &ze);
    printf("FindZipItem(\"%s\") = 0x%x  idx=%d  unc=%u  comp=%u\n",
           argv[3], (unsigned)zr, idx, (unsigned)ze.unc_size, (unsigned)ze.comp_size);
    if (zr == ZR_OK) {
        unsigned char *buf = (unsigned char *)malloc(ze.unc_size ? ze.unc_size : 16);
        ZRESULT zr2 = UnzipItem(hz, idx, buf, 0);
        printf("UnzipItem = 0x%x  first16 =", (unsigned)zr2);
        for (int i = 0; i < 16; i++) printf(" %02x", buf[i]);
        printf("\n");
        free(buf);
    }
    CloseZipU(hz);
    return zr == ZR_OK ? 0 : 1;
}
