"""SSH 远程管理模块"""

import subprocess
from dataclasses import dataclass
from typing import Optional


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

    def run_command(self, command: str, timeout: int = 30) -> tuple[bool, str]:
        """执行远程命令"""
        try:
            cmd = self._build_ssh_cmd([command])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, result.stderr.strip() or result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)

    def read_remote_file(self, remote_path: str) -> tuple[bool, str]:
        """读取远程文件内容"""
        return self.run_command(f"cat {remote_path}")

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
