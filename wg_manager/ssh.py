"""SSH 远程管理模块"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import REMOTE_WG_DIR


@dataclass
class SSHConfig:
    """SSH 配置"""
    host: str
    port: int = 22
    user: str = "root"
    key_file: Optional[str] = None


class SSHClient:
    """SSH 客户端 - 使用系统 ssh 命令"""

    def __init__(self, config: SSHConfig):
        self.config = config
        self._connected = False

    def _build_ssh_cmd(self, extra_args: list[str] = None) -> list[str]:
        """构建 SSH 命令"""
        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10"
        ]

        if self.config.port != 22:
            cmd.extend(["-p", str(self.config.port)])

        if self.config.key_file:
            cmd.extend(["-i", self.config.key_file])

        cmd.append(f"{self.config.user}@{self.config.host}")

        if extra_args:
            cmd.extend(extra_args)

        return cmd

    def _build_scp_cmd(self, local_path: str, remote_path: str, upload: bool = True) -> list[str]:
        """构建 SCP 命令"""
        cmd = [
            "scp",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10"
        ]

        if self.config.port != 22:
            cmd.extend(["-P", str(self.config.port)])

        if self.config.key_file:
            cmd.extend(["-i", self.config.key_file])

        remote = f"{self.config.user}@{self.config.host}:{remote_path}"

        if upload:
            cmd.extend([local_path, remote])
        else:
            cmd.extend([remote, local_path])

        return cmd

    def test_connection(self) -> tuple[bool, str]:
        """测试 SSH 连接"""
        try:
            cmd = self._build_ssh_cmd(["echo", "ok"])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self._connected = True
                return True, "连接成功"
            return False, result.stderr.strip() or "连接失败"
        except subprocess.TimeoutExpired:
            return False, "连接超时"
        except Exception as e:
            return False, str(e)

    def run_command(self, command: str) -> tuple[bool, str]:
        """执行远程命令"""
        try:
            cmd = self._build_ssh_cmd([command])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, result.stderr.strip() or result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)

    def upload_file(self, local_path: str, remote_path: str) -> tuple[bool, str]:
        """上传文件到远程服务器"""
        try:
            cmd = self._build_scp_cmd(local_path, remote_path, upload=True)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True, "上传成功"
            return False, result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "上传超时"
        except Exception as e:
            return False, str(e)

    def download_file(self, remote_path: str, local_path: str) -> tuple[bool, str]:
        """从远程服务器下载文件"""
        try:
            cmd = self._build_scp_cmd(local_path, remote_path, upload=False)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True, "下载成功"
            return False, result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "下载超时"
        except Exception as e:
            return False, str(e)

    def read_remote_file(self, remote_path: str) -> tuple[bool, str]:
        """读取远程文件内容"""
        return self.run_command(f"cat {remote_path}")

    def scan_wireguard_configs(self, wg_dir: str = "/etc/wireguard") -> tuple[bool, list[str]]:
        """扫描远程服务器上的 WireGuard 配置文件，返回接口名列表"""
        success, output = self.run_command(f"ls -1 {wg_dir}/*.conf 2>/dev/null")
        if not success or not output.strip():
            return False, []

        interfaces = []
        for line in output.strip().split('\n'):
            if line.endswith('.conf'):
                # 从 /etc/wireguard/wg0.conf 提取 wg0
                import os
                interface = os.path.basename(line).replace('.conf', '')
                interfaces.append(interface)

        return True, interfaces

    def write_remote_file(self, remote_path: str, content: str) -> tuple[bool, str]:
        """写入远程文件（通过 stdin）"""
        try:
            cmd = self._build_ssh_cmd([f"cat > {remote_path}"])
            result = subprocess.run(
                cmd, input=content, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return True, "写入成功"
            return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)


class RemoteWireGuard:
    """远程 WireGuard 管理"""

    def __init__(self, ssh_client: SSHClient, interface: str = "wg0"):
        self.ssh = ssh_client
        self.interface = interface
        self.config_path = f"{REMOTE_WG_DIR}/{interface}.conf"

    def get_config(self) -> tuple[bool, str]:
        """获取远程配置文件"""
        return self.ssh.read_remote_file(self.config_path)

    def update_config(self, config_content: str) -> tuple[bool, str]:
        """更新远程配置文件"""
        return self.ssh.write_remote_file(self.config_path, config_content)

    def get_status(self) -> tuple[bool, str]:
        """获取 WireGuard 状态"""
        return self.ssh.run_command("wg show")

    def restart(self) -> tuple[bool, str]:
        """重启 WireGuard 服务"""
        success, output = self.ssh.run_command(
            f"systemctl restart wg-quick@{self.interface}"
        )
        if success:
            return True, f"WireGuard {self.interface} 已重启"
        return False, output

    def reload(self) -> tuple[bool, str]:
        """重载配置（不中断连接）"""
        # 先检查接口是否存在
        check_success, _ = self.ssh.run_command(f"ip link show {self.interface}")

        if check_success:
            # 接口存在，使用 wg syncconf 热重载
            # 先生成 strip 配置到临时文件，避免进程替换问题
            strip_cmd = (
                f"wg-quick strip {self.interface} > /tmp/{self.interface}_strip.conf && "
                f"wg syncconf {self.interface} /tmp/{self.interface}_strip.conf && "
                f"rm -f /tmp/{self.interface}_strip.conf"
            )
            success, output = self.ssh.run_command(strip_cmd)
            if success:
                return True, "配置已重载"
            # syncconf 失败，尝试重启
            return self.restart()
        else:
            # 接口不存在，需要启动服务
            return self.restart()

    def start(self) -> tuple[bool, str]:
        """启动 WireGuard"""
        return self.ssh.run_command(f"systemctl start wg-quick@{self.interface}")

    def stop(self) -> tuple[bool, str]:
        """停止 WireGuard"""
        return self.ssh.run_command(f"systemctl stop wg-quick@{self.interface}")

    def enable(self) -> tuple[bool, str]:
        """设置开机启动"""
        return self.ssh.run_command(f"systemctl enable wg-quick@{self.interface}")

    def is_active(self) -> bool:
        """检查服务是否运行"""
        success, output = self.ssh.run_command(
            f"systemctl is-active wg-quick@{self.interface}"
        )
        return success and output.strip() == "active"

    def add_peer_live(self, public_key: str, allowed_ips: str,
                      preshared_key: str = "") -> tuple[bool, str]:
        """动态添加 peer（不重启服务）"""
        cmd = f"wg set {self.interface} peer {public_key} allowed-ips {allowed_ips}"
        if preshared_key:
            # 需要通过临时文件传递 preshared key
            cmd = f"echo '{preshared_key}' | wg set {self.interface} peer {public_key} preshared-key /dev/stdin allowed-ips {allowed_ips}"
        return self.ssh.run_command(cmd)

    def remove_peer_live(self, public_key: str) -> tuple[bool, str]:
        """动态移除 peer（不重启服务）"""
        return self.ssh.run_command(
            f"wg set {self.interface} peer {public_key} remove"
        )
