#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: run_drone9_tmux.sh [--auto-udp] [--skip-udp] [--skip-aero]

默认流程：
  1. 进入 Aerostack2 工程目录，source ROS + Aerostack2 环境后调用 ./launch_as2.bash -n drone9。
     该脚本会自动创建名为 "drone9" 的 tmux 会话并附着，方便你观察启动；
     确认正常后，用 Ctrl+B 再按 d 脱离 tmux 才能继续下一步。
  2. 返回本脚本后，它会询问是否启动 UDP/Nexfi/GPS 测试；若确认，则另起 tmux 会话
     (默认名 "drone9_udp") 来运行 ./start_test.sh receiver ...，SSH 断开也不会中断。

可选项：
  --auto-udp   不提示，Aerostack2 启动完成后立即开启 UDP。
  --skip-udp   只启动 Aerostack2。
  --skip-aero  不启动 Aerostack2，仅创建 UDP tmux (假设你已手动拉起)。
  -h|--help    显示本说明。

环境变量可覆盖路径：
  ROS_SETUP=/opt/ros/humble/setup.bash
  AEROSTACK_WS=/home/amov/aerostack2_ws
  UDP_PROJECT=/home/amov/udp_test/udp-latency
  VENV_ACTIVATE=$UDP_PROJECT/venv/bin/activate
USAGE
}

AUTO_START_UDP=${AUTO_START_UDP:-false}
SKIP_UDP=${SKIP_UDP:-false}
SKIP_AERO=${SKIP_AERO:-false}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto-udp)
            AUTO_START_UDP=true
            ;;
        --skip-udp)
            SKIP_UDP=true
            ;;
        --skip-aero)
            SKIP_AERO=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

if ! command -v tmux >/dev/null 2>&1; then
    echo "tmux is required but not found" >&2
    exit 1
fi

ROS_SETUP=${ROS_SETUP:-/opt/ros/humble/setup.bash}
AEROSTACK_WS=${AEROSTACK_WS:-/home/amov/aerostack2_ws}
AS2_SETUP=${AS2_SETUP:-${AEROSTACK_WS}/install/setup.bash}
UDP_PROJECT=${UDP_PROJECT:-/home/amov/udp_test/udp-latency}
VENV_ACTIVATE=${VENV_ACTIVATE:-${UDP_PROJECT}/venv/bin/activate}
AEROSTACK_PROJECT=${AEROSTACK_PROJECT:-${AEROSTACK_WS}/src/project_dji_psdk}
LAUNCH_SCRIPT="${AEROSTACK_PROJECT}/launch_as2.bash"
ROS_DOMAIN_ID_VALUE=${ROS_DOMAIN_ID_VALUE:-9}
DRONE_ID=${DRONE_ID:-drone9}
AEROSTACK_SESSION=${AEROSTACK_SESSION:-$DRONE_ID}
UDP_SESSION_NAME=${UDP_SESSION_NAME:-${DRONE_ID}_udp}

require_path() {
    local path="$1"
    if [[ ! -e "$path" ]]; then
        echo "Required path missing: $path" >&2
        exit 1
    fi
}

require_path "$ROS_SETUP"
require_path "$AS2_SETUP"
require_path "$VENV_ACTIVATE"
require_path "$LAUNCH_SCRIPT"

run_aerostack() {
    if tmux has-session -t "$AEROSTACK_SESSION" 2>/dev/null; then
        echo "Aerostack tmux session '$AEROSTACK_SESSION' 已在运行，跳过启动。"
        return
    fi

    echo "[drone9] 即将启动 Aerostack2。launch_as2 会自动进入 tmux session '$AEROSTACK_SESSION'。"
    echo "[drone9] 在该 tmux 中观察启动，确认正常后按 Ctrl+B 再按 d 返回此脚本。"
    (
        set +u
        source "$ROS_SETUP"
        source "$AS2_SETUP"
        export ROS_DOMAIN_ID="$ROS_DOMAIN_ID_VALUE"
        cd "$AEROSTACK_PROJECT"
        ./launch_as2.bash -n "$DRONE_ID"
    )
    echo "[drone9] 已从 Aerostack2 tmux 客户端返回 (session '$AEROSTACK_SESSION' 仍在后台)。"
}

run_udp_tmux() {
    if tmux has-session -t "$UDP_SESSION_NAME" 2>/dev/null; then
        echo "UDP tmux session '$UDP_SESSION_NAME' 已存在，放弃重复创建。"
        return
    fi

    local bash_body start_cmd
    bash_body=$(cat <<COMMAND
set -eo pipefail
cd "$UDP_PROJECT"
source "$VENV_ACTIVATE"
source "$ROS_SETUP"
source "$AS2_SETUP"
export ROS_DOMAIN_ID="$ROS_DOMAIN_ID_VALUE"
./start_test.sh receiver --local-ip=192.168.104.109 --peer-ip=192.168.104.112 --enable-nexfi --nexfi-ip=192.168.104.9 --time=2400 --enable-gps --drone-id=drone9 --gps-interval=0.1 --nexfi-interval=0.1 --enable-static-route --static-route-via=192.168.104.12
COMMAND
)
    printf -v start_cmd 'bash -lc %q' "$bash_body"

    tmux new-session -d -s "$UDP_SESSION_NAME" -n udp
    tmux send-keys -t "$UDP_SESSION_NAME:udp" "$start_cmd" C-m
    echo "[drone9] UDP 测试已在 tmux session '$UDP_SESSION_NAME' 中运行。"
    echo "[drone9] 现在将自动 attach。按 Ctrl+B d 可脱离，保持后台运行。"
    tmux attach -t "$UDP_SESSION_NAME"
}

if [[ "$SKIP_AERO" == "false" ]]; then
    run_aerostack
fi

if [[ "$SKIP_UDP" == "true" ]]; then
    echo "[drone9] 按要求跳过 UDP/Nexfi 测试。"
    exit 0
fi

if [[ "$AUTO_START_UDP" == "false" ]]; then
    read -r -p "[drone9] 是否继续启动 UDP/Nexfi/GPS 测试? (y/N) " answer || true
    case "$answer" in
        y|Y|yes|YES)
            ;;
        *)
            echo "[drone9] 用户选择不启动 UDP/Nexfi 测试。"
            exit 0
            ;;
    esac
fi

run_udp_tmux
