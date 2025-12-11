"""WireGuard 管理器核心模块"""

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import CONFIG_DIR, DB_FILE, EXPORT_DIR, DEFAULT_DNS, DEFAULT_MTU, generate_random_port
from .crypto import generate_keypair, generate_preshared_key, generate_public_key
from .database import Database
from .models import Peer, ServerConfig
from .ssh import SSHClient, SSHConfig, RemoteWireGuard


class WireGuardManager:
    """WireGuard 管理器"""

    def __init__(self, server_id: Optional[int] = None):
        self.config_dir = CONFIG_DIR
        self.export_dir = EXPORT_DIR
        self._ensure_dirs()
        self.db = Database(DB_FILE)
        self._server_id = server_id
        self._load_data()
        self._ssh_client: Optional[SSHClient] = None
        self._remote_wg: Optional[RemoteWireGuard] = None

    def _ensure_dirs(self):
        """确保目录存在"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def _load_data(self):
        """加载配置数据"""
        servers = self.db.get_servers()
        if self._server_id:
            self.server = self.db.get_server(self._server_id) or ServerConfig()
        elif servers:
            # 默认使用第一个服务端
            self.server = servers[0]
            self._server_id = self.server.id
        else:
            self.server = ServerConfig()
            self._server_id = None

        if self._server_id:
            self.peers = self.db.get_peers(self._server_id)
        else:
            self.peers = []

    def _refresh_peers(self):
        """刷新客户端列表"""
        if self._server_id:
            self.peers = self.db.get_peers(self._server_id)
        else:
            self.peers = []

    @property
    def server_id(self) -> Optional[int]:
        """当前服务端 ID"""
        return self._server_id

    # ========== 多服务端管理 ==========

    def get_servers(self) -> list[ServerConfig]:
        """获取所有服务端"""
        return self.db.get_servers()

    def switch_server(self, server_id: int) -> bool:
        """切换到指定服务端"""
        server = self.db.get_server(server_id)
        if server:
            self._server_id = server_id
            self.server = server
            self._refresh_peers()
            self._ssh_client = None
            self._remote_wg = None
            return True
        return False

    def switch_server_by_endpoint(self, endpoint: str, interface: str = None) -> bool:
        """根据 endpoint（和可选的 interface）切换服务端"""
        if interface:
            # 精确匹配 endpoint + interface
            server = self.db.get_server_by_endpoint_and_interface(endpoint, interface)
        else:
            # 只匹配 endpoint，如果有多个则返回第一个
            server = self.db.get_server_by_endpoint(endpoint)
        if server:
            return self.switch_server(server.id)
        return False

    def delete_server(self, server_id: int) -> bool:
        """删除服务端及其所有客户端"""
        if self._server_id == server_id:
            # 如果删除的是当前服务端，切换到其他服务端
            servers = self.db.get_servers()
            other_server = next((s for s in servers if s.id != server_id), None)
            if other_server:
                self.switch_server(other_server.id)
            else:
                self._server_id = None
                self.server = ServerConfig()
                self.peers = []

        return self.db.delete_server(server_id)

    # ========== SSH 相关 ==========

    def setup_ssh(self, host: str, port: int = 22, user: str = "root",
                  key_file: Optional[str] = None) -> tuple[bool, str]:
        """配置 SSH 连接"""
        if not self._server_id:
            return False, "请先初始化或选择服务端"

        config = SSHConfig(host=host, port=port, user=user, key_file=key_file)
        self._ssh_client = SSHClient(config)

        success, msg = self._ssh_client.test_connection()
        if success:
            self.db.save_ssh_config(self._server_id, host, port, user)
            self._remote_wg = RemoteWireGuard(self._ssh_client, self.server.interface)
        return success, msg

    def get_ssh_client(self) -> Optional[SSHClient]:
        """获取 SSH 客户端"""
        if self._ssh_client:
            return self._ssh_client

        if not self._server_id:
            return None

        ssh_config = self.db.get_ssh_config(self._server_id)
        if ssh_config:
            config = SSHConfig(**ssh_config)
            self._ssh_client = SSHClient(config)
            return self._ssh_client
        return None

    def get_remote_wg(self) -> Optional[RemoteWireGuard]:
        """获取远程 WireGuard 管理器"""
        if self._remote_wg:
            return self._remote_wg

        client = self.get_ssh_client()
        if client and self.server.interface:
            self._remote_wg = RemoteWireGuard(client, self.server.interface)
            return self._remote_wg
        return None

    # ========== 服务端管理 ==========

    def init_server(self, endpoint: str, address: str = "10.0.0.1/24",
                    port: int = 51820, interface: str = "wg0") -> ServerConfig:
        """初始化服务端配置"""
        # 检查 endpoint + interface 组合是否已存在
        existing = self.db.get_server_by_endpoint_and_interface(endpoint, interface)
        if existing:
            raise ValueError(f"服务端 '{endpoint}:{interface}' 已存在")

        private_key, public_key = generate_keypair()

        try:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True
            )
            default_interface = result.stdout.split()[4] if result.stdout else "eth0"
        except:
            default_interface = "eth0"

        post_up = f"iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o {default_interface} -j MASQUERADE"
        post_down = f"iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o {default_interface} -j MASQUERADE"

        self.server = ServerConfig(
            id=None,  # 新服务端，让数据库自动分配 ID
            private_key=private_key,
            public_key=public_key,
            address=address,
            listen_port=port,
            interface=interface,
            endpoint=endpoint,
            post_up=post_up,
            post_down=post_down
        )
        self.server = self.db.save_server(self.server)
        self._server_id = self.server.id
        self._refresh_peers()
        return self.server

    def import_server(self, private_key: str, endpoint: str,
                      address: str = "10.0.0.1/24", port: int = 51820,
                      interface: str = "wg0", post_up: str = "",
                      post_down: str = "") -> ServerConfig:
        """导入已有服务端配置（通过私钥）"""
        # 检查 endpoint + interface 组合是否已存在
        existing = self.db.get_server_by_endpoint_and_interface(endpoint, interface)
        if existing:
            # 更新现有服务端
            self.server = existing
            self._server_id = existing.id
        else:
            self.server = ServerConfig(id=None)

        public_key = generate_public_key(private_key)

        self.server.private_key = private_key
        self.server.public_key = public_key
        self.server.address = address
        self.server.listen_port = port
        self.server.interface = interface
        self.server.endpoint = endpoint
        self.server.post_up = post_up
        self.server.post_down = post_down

        self.server = self.db.save_server(self.server)
        self._server_id = self.server.id
        self._refresh_peers()
        return self.server

    def import_server_from_config(self, config_path: str, endpoint: str) -> tuple[ServerConfig, list[dict]]:
        """从现有配置文件导入服务端"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        content = config_file.read_text()
        return self._parse_and_import_config(content, endpoint, config_file.stem)

    def import_server_from_remote(self, endpoint: str) -> tuple[ServerConfig, list[dict]]:
        """从远程服务器导入配置"""
        remote_wg = self.get_remote_wg()
        if not remote_wg:
            raise RuntimeError("SSH 未配置")

        success, content = remote_wg.get_config()
        if not success:
            raise RuntimeError(f"读取远程配置失败: {content}")

        return self._parse_and_import_config(content, endpoint, self.server.interface or "wg0")

    def _parse_and_import_config(self, content: str, endpoint: str,
                                  interface: str) -> tuple[ServerConfig, list[dict]]:
        """解析配置内容并导入"""
        private_key = ""
        address = "10.0.0.1/24"
        port = 51820
        post_up = ""
        post_down = ""

        interface_match = re.search(r'\[Interface\](.*?)(?=\[Peer\]|$)', content, re.DOTALL | re.IGNORECASE)
        if interface_match:
            interface_section = interface_match.group(1)

            pk_match = re.search(r'PrivateKey\s*=\s*(\S+)', interface_section)
            if pk_match:
                private_key = pk_match.group(1)

            addr_match = re.search(r'Address\s*=\s*(\S+)', interface_section)
            if addr_match:
                address = addr_match.group(1)

            port_match = re.search(r'ListenPort\s*=\s*(\d+)', interface_section)
            if port_match:
                port = int(port_match.group(1))

            postup_match = re.search(r'PostUp\s*=\s*(.+)$', interface_section, re.MULTILINE)
            if postup_match:
                post_up = postup_match.group(1).strip()

            postdown_match = re.search(r'PostDown\s*=\s*(.+)$', interface_section, re.MULTILINE)
            if postdown_match:
                post_down = postdown_match.group(1).strip()

        if not private_key:
            raise ValueError("配置文件中未找到 PrivateKey")

        server = self.import_server(
            private_key=private_key,
            endpoint=endpoint,
            address=address,
            port=port,
            interface=interface,
            post_up=post_up,
            post_down=post_down
        )

        existing_peers = []
        peer_matches = re.finditer(r'\[Peer\](.*?)(?=\[Peer\]|$)', content, re.DOTALL | re.IGNORECASE)
        for i, match in enumerate(peer_matches):
            peer_section = match.group(1)

            pub_match = re.search(r'PublicKey\s*=\s*(\S+)', peer_section)
            allowed_match = re.search(r'AllowedIPs\s*=\s*(\S+)', peer_section)
            psk_match = re.search(r'PresharedKey\s*=\s*(\S+)', peer_section)
            comment_match = re.search(r'#\s*(.+)$', peer_section, re.MULTILINE)

            if pub_match:
                name = comment_match.group(1).strip() if comment_match else f"imported_peer_{i+1}"
                existing_peers.append({
                    "name": name,
                    "public_key": pub_match.group(1),
                    "preshared_key": psk_match.group(1) if psk_match else "",
                    "allowed_ips": allowed_match.group(1) if allowed_match else ""
                })

        return server, existing_peers

    # ========== 客户端管理 ==========

    def _get_next_ip(self) -> str:
        """获取下一个可用 IP"""
        base = self.server.address.split("/")[0]
        parts = base.split(".")
        base_prefix = ".".join(parts[:3])

        used_ips = self.db.get_used_ips(self._server_id)

        for i in range(2, 255):
            if i not in used_ips:
                return f"{base_prefix}.{i}/32"

        raise RuntimeError("IP 地址池已满")

    def _get_server_network(self) -> str:
        """获取服务端网段 (如 10.1.1.0/24)"""
        base = self.server.address.split("/")[0]
        parts = base.split(".")
        return f"{'.'.join(parts[:3])}.0/24"

    def add_peer(self, name: str, dns: str = DEFAULT_DNS,
                 mtu: int = DEFAULT_MTU, sync_remote: bool = True) -> Peer:
        """添加客户端"""
        if not self._server_id:
            raise RuntimeError("请先初始化或选择服务端")

        if self.db.get_peer_by_name(name, self._server_id):
            raise ValueError(f"客户端名称 '{name}' 已存在")

        private_key, public_key = generate_keypair()
        psk = generate_preshared_key()
        address = self._get_next_ip()

        # 客户端 AllowedIPs 默认为服务端网段
        allowed_ips = self._get_server_network()

        peer = Peer(
            id=None,
            server_id=self._server_id,
            name=name,
            public_key=public_key,
            private_key=private_key,
            preshared_key=psk,
            address=address,
            allowed_ips=allowed_ips,
            dns=dns,
            listen_port=generate_random_port(),
            mtu=mtu,
            created_at=datetime.now().isoformat(),
            enabled=True
        )
        peer = self.db.add_peer(peer)
        self._refresh_peers()

        # 同步到远程服务器
        if sync_remote:
            self._sync_peer_to_remote(peer, action="add")

        return peer

    def remove_peer(self, name: str, sync_remote: bool = True) -> bool:
        """删除客户端"""
        if not self._server_id:
            return False

        peer = self.db.get_peer_by_name(name, self._server_id)
        if not peer:
            return False

        # 保存 public_key 用于远程删除
        public_key = peer.public_key

        # 先从数据库删除
        if self.db.remove_peer(name, self._server_id):
            conf_file = self.export_dir / f"{name}.conf"
            if conf_file.exists():
                conf_file.unlink()
            self._refresh_peers()

            # 同步删除到远程
            if sync_remote:
                self._sync_peer_remove_to_remote(public_key)

            return True
        return False

    def toggle_peer(self, name: str, sync_remote: bool = True) -> Optional[bool]:
        """启用/禁用客户端"""
        if not self._server_id:
            return None

        result = self.db.toggle_peer(name, self._server_id)
        if result is not None:
            self._refresh_peers()
            if sync_remote:
                self._sync_to_remote()
        return result

    def import_existing_peer(self, name: str, public_key: str, address: str,
                             preshared_key: str = "") -> dict:
        """导入已有客户端（仅记录公钥，无法生成客户端配置）"""
        if not self._server_id:
            raise RuntimeError("请先初始化或选择服务端")

        if self.db.get_peer_by_name(name, self._server_id):
            raise ValueError(f"客户端名称 '{name}' 已存在")

        peer = Peer(
            id=None,
            server_id=self._server_id,
            name=name,
            public_key=public_key,
            private_key="",
            preshared_key=preshared_key,
            address=address,
            allowed_ips="",
            dns="",
            created_at=datetime.now().isoformat(),
            enabled=True
        )
        self.db.add_peer(peer)
        self._refresh_peers()
        return {"name": name, "public_key": public_key, "address": address, "imported": True}

    # ========== 配置生成 ==========

    def get_server_config(self) -> str:
        """生成服务端配置文件内容"""
        if not self.server.private_key:
            raise RuntimeError("服务端未初始化")

        config = f"""[Interface]
PrivateKey = {self.server.private_key}
Address = {self.server.address}
ListenPort = {self.server.listen_port}
"""
        if self.server.post_up:
            config += f"PostUp = {self.server.post_up}\n"
        if self.server.post_down:
            config += f"PostDown = {self.server.post_down}\n"

        for peer in self.peers:
            if peer.enabled:
                config += f"""
[Peer]
# {peer.name}
PublicKey = {peer.public_key}
PresharedKey = {peer.preshared_key}
AllowedIPs = {peer.address.split('/')[0]}/32
"""
        return config

    def get_client_config(self, name: str) -> str:
        """生成客户端配置文件内容"""
        if not self._server_id:
            raise RuntimeError("请先选择服务端")

        peer = self.db.get_peer_by_name(name, self._server_id)
        if not peer:
            raise ValueError(f"客户端 '{name}' 不存在")

        if not peer.private_key:
            raise ValueError(f"客户端 '{name}' 是导入的，没有私钥")

        if not self.server.endpoint:
            raise RuntimeError("服务端 endpoint 未配置")

        # 客户端地址使用 /24 网段
        address_ip = peer.address.split("/")[0]
        address_with_mask = f"{address_ip}/24"

        # 构建配置
        config = "# https://www.wireguard.com\n"
        config += "[Interface]\n"
        config += f"Address = {address_with_mask}\n"
        config += f"ListenPort = {peer.listen_port}\n"
        config += f"MTU = {peer.mtu}\n"
        config += f"PrivateKey = {peer.private_key}\n"

        if peer.dns:
            config += f"DNS = {peer.dns}\n"

        config += "\n[Peer]\n"
        # 客户端 AllowedIPs 使用服务端网段
        client_allowed_ips = self._get_server_network()
        config += f"AllowedIPs = {client_allowed_ips}\n"
        config += f"Endpoint = {self.server.endpoint}:{self.server.listen_port}\n"
        config += "PersistentKeepalive = 25\n"
        config += f"PresharedKey = {peer.preshared_key}\n"
        config += f"PublicKey = {self.server.public_key}\n"

        # 添加尾部注释
        config += f"# Client config --> {self.export_dir}/{name}.conf\n"

        return config

    # ========== 导出功能 ==========

    def export_client_config(self, name: str) -> Path:
        """导出客户端配置到文件"""
        config = self.get_client_config(name)
        filepath = self.export_dir / f"{name}.conf"
        with open(filepath, "w") as f:
            f.write(config)
        return filepath

    def export_client_qrcode(self, name: str) -> bool:
        """生成客户端配置二维码（终端显示）"""
        try:
            import qrcode
            config = self.get_client_config(name)
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=1,
                border=1,
            )
            qr.add_data(config)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
            return True
        except Exception as e:
            print(f"生成二维码失败: {e}")
            return False

    def export_server_config(self) -> Path:
        """导出服务端配置到文件"""
        config = self.get_server_config()
        filepath = self.config_dir / f"{self.server.interface}.conf"
        with open(filepath, "w") as f:
            f.write(config)
        return filepath

    # ========== 远程同步 ==========

    def _sync_peer_to_remote(self, peer: Peer, action: str = "add") -> tuple[bool, str]:
        """同步添加客户端到远程服务器（不重启服务）"""
        remote_wg = self.get_remote_wg()
        if not remote_wg:
            return True, "SSH 未配置，跳过远程同步"

        # 1. 先更新配置文件（确保持久化）
        config = self.get_server_config()
        success, msg = remote_wg.update_config(config)
        if not success:
            return False, f"更新远程配置失败: {msg}"

        # 2. 动态添加 peer 到运行中的 WireGuard（不重启）
        allowed_ips = f"{peer.address.split('/')[0]}/32"
        success, msg = remote_wg.add_peer_live(
            peer.public_key, allowed_ips, peer.preshared_key
        )
        if success:
            return True, f"客户端 '{peer.name}' 已同步到远程"

        # 动态更新失败，尝试重载配置
        return remote_wg.reload()

    def _sync_peer_remove_to_remote(self, public_key: str) -> tuple[bool, str]:
        """同步删除客户端到远程服务器（不重启服务）"""
        remote_wg = self.get_remote_wg()
        if not remote_wg:
            return True, "SSH 未配置，跳过远程同步"

        # 1. 先更新配置文件（此时 peer 已从本地数据库删除）
        config = self.get_server_config()
        success, msg = remote_wg.update_config(config)
        if not success:
            return False, f"更新远程配置失败: {msg}"

        # 2. 动态移除 peer（不重启）
        success, msg = remote_wg.remove_peer_live(public_key)
        if success:
            return True, "客户端已从远程移除"

        # 动态更新失败，尝试重载配置
        return remote_wg.reload()

    def _sync_to_remote(self) -> tuple[bool, str]:
        """同步完整配置到远程服务器"""
        remote_wg = self.get_remote_wg()
        if not remote_wg:
            return True, "SSH 未配置，跳过远程同步"

        config = self.get_server_config()
        success, msg = remote_wg.update_config(config)
        if not success:
            return False, f"更新远程配置失败: {msg}"

        # 重载配置
        success, msg = remote_wg.reload()
        return success, msg

    def sync_to_remote(self) -> tuple[bool, str]:
        """手动同步到远程服务器"""
        return self._sync_to_remote()

    def get_remote_status(self) -> tuple[bool, str]:
        """获取远程 WireGuard 状态"""
        remote_wg = self.get_remote_wg()
        if not remote_wg:
            return False, "SSH 未配置"
        return remote_wg.get_status()

    # ========== 其他功能 ==========

    def list_peers(self) -> list[Peer]:
        """列出所有客户端"""
        return self.peers

    def get_status(self) -> dict:
        """获取本地 WireGuard 状态"""
        from .crypto import run_wg_command
        success, output = run_wg_command(["wg", "show"])
        return {"running": success, "output": output if success else "WireGuard 未运行或无权限"}
