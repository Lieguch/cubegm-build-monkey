# ModelScope mynotebook 构建指南（替代 CNB 云开发）

## 背景

CNB 云开发额度已耗尽，无法再用作交互式构建环境。ModelScope mynotebook 提供**免费 CPU 环境（8核32G，长期免费，持久化 /mnt/workspace）**，可作为替代构建路径。

## 资源规格

| 项目 | 规格 |
|------|------|
| 环境 | PAI-DSW CPU 环境 |
| CPU/内存 | 8核 / 32G |
| 存储 | /mnt/workspace/ 持久化 |
| 免费额度 | 长期免费 CPU，单次实例最长 10 小时，空闲 >1 小时自动超时 |
| 账号 | 需登录 ModelScope 账号并绑定阿里云账号 |

## 使用步骤

### 1. 获取免费额度

1. 访问 https://modelscope.cn/my/mynotebook
2. 登录 ModelScope 账号（无账号先注册）
3. 根据提示绑定阿里云账号（需勾选全部授权选项，否则授权失败）
4. 绑定成功后即可获得免费初始资源
5. 后续使用无需重复绑定，仅需确保阿里云账号处于登录态

### 2. 创建 Notebook 实例

1. 在 https://modelscope.cn/my/mynotebook 页面点击"创建实例"或"启动 Notebook"
2. 选择 CPU 环境（GPU 额度有限，CPU 长期免费）
3. 实例启动后，在浏览器中打开 JupyterLab 界面
4. 打开终端（Terminal）开始构建

### 3. 构建 rkgame 重建二进制

```bash
# 进入工作目录（持久化目录）
cd /mnt/workspace

# 克隆仓库
git clone https://github.com/Lieguch/cubegm-build-monkey.git
cd cubegm-build-monkey

# ★ R277：获取 stb_truetype v1.22 头文件（与原厂 ≤1.22 对齐，修复 B6A）
#   v1.26 (2021-08-28) "fix broken rasterizer" 改变字体 rasterization 输出，
#   导致 frame_hash_abi 与原厂分歧（Factory=dfdaf563 vs Rebuild=ae825958）。
git clone --depth 1 --branch v1.22 https://github.com/nothings/stb.git /tmp/stb_v122
cp /tmp/stb_v122/stb_truetype.h src/upstream/stb/stb_truetype.h
head -1 src/upstream/stb/stb_truetype.h   # 应输出：// stb_truetype.h - v1.22 - public domain

# 安装 zig（与 CI 同一工具链）
pip install ziglang==0.16.0
ZIG="$(python3 -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))')"
chmod +x "$ZIG"
export CC="$ZIG cc"
export ZIG_GLOBAL_CACHE_DIR=/mnt/workspace/.zig-cache

# 获取 Bootlin63 工具链（sysroot + 真 glibc 2.24 头）
sh tools/fetch_bootlin63.sh

# 编译上游组件（stb_truetype v1.22 对齐原厂）
sh tools/build_upstream.sh

# 严格原型编译门禁（214/214 零错误）
sh tools/check_arity_compile.sh

# 完整链接
sh tools/link_full.sh

# 产物：build/rkgame.rebuilt.elf
ls -la build/rkgame.rebuilt.elf
sha256sum build/rkgame.rebuilt.elf
```

### 替代方案：GitHub Codespaces（推荐，与 GitHub 仓库直接集成）

如不想使用 ModelScope mynotebook，也可直接在 GitHub 仓库中使用 Codespaces：

1. 访问 https://github.com/Lieguch/cubegm-build-monkey/codespaces/new
2. 点击 "Create codespace on master"，容器将自动安装工具链（见 `.devcontainer/post-create.sh`）
3. 在 Codespaces 终端中执行相同的构建命令（含 stb_truetype v1.22 替换）

Codespaces 免费额度：每月 120 核心小时，足够多次构建。

### 4. 推送触发 GitHub CI

构建完成后，将代码推送到 GitHub 触发 CI 验证：

```bash
git add -A
git commit -m "R277: build via ModelScope mynotebook"
git push github master
```

GitHub Actions 将自动运行：
- `1to1-verify`：静态门禁（编译/链接/ABI）
- `1to1-qemu-behav`：动态门禁（qemu-user 行为差分，B6/B6A）

### 5. 注意事项

- 实例空闲 >1 小时会自动超时，长时间构建需定期活动
- 单次实例最长 10 小时，构建完成后建议手动关闭实例避免额度消耗
- /mnt/workspace/ 是持久化目录，实例重启后数据保留
- 构建需要网络访问 GitHub（获取源码、依赖等）

## 预期结果

| 判据 | 预期值 |
|------|--------|
| Arity 门禁 | 214/214 零错误 |
| 完整链接 | build/rkgame.rebuilt.elf（~5.5 MB） |
| 1to1-verify CI | 全绿 |
| 1to1-qemu-behav CI | B6/B6A 全绿（stb_truetype v1.22 对齐后） |
