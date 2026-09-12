/* operator_shim.cpp — 工厂以 C 接口暴露 TUnzip 的 C++ 对象语义。
 * Ghidra 把 `operator new/delete` 渲染为 operator_new/operator_delete（C 改名）。
 * 此 shim 以真实 C++ new/delete 实现，二者 ABI 一致（ARM32 AAPCS32）。 */
void *operator_new(unsigned int size) { return ::operator new(size); }
void operator_delete(void *p)         { ::operator delete(p); }
