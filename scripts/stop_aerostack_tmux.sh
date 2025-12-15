#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
用法: ./scripts/stop_aerostack_tmux.sh [--kill-udp] drone9 [drone12 ...]

作用：包装 ~/aerostack2_ws/src/project_dji_psdk/stop_tmuxinator_as2.bash，
      让你可以在 udp-latency/scripts 目录下快速关闭指定 Aerostack2 tmux 会话。

参数：
  --kill-udp  同时 kill 掉对应的 UDP tmux session（例如 drone9 -> drone9_udp）。
  droneX     无人机命名空间，可一次传多个，例如：
             ./scripts/stop_aerostack_tmux.sh drone9 drone12
USAGE
}

KILL_UDP=false
namespaces=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --kill-udp)
            KILL_UDP=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            namespaces+=("$1")
            ;;
    esac
    shift
done

if [[ ${#namespaces[@]} -eq 0 ]]; then
    usage
    exit 1
fi

TARGET_DIR=${TARGET_DIR:-/home/amov/aerostack2_ws/src/project_dji_psdk}
TARGET_SCRIPT="$TARGET_DIR/stop_tmuxinator_as2.bash"

if [[ "$KILL_UDP" == "true" ]]; then
    if ! command -v tmux >/dev/null 2>&1; then
        echo "启用 --kill-udp 需要 tmux，但当前环境未找到 tmux。" >&2
        exit 1
    fi

    for ns in "${namespaces[@]}"; do
        udp_session="${ns}_udp"
        if tmux has-session -t "$udp_session" 2>/dev/null; then
            echo "正在关闭 UDP tmux session: $udp_session"
            tmux kill-session -t "$udp_session" 2>/dev/null || echo "UDP tmux session '$udp_session' 已不存在，跳过。"
        else
            echo "UDP tmux session '$udp_session' 未运行，跳过。"
        fi
    done
fi

if [[ ! -x "$TARGET_SCRIPT" ]]; then
    echo "找不到目标脚本: $TARGET_SCRIPT" >&2
    exit 1
fi

combined_namespaces=$(printf "%s," "${namespaces[@]}")
combined_namespaces=${combined_namespaces%,}

exec "$TARGET_SCRIPT" "$combined_namespaces"
