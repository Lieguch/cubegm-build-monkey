/* zstub.c — **链接期** libz 桩（不打包进产物，不在设备上执行）
 *
 * 来历（2026-09-14 真实差分暴露的运行期地雷）
 * ---------------------------------------------------------------
 * 工厂 rkgame 的 `compress` / `uncompress` 是从 `libz.so.1` **动态导入**的
 * （工厂 NEEDED 里有 libz.so.1）。而我们的重建产物此前在链接脚本里用
 * `PROVIDE_HIDDEN(compress = 0)` 把它们绑成 **ABS 0** ⇒ 调用即跳地址 0。
 * 这两个符号被 `retro_save_state` / `retro_load_state`（以及 TestLibz0）调用，
 * 也就是**存档 / 读档功能必崩**。dyn_audit 的 A6 门禁专门拦这一类（ABS 0 占位）。
 *
 * 为什么不直接链接一个真实的 libz.so.1？
 * ---------------------------------------------------------------
 * 实测：链接真实 DSO 会让链接器把引用**绑到具体符号版本**（`.gnu.version_r` 里写下
 * 如 `ZLIB_1.2.9`）。而设备 SD 上原厂 ARM libz.so.1 导出的版本集是**非标准的**
 * （我们读出来是 `ZLIB_1.2.0 … ZLIB_1.2.12`），Ubuntu 22.04 的 zlib 与之不一定重合
 * ⇒ 在设备上可能报 `version ZLIB_x not found`。
 * 因此改用**本桩**：`NEEDED` 仍然只记 `libz.so.1`（与工厂一致），但**不绑任何版本**，
 * 运行期由设备自己的 `/usr/lib/libz.so.1`（或 `LD_LIBRARY_PATH` 里的那份）解析。
 * ⇒ 桩里的函数体**永远不会被执行**，返回值只是为了让编译器闭嘴。
 */
int compress(void *dest, unsigned long *destLen, const void *source, unsigned long sourceLen);
int compress(void *dest, unsigned long *destLen, const void *source, unsigned long sourceLen)
{
    (void)dest; (void)destLen; (void)source; (void)sourceLen;
    return -1;
}

int uncompress(void *dest, unsigned long *destLen, const void *source, unsigned long sourceLen);
int uncompress(void *dest, unsigned long *destLen, const void *source, unsigned long sourceLen)
{
    (void)dest; (void)destLen; (void)source; (void)sourceLen;
    return -1;
}
