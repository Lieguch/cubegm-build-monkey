/* stb_truetype_impl.c — stb_truetype 单头库的实现单元（工厂 ≤1.22，已对齐）
 * 工厂符号：stbtt_InitFont / stbtt_ScaleForPixelHeight / stbtt_GetFontVMetrics /
 *          stbtt_GetCodepointHMetrics / stbtt_MakeCodepointBitmapSubpixel /
 *          stbtt_GetCodepointBitmapBoxSubpixel
 * 证据：src/upstream/stb/stb_truetype.h 头部版本需为 v1.22（与原厂 ≤1.22 对齐，R277）
 *       v1.26 (2021-08-28) "fix broken rasterizer" 会改变字体 rasterization 输出，
 *       导致 frame_hash_abi 与原厂分歧（B6A 失败根因）。
 * 注意：工厂以 C 编译（无 mangled），故用 C 编译器编译本文件。
 * R277 补充：在 ModelScope 环境中，先执行
 *   git clone --depth 1 --branch v1.22 https://github.com/nothings/stb.git /tmp/stb_v122
 *   cp /tmp/stb_v122/stb_truetype.h src/upstream/stb/stb_truetype.h
 * 以替换为 v1.22 头文件后再编译。
 */
#define STB_TRUETYPE_IMPLEMENTATION
#include "stb_truetype.h"
