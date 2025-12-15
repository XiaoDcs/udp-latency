# 脚本使用指南

本指南适用于 `scripts/run_drone9_tmux.sh`（接收端）与 `scripts/run_drone12_tmux.sh`（发送端），帮助你用 tmux 自动化启动 Aerostack2 与 UDP/Nexfi/GPS 测试流程。

## 1. 执行前准备

- 确保 ROS2 Humble、Aerostack2、`udp-latency` 项目以及虚拟环境 `venv` 均已就绪。
- 两台机分别保持各自对应的 IP、Nexfi、静态路由配置，且能正常访问 `/home/amov/aerostack2_ws` 与 `/home/amov/udp_test/udp-latency`。
- 默认路径/变量可以通过环境变量覆盖（示例：`ROS_SETUP=/opt/ros/humble/setup.bash`、`AEROSTACK_WS=/home/amov/aerostack2_ws` 等），详见脚本头部注释。

## 2. drone9（接收端）脚本

```bash
cd /home/amov/udp_test/udp-latency
./scripts/run_drone9_tmux.sh [可选参数]
```

默认流程：
1. 脚本会 source ROS + Aerostack2 环境，进入 `/home/amov/aerostack2_ws/src/project_dji_psdk`，执行 `./launch_as2.bash -n drone9`，并自动进入由 `launch_as2` 创建的 tmux 会话（名称通常为 `drone9`）。  
2. 在该 tmux 中观察所有窗口启动情况。确认正常后，使用 `Ctrl+B` 再按 `d` 脱离，脚本才会继续下一步。
3. 返回脚本后，会询问是否启动 UDP/Nexfi/GPS 测试。确认后，它会创建新的 tmux 会话 `drone9_udp` 并执行：
   ```
   ./start_test.sh receiver --local-ip=192.168.104.109 --peer-ip=192.168.104.112 \
     --enable-nexfi --nexfi-ip=192.168.104.9 --time=1000 \
     --enable-gps --drone-id=drone9 --gps-interval=0.1 \
     --nexfi-interval=0.1 --enable-static-route --static-route-via=192.168.104.12
   ```
   tmux 会保持该进程，即使 SSH 断开也不会停止。

可选参数：
- `--auto-udp`：跳过确认，Aerostack2 启动结束后立即进入 UDP 阶段。
- `--skip-udp`：仅启动 Aerostack2，不运行通信脚本。
- `--skip-aero`：跳过 Aerostack2 步骤，仅创建 UDP tmux（适合已经手动启动的情况）。

## 3. drone12（发送端）脚本

```bash
cd /home/amov/udp_test/udp-latency
./scripts/run_drone12_tmux.sh [可选参数]
```

行为与接收端脚本一致，只是默认 `ROS_DOMAIN_ID=12`，Aerostack2 会话叫 `drone12`，UDP 会话叫 `drone12_udp`，运行命令为：

```
./start_test.sh sender --local-ip=192.168.104.112 --peer-ip=192.168.104.109 \
  --enable-nexfi --nexfi-ip=192.168.104.12 --time=1000 \
  --enable-gps --drone-id=drone12 --gps-interval=0.1 \
  --nexfi-interval=0.1 --enable-static-route --static-route-via=192.168.104.9
```

同样支持 `--auto-udp / --skip-udp / --skip-aero`。

## 4. tmux 常用操作

| 目的 | 操作 |
| --- | --- |
| 查看所有 session | `tmux ls` |
| 附着到指定 session | `tmux attach -t <session_name>` |
| 从 session 脱离 | 在 tmux 内按 `Ctrl+B`，松开后按 `d` |
| 关闭当前 pane / shell | 在 pane 中执行 `exit` 或按 `Ctrl+D` |
| 直接结束某个 session | `tmux kill-session -t <session_name>` |
| 重命名 session（在 tmux 内） | `Ctrl+B` 然后 `:` 输入 `rename-session <new_name>` |

提示：
- 如果脚本提示 session 已存在，大概率是之前的 tmux 仍在运行。可用 `tmux ls` 查看，确认后再 `tmux attach` 或 `tmux kill-session`。
- 需要同时查看 Aerostack2 与 UDP 输出时，可在不同终端分别 `tmux attach -t drone9` 与 `tmux attach -t drone9_udp`（或 drone12 对应 session）。

## 5. 结束与退出

1. **先停止 UDP/Nexfi/GPS 测试**  
   - 接收端：`tmux attach -t drone9_udp`，在窗口内按 `Ctrl+C` 结束 `start_test.sh`，再 `exit`。  
   - 发送端：`tmux attach -t drone12_udp`，同样 `Ctrl+C` → `exit`。  
   - 如果确定不再需要，可直接 `tmux kill-session -t droneX_udp`，但推荐先 `Ctrl+C` 让脚本做善后。

2. **再关闭 Aerostack2 tmux**  
   - 从 `udp-latency/scripts` 目录下运行包装脚本：  
     ```bash
     ./stop_aerostack_tmux.sh drone9
     ./stop_aerostack_tmux.sh drone9 drone12   # 同时停止多台
     ```  
   - 如果希望同时结束 UDP tmux（如 `drone9_udp`），可加 `--kill-udp`：  
     ```bash
     ./stop_aerostack_tmux.sh --kill-udp drone9
     ./stop_aerostack_tmux.sh --kill-udp drone9 drone12
     ```  
   - 该脚本会调用 `~/aerostack2_ws/src/project_dji_psdk/stop_tmuxinator_as2.bash`，依次对目标 session 中的所有窗口发送 `Ctrl+C`，然后 kill session。  
   - 也可直接到 Aerostack2 工程目录执行原始脚本：  
     ```bash
     cd ~/aerostack2_ws/src/project_dji_psdk
     ./stop_tmuxinator_as2.bash drone9
     ```

3. **收尾检查**  
   - `tmux ls` 确认 `droneX`、`droneX_udp` 均已消失。  
   - 若 `stop_aerostack_tmux.sh` 正在 tmux 会话内执行，它也会自动关闭当前 session，因此最好在普通终端运行。

## 6. 常见问题

- **ROS setup 报 `unbound variable`**：脚本已将 `set -eo pipefail` 放在 `source` 前，避免 `setup.bash` 内部使用未定义变量导致中断。如仍出现异常，检查自定义环境变量是否正确。
- **UDP 会话未启动**：确认你在 Aerostack2 tmux 中已经脱离（`Ctrl+B d`），脚本才会继续；或使用 `--auto-udp` 自动衔接。
- **需要修改参数**：可直接编辑 `run_drone*_tmux.sh` 中 `start_test.sh` 的参数，或在脚本外层包一层自定义脚本。

将本指南与脚本放在 `scripts/` 目录下，方便在现场设备上快速查阅。祝测试顺利！ 
