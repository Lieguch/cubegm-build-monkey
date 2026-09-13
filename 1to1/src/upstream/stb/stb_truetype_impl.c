/* stb_truetype_impl.c — stb_truetype 单头库的实现单元（工厂 v1.26）
 * 工厂符号：stbtt_InitFont / stbtt_ScaleForPixelHeight / stbtt_GetFontVMetrics /
 *          stbtt_GetCodepointHMetrics / stbtt_MakeCodepointBitmapSubpixel /
 *          stbtt_GetCodepointBitmapBoxSubpixel
 * 证据：src/upstream/stb/stb_truetype.h 头部版本宏 v1.26，与固件时间窗一致。
 * 注意：工厂以 C 编译（无 mangled），故用 C 编译器编译本文件。
 */
#define STB_TRUETYPE_IMPLEMENTATION
#include "stb_truetype.h"
