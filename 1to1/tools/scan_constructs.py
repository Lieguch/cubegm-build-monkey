import os, re, collections, json

ROOT = r'D:/output/rkgame-1to1/src/proprietary'
GHIDRA_TYPES = ['undefined8', 'undefined4', 'undefined2', 'undefined1', 'undefined',
                'uint3', 'uint2', 'uint1', 'uint', 'ulong', 'ushort', 'uchar', 'uint64_t',
                'int64_t', 'uint32_t', 'int32_t', 'uint16_t', 'int16_t', 'uint8_t', 'int8_t',
                'byte', 'sbyte', 'word', 'dword', 'qword', 'code', 'bool', 'size_t',
                'longlong', 'ulonglong', 'float10', 'unknown8']
PSEUDO = ['CONCAT44', 'CONCAT31', 'CONCAT22', 'CONCAT13', 'CONCAT12', 'CONCAT11',
          'SUB84', 'SUB41', 'SUB42', 'SUB44', 'SUB168', 'SUB164', 'SUB161',
          'ZEXT48', 'ZEXT44', 'ZEXT28', 'SEXT48', 'SEXT44', 'ZEXT14', 'SEXT14',
          'SBA', 'SBORROW', 'CARRY', 'POPCOUNT', 'ABS', 'NAN', 'INFINITY', 'ROUND',
          'SWAP', 'NEAREST', 'PTRSUB', 'PTRADD', 'SEGMENT', 'OPCODE2',
          'in_FSR', 'in_FPSCR', 'in_GQR', 'in_stack_', 'unaff_', 'extraout_', 'in_r0x',
          'in_lr', 'in_rett', 'RegisterGlobals']

files = []
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if f.endswith('.c'):
            files.append(os.path.join(dp, f))

types = collections.Counter()
pseudo = collections.Counter()
labels = collections.Counter()
misc = collections.Counter()

IDENT = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\b')
for p in files:
    t = open(p, encoding='utf-8', errors='replace').read()
    # 去掉注释与字符串，避免噪声
    t2 = re.sub(r'/\*.*?\*/', ' ', t, flags=re.S)
    t2 = re.sub(r'//[^\n]*', ' ', t2)
    t2 = re.sub(r'"(?:[^"\\]|\\.)*"', '""', t2)
    for tp in GHIDRA_TYPES:
        for m in re.finditer(r'\b' + tp + r'\b', t2):
            types[tp] += 1
    for ps in PSEUDO:
        n = len(re.findall(r'\b' + ps + r'\w*', t2))
        if n:
            pseudo[ps] += n
    for m in re.finditer(r'\b(LAB_[0-9a-f]+|switchD_[0-9a-f]+|code_r0x[0-9a-f]+|'
                         r'joined_r0x[0-9a-f]+|default_?[A-Za-z_]*|UNK_[0-9a-f]+|'
                         r'FUN_[0-9a-f]+|_DAT_[0-9a-f]+)', t2):
        labels[m.group(1).split('_')[0] if m.group(1).startswith(('LAB_', 'switchD_', 'code_r0x',
                                                                  'joined_r0x', 'UNK_', 'FUN_',
                                                                  '_DAT_'))
               else m.group(1)] += 1
    for m in re.finditer(r'\b(__[A-Za-z0-9_]+)\b', t2):
        misc[m.group(1)] += 1

print('扫描 %d 个函数文件' % len(files))
print()
print('=== 1. Ghidra 私有类型（需 typedef）===')
for k, v in types.most_common():
    print('   %-14s %6d' % (k, v))
print()
print('=== 2. Ghidra 伪算子（需宏实现）===')
for k, v in pseudo.most_common(30):
    print('   %-14s %6d' % (k, v))
print()
print('=== 3. Ghidra 标签（需 goto 目标）===')
for k, v in labels.most_common(12):
    print('   %-16s %6d' % (k, v))
print()
print('=== 4. 双下划线内建/特殊符号 Top25 ===')
for k, v in misc.most_common(25):
    print('   %-30s %6d' % (k, v))

json.dump({'files': len(files), 'types': dict(types), 'pseudo': dict(pseudo),
           'labels': dict(labels), 'misc': dict(misc)},
          open(r'D:/output/rkgame-1to1/ledger/ghidra_constructs.json', 'w', encoding='utf-8'),
          indent=1, ensure_ascii=False)
print()
print('-> ledger/ghidra_constructs.json')
