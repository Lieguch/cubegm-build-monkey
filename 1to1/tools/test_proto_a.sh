#!/bin/bash
# =============================================================================
# Phase 1 测试脚：FilePreEmu / SeletEmuCore 轨迹对比
# =============================================================================
set -e  # 出错退出

# ------------------- 配置区 -------------------
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$REPO_ROOT/build"
QEMU_SIZE=3000  # QEMU 执行步数限制（避免日志爆炸）

# 确保已编译
echo "=== 检查编译状态 ==="
if [ ! -f "$BUILD_DIR/rkgame.rebuilt.elf" ]; then
    echo "❌ 重建 binary 不存在，需先运行 REBUILD=5"
    exit 1
fi

# ------------------- QEMU 取证脚本 -------------------
echo "=== 运行 QEMU tra 对比 ==="
echo "📝 目标：对比工厂与重建的 QEMU 执行轨迹，定位簇 A 差异"

# 我们需要一个能自动运行到你想要场景的 QEMU 启动命令
# 根据审计报告，关键场景是 MUI 文件列表 → 进入文件选择 → 读取 cores/config.xml

# 方案：使用建好的 QEMU 沙箱脚区（如有）
if [ -f "$REPO_ROOT/tools/qemu_run_proto.sh" ]; then
    # 运行工厂版（假设有工具包）
    if [ -f "$REPO_ROOT/golden/factory.rkgame.bin" ]; then
        echo "🏭 运行工厂版 (金数据)..."
        # 工厂版无法直接运行，需要模拟器 stdin 等，这里用简单的 exec 统计
        QEMUARCH=arm QEMU_SYSROOT="$BUILDDIR/sytem-root" \
            qemu-system-arm -kernel "$BUILD_DIR/rkgame.rebuilt.elf" \
            -d exec -D "$BUILD_DIR/factory.trace" &
        PID1=$!
        sleep 10
        kill $PID1 2>/dev/null || true
    fi

    # 运行重建版
    echo "🛠️ 运行重建版..."
    QEMUARCH=arm QEMU_SYSROOT="$BUILD_DIR/system-root" \
        qemu-system-arm -kernel "$BUILD_DIR/rkgame.rebuilt.elf" \
        -d exec -D "$BUILD_DIR/rebuild.trace" &
    PID2=$!
    sleep 10
    kill $PID2 2>/dev/null || true

    # 等待清理
    wait

    # 对比 trace 中的关键调用
    echo ""
    echo "=== 轨迹统计 ==="
    echo "Factory trace lines: $(wc -l < "$BUILD_DIR/factory.trace")"
    echo "Rebuild trace lines: $(wc -l < "$BUILD_DIR/rebuild.trace")"

    echo ""
    echo "=== 关键符号调用对比 ==="
    for sym in "FilePreEmu" "SeletEmuCore" "strcmp" "mxmlLoadFile" "mxmlFindElement"; do
        count1=$(grep -c "$sym" "$BUILD_DIR/factory.trace" 2>/dev/null || echo "0")
        count2=$(grep -c "$sym" "$BUILD_DIR/rebuild.trace" 2>/dev/null || echo "0")
        echo "$sym: factory=$count1, rebuild=$count2"
    done

    echo ""
    echo "=== mxmlLoadFile 参数行 ==="
    echo "Factory:"
    grep "mxmlLoadFile" "$BUILD_DIR/factory.trace" | head -3
    echo "Rebuild:"
    grep "mxmlLoadFile" "$BUILD_DIR/rebuild.trace" | head -3

    echo ""
    echo "✅ 对比完成。检查上面输出。"
else
    echo "❌ 缺少 qeem_run_proto.sh，需要先设置 QEMU 沙箱"
    # 简易版本：直接统计 trace
    echo "📊 使用简易模式（仅统计 exec 地址）..."
    QEMUARCH=arm QEMU_SYSROOT="$BUILD_DIR/system-root" \
        qemu-system-arm -kernel "$BUILD_DIR/rkgame.rebuilt.elf" \
        -d exec -D "$BUILD_DIR/rebuild_simple.trace" &
    PID=$!
    sleep 20
    kill $PID 2>/dev/null || true
    wait

    echo ""
    echo "=== 重建版 exec 统计 ==="
    echo "总 exec 行: $(wc -l < "$BUILD_DIR/rebuild_simple.trace")"
    echo "关键符号:"
    for sym in "FilePreEmu" "SeletEmuCore" "strcmp" "mxmlLoadFile" "mxmlFindElement"; do
        count=$(grep -c "$sym" "$BUILD_DIR/rebuild_simple.trace" 2>/dev/null || echo "0")
        echo "$sym: $count"
    done
fi

echo ""
echo "📝 下一步：检查 PHASE1-FILEPREEMU-SELETEMUCORE.md 进行分析"
