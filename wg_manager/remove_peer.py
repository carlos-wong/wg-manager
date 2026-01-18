"""删除 WireGuard 客户端节点模块"""

import re
import sys
from typing import Optional

from .config import REMOTE_WG_DIR
from .parser import scan_interfaces, parse_peers
from .ssh import connect_ssh


def remove_peer(
    host: str,
    name: str,
    interface: Optional[str] = None,
    ssh_port: int = 22,
    key_file: Optional[str] = None
) -> bool:
    """删除客户端节点

    Args:
        host: 服务器地址 (user@host 格式)
        name: 客户端名称
        interface: 指定接口名称（留空则自动检测/询问）
        ssh_port: SSH 端口，默认 22
        key_file: SSH 私钥文件路径

    Returns:
        是否成功
    """
    ssh, server = connect_ssh(host, ssh_port, key_file)
    if ssh is None:
        return False

    # 扫描配置文件
    print("扫描 WireGuard 配置...")
    interfaces = scan_interfaces(ssh)

    if not interfaces:
        print("错误: 服务器上没有 WireGuard 配置文件", file=sys.stderr)
        return False

    # 选择接口
    if interface:
        # 指定了接口，验证是否存在
        matching = [(iface, net) for iface, net in interfaces if iface == interface]
        if not matching:
            print(f"错误: 接口 {interface} 不存在", file=sys.stderr)
            return False
        selected_interface = interface
    elif len(interfaces) == 1:
        selected_interface = interfaces[0][0]
        print(f"使用接口: {selected_interface}")
    else:
        # 多个接口，询问用户
        print("\n发现多个 WireGuard 接口:")
        for i, (iface, net) in enumerate(interfaces, 1):
            print(f"  {i}. {iface} ({net})")
        try:
            choice = input(f"请选择 [1-{len(interfaces)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(interfaces):
                selected_interface = interfaces[idx][0]
            else:
                print("无效选择", file=sys.stderr)
                return False
        except (ValueError, KeyboardInterrupt):
            print("\n已取消", file=sys.stderr)
            return False

    # 读取配置文件
    config_path = f"{REMOTE_WG_DIR}/{selected_interface}.conf"
    success, config_content = ssh.read_remote_file(config_path)
    if not success:
        print(f"读取配置失败: {config_content}", file=sys.stderr)
        return False

    # 解析 peers
    peers = parse_peers(config_content)
    if not peers:
        print("错误: 配置文件中没有客户端", file=sys.stderr)
        return False

    # 查找要删除的 peer
    target_peer = None
    for peer in peers:
        if peer["name"] == name:
            target_peer = peer
            break

    if not target_peer:
        print(f"错误: 客户端 '{name}' 不存在", file=sys.stderr)
        print("现有客户端:")
        for peer in peers:
            print(f"  - {peer['name']}: {peer['allowed_ips']}")
        return False

    # 从配置中删除 peer 段
    # 匹配 [Peer] 段，包含指定名称的注释
    pattern = rf'\n?\[Peer\]\s*\n#\s*{re.escape(name)}\s*\n.*?(?=\n\[Peer\]|\Z)'
    new_config = re.sub(pattern, '', config_content, flags=re.DOTALL)

    # 如果上面的模式没匹配到（可能名称不在注释中），尝试按 PublicKey 删除
    if new_config == config_content:
        pubkey = target_peer["public_key"]
        pattern = rf'\n?\[Peer\].*?PublicKey\s*=\s*{re.escape(pubkey)}.*?(?=\n\[Peer\]|\Z)'
        new_config = re.sub(pattern, '', config_content, flags=re.DOTALL)

    if new_config == config_content:
        print(f"错误: 无法从配置中删除客户端 '{name}'", file=sys.stderr)
        return False

    # 写入更新后的配置
    print(f"更新配置文件...")
    success, msg = ssh.write_remote_file(config_path, new_config.strip() + '\n')
    if not success:
        print(f"写入配置失败: {msg}", file=sys.stderr)
        return False

    # 从运行中的 WireGuard 移除 peer
    print("从运行中的服务移除客户端...")
    pubkey = target_peer["public_key"]
    success, msg = ssh.run_command(f"wg set {selected_interface} peer {pubkey} remove")
    if not success:
        # 如果动态移除失败，尝试重载配置
        print("动态移除失败，尝试重载配置...")
        reload_cmd = (
            f"wg-quick strip {selected_interface} > /tmp/{selected_interface}_strip.conf && "
            f"wg syncconf {selected_interface} /tmp/{selected_interface}_strip.conf && "
            f"rm -f /tmp/{selected_interface}_strip.conf"
        )
        success, msg = ssh.run_command(reload_cmd)
        if not success:
            print(f"警告: 重载配置失败，可能需要重启服务: {msg}", file=sys.stderr)

    print()
    print(f"客户端 '{name}' 已删除!")
    print(f"  IP: {target_peer['allowed_ips']}")

    return True


def list_peers(
    host: str,
    interface: Optional[str] = None,
    ssh_port: int = 22,
    key_file: Optional[str] = None
) -> bool:
    """列出所有客户端节点

    Args:
        host: 服务器地址 (user@host 格式)
        interface: 指定接口名称（留空则显示所有）
        ssh_port: SSH 端口，默认 22
        key_file: SSH 私钥文件路径

    Returns:
        是否成功
    """
    ssh, _ = connect_ssh(host, ssh_port, key_file)
    if ssh is None:
        return False

    # 扫描配置文件
    interfaces = scan_interfaces(ssh)

    if not interfaces:
        print("服务器上没有 WireGuard 配置文件")
        return True

    # 过滤接口
    if interface:
        interfaces = [(i, n) for i, n in interfaces if i == interface]
        if not interfaces:
            print(f"错误: 接口 {interface} 不存在", file=sys.stderr)
            return False

    # 列出每个接口的客户端
    for iface, network in interfaces:
        config_path = f"{REMOTE_WG_DIR}/{iface}.conf"
        success, config_content = ssh.read_remote_file(config_path)
        if not success:
            continue

        peers = parse_peers(config_content)
        print(f"\n{iface} ({network}):")
        if not peers:
            print("  (无客户端)")
        else:
            for peer in peers:
                print(f"  - {peer['name']}: {peer['allowed_ips']}")

    return True
