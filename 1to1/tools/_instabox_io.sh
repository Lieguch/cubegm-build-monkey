#!/usr/bin/env bash
# _instabox_io.sh —— 按 **InstaBox 官方 API** 上传/下载文件（不是 exec + base64）。
#
# 为什么必须有这个文件（R308 事故）：
#   `ibx.sh put/get` 自己拼 `printf %s '<base64>' | base64 -d` 塞进 exec 的 cmd，
#   而官方 `POST /v1/machines/{id}/exec` 的 **cmd 请求体 ~64 KiB 就 400 Bad Request**
#   （INSTABOX.md §8 已实测记录）。本轮传 2.8 MiB 资产时连 128 KiB 分片都 400，
#   只有 32 KiB 能过 ⇒ 白烧了 3 轮。
#   官方正路（https://instabox.sh/docs/api/commands.md）：
#     PUT  /v1/machines/{id}/files?path=<abs>&parents=true   --data-binary @file  ≤5 GiB，返回 sha256
#     GET  /v1/machines/{id}/files/content?path=<abs>        -o file              任意大小
#     POST /v1/machines/{id}/files/upload-url                签名 URL（大文件/断点）
#     CLI: instabox push <box> LOCAL [REMOTE] / instabox pull <box> REMOTE [LOCAL]
#
# 用法：
#   _instabox_io.sh put  <local-file> <remote-abs-path>
#   _instabox_io.sh get  <remote-abs-path> <local-file>
#   _instabox_io.sh info <remote-abs-path>
# 环境变量：IBX_KEYFILE（默认 ~/.config/instabox/key）、IBX_MACHINE（默认取列表第一台）、
#          INSTABOX_API_URL（默认 https://api.instabox.sh）
set -uo pipefail
KEYFILE="${IBX_KEYFILE:-$HOME/.config/instabox/key}"
KEY="${INSTABOX_API_KEY:-$(cat "$KEYFILE" 2>/dev/null || true)}"
API="${INSTABOX_API_URL:-https://api.instabox.sh}"
[ -n "${KEY// }" ] || { echo "找不到 API key：$KEYFILE" >&2; exit 2; }
if [ -z "${IBX_MACHINE:-}" ]; then
  IBX_MACHINE="$(curl -sS -m 30 -H "X-API-Key: $KEY" "$API/v1/machines" \
    | python3 -c 'import sys,json;d=json.load(sys.stdin);ms=d.get("machines") or [];print(ms[0]["id"] if ms else "")')"
fi
[ -n "$IBX_MACHINE" ] || { echo "找不到机器" >&2; exit 3; }
# ★ 官方示例的 `path` 就是**裸绝对路径**，不做 URL 编码。
#   实测两次踩坑（R308）：① 全编码（safe=""）把 `/` 变 `%2F` ⇒ 服务端 400；
#   ② 在 Git Bash/MSYS 下 `python3 -c '...safe="/"...'` 的 `"/"` 被路径转换污染
#      ⇒ 服务端报 `path must be absolute`。⇒ 零依赖：直接用裸路径。
urlq() { printf '%s' "$1"; }

case "${1:-}" in
  put)
    L="${2:-}"; R="${3:-}"
    [ -f "$L" ] && [ -n "$R" ] || { echo "用法: put <local> <remote-abs>" >&2; exit 2; }
    echo "PUT  $L -> $R ($(wc -c < "$L") B)"
    RESP="$(curl -sS -m 600 -X PUT \
      "$API/v1/machines/$IBX_MACHINE/files?path=$(urlq "$R")&parents=true" \
      -H "X-API-Key: $KEY" -H 'Content-Type: application/octet-stream' \
      --data-binary "@$L")" || exit 1
    echo "$RESP"
    REMOTE_SHA="$(printf '%s' "$RESP" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("sha256",""))' 2>/dev/null || true)"
    LOCAL_SHA="$(sha256sum "$L" | cut -d' ' -f1)"
    if [ "$REMOTE_SHA" != "$LOCAL_SHA" ]; then
      echo "★★ sha256 不一致：remote=$REMOTE_SHA local=$LOCAL_SHA" >&2; exit 4
    fi
    echo "sha256 校验一致：$LOCAL_SHA"
    ;;
  get)
    R="${2:-}"; L="${3:-}"
    [ -n "$R" ] && [ -n "$L" ] || { echo "用法: get <remote-abs> <local>" >&2; exit 2; }
    curl -sS -m 600 "$API/v1/machines/$IBX_MACHINE/files/content?path=$(urlq "$R")" \
      -H "X-API-Key: $KEY" -o "$L" || exit 1
    echo "GET  $R -> $L ($(wc -c < "$L") B)"
    ;;
  info)
    R="${2:-}"
    [ -n "$R" ] || { echo "用法: info <remote-abs>" >&2; exit 2; }
    curl -sS -m 60 "$API/v1/machines/$IBX_MACHINE/files?path=$(urlq "$R")" -H "X-API-Key: $KEY"; echo
    ;;
  *) echo "用法: _instabox_io.sh put|get|info ..." >&2; exit 2 ;;
esac
