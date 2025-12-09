#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
用法: ./scripts/stop_aerostack_tmux.sh drone9 [drone12 ...]

作用：包装 ~/aerostack2_ws/src/project_dji_psdk/stop_tmuxinator_as2.bash，
      让你可以在 udp-latency/scripts 目录下快速关闭指定 Aerostack2 tmux 会话。

参数：
  droneX     无人机命名空间，可一次传多个，例如：
             ./scripts/stop_aerostack_tmux.sh drone9 drone12
USAGE
}

if [[ $# -eq 0 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    usage
    if [[ $# -eq 0 ]]; then
        exit 1
    else
        exit 0
    fi
fi

TARGET_DIR=${TARGET_DIR:-/home/amov/aerostack2_ws/src/project_dji_psdk}
TARGET_SCRIPT="$TARGET_DIR/stop_tmuxinator_as2.bash"

if [[ ! -x "$TARGET_SCRIPT" ]]; then
    echo "找不到目标脚本: $TARGET_SCRIPT" >&2
    exit 1
fi

combined_namespaces=$(printf "%s," "$@")
combined_namespaces=${combined_namespaces%,}

exec "$TARGET_SCRIPT" "$combined_namespaces"
