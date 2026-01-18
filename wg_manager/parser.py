"""WireGuard 配置文件解析器"""

import re
from typing import Optional

from .ssh import SSHClient


def parse_host(host_string: str) -> tuple[str, str]:
    """解析 user@host 格式的字符串

    Args:
        host_string: 格式为 user@host 或 host

    Returns:
        (user, host) 元组
    """
    if "@" in host_string:
        user, host = host_string.split("@", 1)
        return user, host
    return "root", host_string


def parse_config(content: str) -> tuple[dict, set[int]]:
    """解析 WireGuard 配置文件，返回服务端配置和已用 IP 列表

    Args:
        content: 配置文件内容

    Returns:
        (server_config, used_ips) 元组
        server_config: 包含 private_key, public_key, address, port, post_up, post_down
        used_ips: 已使用的 IP 最后一位集合
    """
    from .crypto import generate_public_key

    server_config = {
        "private_key": "",
        "public_key": "",
        "address": "",
        "port": 51820,
        "post_up": "",
        "post_down": "",
    }
    used_ips = set()

    # 解析 Interface 部分
    interface_match = re.search(r'\[Interface\](.*?)(?=\[Peer\]|$)', content, re.DOTALL | re.IGNORECASE)
    if interface_match:
        section = interface_match.group(1)

        # PrivateKey
        pk_match = re.search(r'PrivateKey\s*=\s*(\S+)', section)
        if pk_match:
            server_config["private_key"] = pk_match.group(1)
            server_config["public_key"] = generate_public_key(pk_match.group(1))

        # Address
        addr_match = re.search(r'Address\s*=\s*(\S+)', section)
        if addr_match:
            server_config["address"] = addr_match.group(1)
            # 服务端 IP 也算已用
            ip_part = addr_match.group(1).split('/')[0]
            last_octet = int(ip_part.split('.')[-1])
            used_ips.add(last_octet)

        # ListenPort
        port_match = re.search(r'ListenPort\s*=\s*(\d+)', section)
        if port_match:
            server_config["port"] = int(port_match.group(1))

        # PostUp
        postup_match = re.search(r'PostUp\s*=\s*(.+)$', section, re.MULTILINE)
        if postup_match:
            server_config["post_up"] = postup_match.group(1).strip()

        # PostDown
        postdown_match = re.search(r'PostDown\s*=\s*(.+)$', section, re.MULTILINE)
        if postdown_match:
            server_config["post_down"] = postdown_match.group(1).strip()

    # 解析 Peer 部分，提取已用 IP
    for peer_match in re.finditer(r'\[Peer\](.*?)(?=\[Peer\]|$)', content, re.DOTALL | re.IGNORECASE):
        section = peer_match.group(1)
        allowed_match = re.search(r'AllowedIPs\s*=\s*(\S+)', section)
        if allowed_match:
            ip = allowed_match.group(1).split('/')[0]
            # 只处理 IPv4 地址
            if '.' in ip:
                try:
                    last_octet = int(ip.split('.')[-1])
                    used_ips.add(last_octet)
                except ValueError:
                    pass

    return server_config, used_ips


def parse_peers(content: str) -> list[dict]:
    """解析配置文件中的 Peer 信息

    Args:
        content: 配置文件内容

    Returns:
        Peer 信息列表，每个包含 name, public_key, preshared_key, allowed_ips
    """
    peers = []

    for i, peer_match in enumerate(re.finditer(r'\[Peer\](.*?)(?=\[Peer\]|$)', content, re.DOTALL | re.IGNORECASE)):
        section = peer_match.group(1)

        pub_match = re.search(r'PublicKey\s*=\s*(\S+)', section)
        allowed_match = re.search(r'AllowedIPs\s*=\s*(\S+)', section)
        psk_match = re.search(r'PresharedKey\s*=\s*(\S+)', section)
        # 注释行作为名称
        comment_match = re.search(r'#\s*(.+)$', section, re.MULTILINE)

        if pub_match:
            name = comment_match.group(1).strip() if comment_match else f"peer_{i+1}"
            peers.append({
                "name": name,
                "public_key": pub_match.group(1),
                "preshared_key": psk_match.group(1) if psk_match else "",
                "allowed_ips": allowed_match.group(1) if allowed_match else ""
            })

    return peers


def scan_interfaces(ssh: SSHClient, wg_dir: str = "/etc/wireguard") -> list[tuple[str, str]]:
    """扫描服务器上的 WireGuard 配置文件

    Args:
        ssh: SSH 客户端
        wg_dir: WireGuard 配置目录

    Returns:
        [(接口名, 网段), ...] 列表
    """
    success, output = ssh.run_command(f"ls -1 {wg_dir}/*.conf 2>/dev/null")
    if not success or not output.strip():
        return []

    interfaces = []
    for f in output.strip().split('\n'):
        if f and f.endswith('.conf'):
            # /etc/wireguard/wg0.conf -> wg0
            interface = f.split('/')[-1].replace('.conf', '')

            # 读取配置获取网段
            success, config = ssh.read_remote_file(f)
            if success:
                addr_match = re.search(r'Address\s*=\s*(\S+)', config)
                network = addr_match.group(1) if addr_match else "unknown"
                interfaces.append((interface, network))

    return interfaces


def get_network(address: str) -> str:
    """从地址获取网段

    Args:
        address: 如 10.0.0.1/24

    Returns:
        网段，如 10.0.0.0/24
    """
    ip = address.split('/')[0]
    parts = ip.split('.')
    return f"{'.'.join(parts[:3])}.0/24"


def allocate_ip(server_address: str, used_ips: set[int]) -> str:
    """分配新的 IP 地址

    Args:
        server_address: 服务端地址，如 10.0.0.1/24
        used_ips: 已使用的 IP 最后一位集合

    Returns:
        新的 IP 地址，如 10.0.0.2/32
    """
    base = server_address.split('/')[0]
    parts = base.split('.')
    base_prefix = '.'.join(parts[:3])

    for i in range(2, 255):
        if i not in used_ips:
            return f"{base_prefix}.{i}/32"

    raise RuntimeError("IP 地址池已满")
