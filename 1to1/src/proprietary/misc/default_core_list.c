/* ★★★ 2026-10-04（第 131 轮）T09 根修：定义已移到 src/data/factory_image.S（镜像别名）。
 *
 * 根因（取证链完整，非推断）：
 *   ① 工厂 default_core_list @ 0x003b0254（size 0x1a90=6800，.data，GLOBAL）
 *      —— 权威账本 ledger/factory_globals.tsv:752。
 *   ② 该地址落在 .fimg_data 镜像区（段基址 0x3af000，偏移 0x1254），
 *      且镜像里**本来就含它的内容**：0x3b0254 处首 4 字节 = "BKP\0"，
 *      正是 default_core_list 的第一项（工厂 33 项：BKP/ZIP/SMC/FIG/SFC/…）。
 *   ③ 但本文件又用 C 数组**重编了一份**放在自有 .data @ 0x4df004（size 6800），
 *      于是产物里同一份数据有**两个副本**，而符号绑定的是**非工厂地址**那份。
 *      （src/compat/globals.h:4301 早已按工厂地址正确声明：@0x003b0254 ⇒ 声明侧对、定义侧错。）
 *   ④ 实测两份内容**逐字节相同**（6800/6800）⇒ 纯重复副本，唯一问题是地址绑定。
 *   ⑤ 后果（T09 实测 22 个 DIVERGE 的主因）：GetCoreIndex / FilePreEmu / SeletEmuCore 等
 *      按「工厂读 0x3b0254、我方读 0x4df004」被判 DIVERGE。
 *      tools/diff_exec.py:fp_key 的口径是「工厂 GLOBAL ⇒ 地址有意义」，
 *      并明确写了「不得因为名字相同就放行」⇒ **该判据是对的，是我方绑定错了**。
 *
 * 修法：删掉这份重复定义，改用与 src/data/factory_image.S 里其余 934 个数据对象
 *   **完全相同**的 .set 别名机制（__f_data_base + 0x1254），
 *   使符号落到工厂地址 ⇒ 同时消除重复副本与这批 DIVERGE。
 *
 * 为何不走另外两条路（都被证据否掉）：
 *   ✗ 放宽 diff_exec 判据（把它当"纯私有"按名字配对）⇒ 会掩盖真实绑定错误；
 *     tools/dup_sym_gate.py 文档里 ArchivePath（工厂同名两份、代码引用低地址那份，
 *     我方绑到 GLOBAL 那份 ⇒ 真机读错内存）就是同族真缺陷。
 *   ✗ 把 C 数组搬进自定义段 ⇒ 段 VMA 必须与工厂一致（代码里烧死绝对地址），
 *     只有"镜像 + .set 别名"能同时保证地址与字节都逐位一致（tools/gen_data_module.py 文件头）。
 *
 * 内容等价性证据：factory_data.bin 的 [0x1254, 0x2ce4) 与本文件原 6800 字节逐字节相等。
 *
 * 回退：git checkout src/proprietary/misc/default_core_list.c src/data/factory_image.S
 */
#include "globals.h"
#include "proto.h"

/* default_core_list 的**定义**现在是 src/data/factory_image.S 里的镜像别名：
 *     .globl default_core_list
 *     .set  default_core_list, __f_data_base + 0x1254
 *     .size  default_core_list, 0x1a90
 * 这里只需包含 globals.h 的 extern 声明（globals.h:4301，已标注工厂地址 0x003b0254）。
 * 若链接报 undefined，说明 factory_image.S 未被链入或别名被 gen_data_module.py 重生成覆盖
 * —— 那时应重跑 tools/regen_data.sh（它会用 --globals ledger/factory_globals.tsv 重新生成别名）。 */
