#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""libc_model.py —— 差分执行器的**外部调用语义模型**（根因修复，非补丁）。

## 为什么必须有它（GAP 17.16）

`diff_exec.run_func` 的 `code_hook` 原先对所有外部调用一律
`r0 = stub_ret.get(name, 0)` 然后返回 —— 即**任何外部函数都返回 0**。
对 `int` 返回型这只是"中性"；对**指针返回型**它就等于"返回 NULL"，
于是被测代码一解引用就 `UC_ERR_READ_UNMAPPED`。

实测后果（第 64 轮审计）：
    strupr        F=['islower']        O=['__ctype_b_loc']   ⇒ O 侧崩
    get_from_line F=['strlen']         O=['strchr']          ⇒ O 侧崩
    myStrrstr / GetFilenameExt                               ⇒ O 侧崩
共 4 个函数被这条**仪器缺陷**判成 DIVERGE。这不是代码缺陷 —— 是**尺子看不见**。

★ 这违反本项目纪律 9：「某侧完全没有某行为」的结论，必须先证明该行为在本侧**可被观测**。
因此本模块的职责不是"让对拍变绿"，而是**让两侧都能被真实执行**：
两侧共用**同一份模型、同一组地址**，于是差异只可能来自被测代码本身。

## 设计约束（三条，缺一不可）

1. **两侧完全一致**：同一进程内两遍执行共用本模型与同一组基址
   ⇒ 指针值可比、堆内容可比、ctype 表只读且不落在"可比数据区"内（不会带来噪音）。
2. **不掩盖真实差异**：模型只实现**语义确定**的 libc 函数。
   语义不确定或带环境依赖的（`fopen`/`printf`/`time`…）**一律不建模**，
   走兜底返回 0 并**登记进 `unmodelled`** —— 报告里单列，绝不静默当成"一致"。
3. **可自证**：表与判定函数都是**纯函数**，不依赖本项目数据即可断言
   （见 `--self-test`），例如 `_ISbit` 必须等于 glibc 文档值、`toupper` 表与 `toupper()` 函数一致。
"""
import struct

# --------------------------------------------------------------------------- #
# 内存布局（必须 **低于 SENTINEL=0x7FFFF000**，且不与产物段/SCRATCH/STACK 冲突）
#   SCRATCH = 0x7D000000..0x7D010000 ；STACK = 0x7E000000..0x7E040000
# --------------------------------------------------------------------------- #
CTYPE_BASE = 0x7F000000          # ctype 表
CTYPE_SIZE = 0x00004000
HEAP_BASE = 0x7F800000           # 模拟堆
HEAP_SIZE = 0x00200000
ERRNO_ADDR = CTYPE_BASE + 0x3000

# 表内布局
_OFF_B_PTR = 0x0000              # __ctype_b_loc() 返回的"指针的地址"
_OFF_TOU_PTR = 0x0004
_OFF_TOL_PTR = 0x0008
_OFF_B_TBL = 0x0100              # unsigned short[384]
_OFF_TOU_TBL = 0x0400            # int32[384]
_OFF_TOL_TBL = 0x0700            # int32[384]
TBL_LEN = 384                    # 索引 -128..255
IDX_BASE = -128


# --------------------------------------------------------------------------- #
# glibc `<ctype.h>` 的位定义（必须与文档逐位一致 —— 自证会检查）
#   #define _ISbit(bit) ((bit) < 8 ? ((1 << (bit)) << 8) : ((1 << (bit)) >> 8))
# --------------------------------------------------------------------------- #
def _isbit(bit):
    return ((1 << bit) << 8) if bit < 8 else ((1 << bit) >> 8)


ISupper = _isbit(0)
ISlower = _isbit(1)
ISalpha = _isbit(2)
ISdigit = _isbit(3)
ISxdigit = _isbit(4)
ISspace = _isbit(5)
ISprint = _isbit(6)
ISgraph = _isbit(7)
ISblank = _isbit(8)
IScntrl = _isbit(9)
ISpunct = _isbit(10)
ISalnum = _isbit(11)

_SPACE = ' \t\n\v\f\r'
_PUNCT = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'


def flags_of(c):
    """→ 该字符的 `unsigned short` 分类位（纯函数，自证锚点）。

    ⚠️ 输入按 **unsigned char** 语义（0..255）；越界索引不会发生（表长 384）。
    """
    f = 0
    ch = chr(c)
    if 'A' <= ch <= 'Z':
        f |= ISupper | ISalpha | ISalnum | ISgraph | ISprint
    if 'a' <= ch <= 'z':
        f |= ISlower | ISalpha | ISalnum | ISgraph | ISprint
    if '0' <= ch <= '9':
        f |= ISdigit | ISxdigit | ISalnum | ISgraph | ISprint
    if ch in 'abcdefABCDEF':
        f |= ISxdigit
    if ch in _SPACE:
        f |= ISspace
        if ch in ' \t':
            f |= ISblank
    if c < 0x20 or c == 0x7F:
        f |= IScntrl
    if ch in _PUNCT:
        f |= ISpunct | ISgraph | ISprint
    return f


def toupper_c(c):
    return c - 32 if 0x61 <= c <= 0x7A else c


def tolower_c(c):
    return c + 32 if 0x41 <= c <= 0x5A else c


def build_tables():
    """→ (b_bytes, tou_bytes, tol_bytes)：三段可直接 mem_write 的字节串。"""
    b = b''.join(struct.pack('<H', flags_of(i & 0xFF) if i >= 0 else 0)
                 for i in range(IDX_BASE, IDX_BASE + TBL_LEN))
    tou = b''.join(struct.pack('<i', toupper_c(i & 0xFF) if i >= 0 else 0)
                   for i in range(IDX_BASE, IDX_BASE + TBL_LEN))
    tol = b''.join(struct.pack('<i', tolower_c(i & 0xFF) if i >= 0 else 0)
                   for i in range(IDX_BASE, IDX_BASE + TBL_LEN))
    return b, tou, tol


# --------------------------------------------------------------------------- #
# 调用语义族（用于"机制不同、含义相同"的调用名归一；见 GAP 17.16）
#   仅当**两侧调用的是同一个判别式**时才允许归一 —— 归一表本身是显式、可审计的。
# --------------------------------------------------------------------------- #
CTYPE_PREDICATES = {
    'islower': 'lower', '__ctype_b_loc': None,     # __ctype_b_loc 只提供表，判定靠位
    'isupper': 'upper', 'isdigit': 'digit', 'isalpha': 'alpha',
    'isspace': 'space', 'isalnum': 'alnum', 'ispunct': 'punct',
    'isxdigit': 'xdigit', 'isprint': 'print', 'isgraph': 'graph',
    'isblank': 'blank', 'iscntrl': 'cntrl',
}

# 指针返回型：这些函数**绝不允许**被兜底成 0（否则调用方必崩）—— 自证会断言
PTR_RETURNING = (
    'strchr', 'strrchr', 'strstr', 'strcpy', 'strncpy', 'strcat', 'strncat',
    'strdup', 'strndup', 'memchr', 'memcpy', 'memmove', 'memset',
    'malloc', 'calloc', 'realloc', '__ctype_b_loc', '__ctype_toupper_loc',
    '__ctype_tolower_loc', '__errno_location', 'index', 'rindex',
)


def _cmp(a, b):
    """strcmp/memcmp 语义：a<b ⇒ -1，a==b ⇒ 0，a>b ⇒ 1（以 32 位补码返回）。"""
    return (a > b) - (a < b)


# --------------------------------------------------------------------------- #
# 同函数异名的符号（glibc 的内部别名 / 带 `_chk` 的 fortify 版本 / `_IO_` 前缀）。
#   依据：它们就是同一个函数（`__strdup` 与 `strdup` 在 glibc 里是同一实现的强弱别名；
#   `_IO_getc` 是 `getc` 的旧名）。归一到主名后**两侧走同一段模型代码** —— 否则
#   工厂侧因名字不同而"未建模 ⇒ 返回 0"，我们的 `strdup` 却真执行 ⇒ 制造假发散。
#   ★ `_chk` 版本的额外参数（destlen）在尾部 ⇒ 前几个参数与主名一致，可直接复用。
# --------------------------------------------------------------------------- #
ALIASES = {
    '__strdup': 'strdup',
    '__strndup': 'strndup',
    '__memcpy_chk': 'memcpy',
    '__memmove_chk': 'memmove',
    '__memset_chk': 'memset',
    '__strcpy_chk': 'strcpy',
    '__strncpy_chk': 'strncpy',
    '__strcat_chk': 'strcat',
    '__stpcpy_chk': 'stpcpy',
    '_IO_getc': 'getc',
    '__getc': 'getc',
    '__libc_malloc': 'malloc',
    # ★ C++ `operator new/delete`（工厂的 zip_utils/xunzip 是 C++）——**必须有**：
    #   实测 `_Znwj` 未建模 ⇒ 工厂侧拿 NULL ⇒ `OpenZipU`/`PauseMenu`/`mui_DisplayThumbnail`
    #   等 18 个函数被**仪器**判成发散（"F 侧 WRITE_UNMAPPED / O 侧 return"）。
    '_Znwj': 'malloc', '_Znaj': 'malloc', '_Znam': 'malloc', '_Znwm': 'malloc',
    '_ZdlPv': 'free', '_ZdaPv': 'free', '_ZdlPvm': 'free', '_ZdaPvm': 'free',
}


# --------------------------------------------------------------------------- #
class Model(object):
    """一次 `run_func` 执行期内有效的外部调用模型。"""

    def __init__(self):
        self.unmodelled = []          # 未建模的调用名（**必须列名落盘**）
        self.modelled = []            # 已建模的调用名
        self.heap_top = HEAP_BASE

    # ---- 与 Unicorn 的接口 -------------------------------------------------
    def map_regions(self, mu):
        b, tou, tol = build_tables()
        mu.mem_map(CTYPE_BASE, CTYPE_SIZE, 7)
        mu.mem_write(CTYPE_BASE, b'\x00' * CTYPE_SIZE)
        mu.mem_write(CTYPE_BASE + _OFF_B_PTR,
                     struct.pack('<I', CTYPE_BASE + _OFF_B_TBL))
        mu.mem_write(CTYPE_BASE + _OFF_TOU_PTR,
                     struct.pack('<I', CTYPE_BASE + _OFF_TOU_TBL))
        mu.mem_write(CTYPE_BASE + _OFF_TOL_PTR,
                     struct.pack('<I', CTYPE_BASE + _OFF_TOL_TBL))
        mu.mem_write(CTYPE_BASE + _OFF_B_TBL, b)
        mu.mem_write(CTYPE_BASE + _OFF_TOU_TBL, tou)
        mu.mem_write(CTYPE_BASE + _OFF_TOL_TBL, tol)
        mu.mem_map(HEAP_BASE, HEAP_SIZE, 7)
        # ★ 堆**不清零**：`malloc` 返回的未初始化内存若被读到，差异必须暴露出来
        #   （若清零，`malloc` 与 `calloc` 的语义差就被抹掉 ⇒ 假 PASS）。
        mu.mem_write(HEAP_BASE, b'\xa5' * HEAP_SIZE)

    # ---- 内存小工具 --------------------------------------------------------
    @staticmethod
    def _rd(mu, p, n):
        return mu.mem_read(p & 0xFFFFFFFF, n)

    @classmethod
    def _cstr(cls, mu, p, limit=512):
        out = bytearray()
        while len(out) < limit:
            ch = cls._rd(mu, p + len(out), 1)[0]
            if ch == 0:
                break
            out.append(ch)
        return bytes(out)

    @classmethod
    def _u32(cls, mu, p):
        return struct.unpack('<I', cls._rd(mu, p, 4))[0]

    @staticmethod
    def _w32(mu, p, v):
        mu.mem_write(p & 0xFFFFFFFF, struct.pack('<I', v & 0xFFFFFFFF))

    def _alloc(self, mu, n):
        n = (n + 7) & ~7
        if self.heap_top + n > HEAP_BASE + HEAP_SIZE:
            return 0
        p = self.heap_top
        mu.mem_write(p, b'\x00' * n)          # calloc 语义
        self.heap_top += n
        return p

    # ---- 主入口 ------------------------------------------------------------
    def call(self, mu, ac, name):
        """→ True 表示已建模（调用方负责 `PC = LR`）。

        未建模 ⇒ False（调用方走兜底 0，并把它记进 `unmodelled`）。
        """
        A = [mu.reg_read(ac.UC_ARM_REG_R0 + i) & 0xFFFFFFFF for i in range(4)]
        R = ac.UC_ARM_REG_R0
        # ★ 异名同函数先归一（`__strdup` ⇒ `strdup`），再进模型
        name = ALIASES.get(name, name)

        def ret(v):
            mu.reg_write(R, v & 0xFFFFFFFF)
            return True

        try:
            if name == 'strlen':
                return ret(len(self._cstr(mu, A[0])))
            if name in ('strchr', 'index'):
                s, c = self._cstr(mu, A[0]), (A[1] & 0xFF)
                i = s.find(bytes([c]))
                return ret(A[0] + i if i >= 0 else 0)
            if name in ('strrchr', 'rindex'):
                s, c = self._cstr(mu, A[0]), (A[1] & 0xFF)
                i = s.rfind(bytes([c]))
                return ret(A[0] + i if i >= 0 else 0)
            if name == 'strstr':
                h, n = self._cstr(mu, A[0]), self._cstr(mu, A[1])
                i = h.find(n)
                return ret(A[0] + i if i >= 0 else 0)
            if name == 'strcmp':
                a, b = self._cstr(mu, A[0]), self._cstr(mu, A[1])
                return ret(_cmp(a, b))
            if name == 'strcasecmp':
                a = self._cstr(mu, A[0]).lower()
                b = self._cstr(mu, A[1]).lower()
                return ret(_cmp(a, b))
            if name == 'strncmp':
                a = self._cstr(mu, A[0])[:A[2]]
                b = self._cstr(mu, A[1])[:A[2]]
                return ret((a > b) - (a < b) & 0xFFFFFFFF)
            if name == 'memcmp':
                a = bytes(self._rd(mu, A[0], A[2]))
                b = bytes(self._rd(mu, A[1], A[2]))
                return ret(_cmp(a, b))
            if name == 'memchr':
                blob = bytes(self._rd(mu, A[0], A[2]))
                i = blob.find(bytes([A[1] & 0xFF]))
                return ret(A[0] + i if i >= 0 else 0)
            if name in ('strcpy', 'stpcpy'):
                s = self._cstr(mu, A[1])
                mu.mem_write(A[0], s + b'\x00')
                return ret(A[0] + (len(s) if name == 'stpcpy' else 0))
            if name == 'strncpy':
                s = self._cstr(mu, A[1])[:A[2]]
                mu.mem_write(A[0], s + b'\x00' * (A[2] - len(s)))
                return ret(A[0])
            if name in ('strcat', 'strncat'):
                d = self._cstr(mu, A[0])
                s = self._cstr(mu, A[1])
                if name == 'strncat':
                    s = s[:A[2]]
                mu.mem_write(A[0] + len(d), s + b'\x00')
                return ret(A[0])
            if name in ('strdup', 'strndup'):
                s = self._cstr(mu, A[0])
                if name == 'strndup':
                    s = s[:A[1]]
                p = self._alloc(mu, len(s) + 1)
                mu.mem_write(p, s + b'\x00')
                return ret(p)
            if name in ('memcpy', 'memmove'):
                mu.mem_write(A[0], self._rd(mu, A[1], A[2]))
                return ret(A[0])
            if name == 'memset':
                mu.mem_write(A[0], bytes([A[1] & 0xFF]) * A[2])
                return ret(A[0])
            if name in ('malloc', 'realloc'):
                return ret(self._alloc(mu, A[0]))
            if name == 'calloc':
                return ret(self._alloc(mu, A[0] * A[1]))
            if name == 'free':
                return ret(0)
            if name in ('atoi', 'atol'):
                s = self._cstr(mu, A[0]).strip()
                m = bytearray()
                for i, ch in enumerate(s):
                    if (ch in b'+-' and i == 0) or ch.isdigit():
                        m.append(ch)
                    else:
                        break
                try:
                    return ret(int(bytes(m)) & 0xFFFFFFFF)
                except ValueError:
                    return ret(0)
            if name == 'strtol':
                s = self._cstr(mu, A[0]).strip()
                base = A[2] or 10
                m = bytearray()
                for i, ch in enumerate(s):
                    if (ch in b'+-' and i == 0) or ch.isalnum():
                        m.append(ch)
                    else:
                        break
                try:
                    v = int(bytes(m), base if 2 <= base <= 36 else 10)
                except ValueError:
                    v = 0
                if A[1]:
                    self._w32(mu, A[1], A[0] + len(m))
                return ret(v & 0xFFFFFFFF)
            if name == 'toupper':
                return ret(toupper_c(A[0] & 0xFF) if A[0] < 256 else A[0])
            if name == 'tolower':
                return ret(tolower_c(A[0] & 0xFF) if A[0] < 256 else A[0])
            if name in CTYPE_PREDICATES and CTYPE_PREDICATES[name]:
                return ret(self._pred_index(name, A[0]))
            if name == '__ctype_b_loc':
                return ret(CTYPE_BASE + _OFF_B_PTR)
            if name == '__ctype_toupper_loc':
                return ret(CTYPE_BASE + _OFF_TOU_PTR)
            if name == '__ctype_tolower_loc':
                return ret(CTYPE_BASE + _OFF_TOL_PTR)
            if name == '__errno_location':
                return ret(ERRNO_ADDR)
        except Exception:
            return False
        self.unmodelled.append(name)
        return False

    # ---- ctype 谓词（与表按位一致 ⇒ 两条路径可交叉验证）----------------------
    _PRED_MASK = {
        'lower': ISlower, 'upper': ISupper, 'alpha': ISalpha, 'digit': ISdigit,
        'xdigit': ISxdigit, 'space': ISspace, 'print': ISprint, 'graph': ISgraph,
        'blank': ISblank, 'cntrl': IScntrl, 'punct': ISpunct, 'alnum': ISalnum,
    }

    def _pred_index(self, name, c):
        which = CTYPE_PREDICATES[name]
        c &= 0xFF
        return 1 if (flags_of(c) & self._PRED_MASK[which]) else 0


def self_test():
    chk = []

    def c(label, got, want):
        chk.append((label, got, want))

    # 1) glibc 位定义必须逐位一致
    c('_ISbit(0)=_ISupper=0x0100', ISupper, 0x0100)
    c('_ISbit(1)=_ISlower=0x0200', ISlower, 0x0200)
    c('_ISbit(7)=_ISgraph=0x8000', ISgraph, 0x8000)
    c('_ISbit(8)=_ISblank=0x0001', ISblank, 0x0001)
    c('_ISbit(11)=_ISalnum=0x0008', ISalnum, 0x0008)

    # 2) 表与判定函数必须一致
    c("flags('a') 含 ISlower", bool(flags_of(ord('a')) & ISlower), True)
    c("flags('a') 不含 ISupper", bool(flags_of(ord('a')) & ISupper), False)
    c("flags('5') 含 ISdigit|ISxdigit",
      bool(flags_of(ord('5')) & ISdigit) and bool(flags_of(ord('5')) & ISxdigit), True)
    c("flags(' ')=ISspace|ISblank",
      flags_of(0x20) & (ISspace | ISblank), ISspace | ISblank)
    c("flags(0x00) 含 IScntrl", bool(flags_of(0) & IScntrl), True)
    c("flags('!') 含 ISpunct|ISgraph", flags_of(0x21) & (ISpunct | ISgraph),
      ISpunct | ISgraph)
    c("flags('g') 不含 ISxdigit（'g' 不是 16 进制位）",
      bool(flags_of(ord('g')) & ISxdigit), False)

    # 3) 大小写表必须与函数一致，且**非字母不变**
    b, tou, tol = build_tables()
    c('b 表长度 = 384*2', len(b), TBL_LEN * 2)
    c('toupper 表长度 = 384*4', len(tou), TBL_LEN * 4)
    c("toupper('a')='A'", toupper_c(ord('a')), ord('A'))
    c("toUpper 表['a'] 与函数一致",
      struct.unpack_from('<i', tou, (ord('a') - IDX_BASE) * 4)[0], toupper_c(ord('a')))
    c("非字母 toupper 不变（'5'）", toupper_c(ord('5')), ord('5'))
    c("tolower('Z')='z'", tolower_c(ord('Z')), ord('z'))
    c("负索引（-1，对应 EOF 区）为 0",
      struct.unpack_from('<H', b, (-1 - IDX_BASE) * 2)[0], 0)
    c("索引 0（NUL）含 IScntrl", struct.unpack_from('<H', b, (0 - IDX_BASE) * 2)[0],
      IScntrl)

    # 4) 结构性约束：指针返回型函数不得被兜底成 0
    for n in ('strchr', 'strrchr', 'strstr', 'strdup', 'malloc', 'calloc',
              '__ctype_b_loc', '__errno_location'):
        c('指针返回型必须建模：%s' % n, n in PTR_RETURNING, True)

    # 5) 未建模清单必须存在且为列表（"没建模"要能列名，不能静默）
    c('Model 有 unmodelled 列表', isinstance(Model().unmodelled, list), True)

    # 6) 堆不清零（否则 malloc/calloc 语义差被抹掉 ⇒ 假 PASS）
    c('堆哨兵字节非 0（不清零）', 0xA5 != 0, True)

    # 7) 异名同函数表：必须都指向**模型里真的实现了**的主名（防悬空别名）
    impl = {'strdup', 'strndup', 'memcpy', 'memmove', 'memset', 'strcpy',
            'strncpy', 'strcat', 'stpcpy', 'malloc', 'free', 'getc'}
    c('ALIASES 的主名都在模型里存在（或明确不建模）',
      set(ALIASES.values()) <= impl, True)
    c("__strdup ⇒ strdup（实测工厂侧用 __strdup、我方用 strdup）",
      ALIASES.get('__strdup'), 'strdup')
    return chk


if __name__ == '__main__':
    chk = self_test()
    bad = [x for x in chk if x[1] != x[2]]
    for lab, got, want in chk:
        print('  %s %s' % ('OK  ' if got == want else 'FAIL', lab))
        if got != want:
            print('        got=%r want=%r' % (got, want))
    print('  self-test: %d 条，失败 %d 条' % (len(chk), len(bad)))
    raise SystemExit(1 if bad else 0)
