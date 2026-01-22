"""添加 WireGuard 客户端节点模块"""

import sys
from typing import Optional

from .config import REMOTE_WG_DIR
from .crypto import generate_keypair, generate_preshared_key
from .parser import parse_config, scan_interfaces, get_network, allocate_ip
from .ssh import connect_ssh


def add_peer(
    host: str,
    name: str,
    allowed_ips: str = "",
    interface: Optional[str] = None,
    ssh_port: int = 22,
    key_file: Optional[str] = None,
    dns: str = ""
) -> bool:
    """添加客户端节点

    Args:
        host: 服务器地址 (user@host 格式)
        name: 客户端名称
        allowed_ips: 客户端 AllowedIPs（留空使用服务端网段）
        interface: 指定接口名称（留空则自动检测/询问）
        ssh_port: SSH 端口，默认 22
        key_file: SSH 私钥文件路径
        dns: DNS 服务器（留空则不设置）

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
        print(f"请先使用 'wg-manager deploy {host}' 部署服务", file=sys.stderr)
        return False

    # 选择接口
    if interface:
        # 指定了接口，验证是否存在
        matching = [(iface, net) for iface, net in interfaces if iface == interface]
        if not matching:
            print(f"错误: 接口 {interface} 不存在", file=sys.stderr)
            print(f"可用接口: {', '.join(i[0] for i in interfaces)}", file=sys.stderr)
            return False
        selected_interface, network = matching[0]
    elif len(interfaces) == 1:
        selected_interface, network = interfaces[0]
        print(f"使用接口: {selected_interface} ({network})")
    else:
        # 多个接口，询问用户
        print("\n发现多个 WireGuard 接口:")
        for i, (iface, net) in enumerate(interfaces, 1):
            print(f"  {i}. {iface} ({net})")
        try:
            choice = input(f"请选择 [1-{len(interfaces)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(interfaces):
                selected_interface, network = interfaces[idx]
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

    # 解析配置
    server_config, used_ips = parse_config(config_content)

    if not server_config["private_key"]:
        print("错误: 配置文件中未找到 PrivateKey", file=sys.stderr)
        return False

    # 分配新 IP
    try:
        new_ip = allocate_ip(server_config["address"], used_ips)
    except RuntimeError as e:
        print(f"错误: {e}", file=sys.stderr)
        return False

    print(f"分配 IP: {new_ip}")

    # 生成客户端密钥
    print("生成客户端密钥...")
    private_key, public_key = generate_keypair()
    psk = generate_preshared_key()

    # 如果未指定 allowed_ips，使用服务端网段
    if not allowed_ips:
        allowed_ips = get_network(server_config["address"])

    # 构建新的 Peer 配置段
    new_peer_section = f"""
[Peer]
# {name}
PublicKey = {public_key}
PresharedKey = {psk}
AllowedIPs = {new_ip.split('/')[0]}/32
"""

    # 更新服务端配置
    updated_config = config_content.rstrip() + "\n" + new_peer_section
    print("更新服务端配置...")
    success, msg = ssh.write_remote_file(config_path, updated_config)
    if not success:
        print(f"写入配置失败: {msg}", file=sys.stderr)
        return False

    # 热重载（不断线）
    print("热重载配置...")
    # 使用临时文件避免进程替换问题
    reload_cmd = (
        f"wg-quick strip {selected_interface} > /tmp/{selected_interface}_strip.conf && "
        f"wg syncconf {selected_interface} /tmp/{selected_interface}_strip.conf && "
        f"rm -f /tmp/{selected_interface}_strip.conf"
    )
    success, msg = ssh.run_command(reload_cmd)
    if not success:
        print(f"警告: 热重载失败，尝试重启服务...", file=sys.stderr)
        success, msg = ssh.run_command(f"systemctl restart wg-quick@{selected_interface}")
        if not success:
            print(f"重启服务失败: {msg}", file=sys.stderr)
            return False

    # 客户端地址使用 /24 网段
    client_address = new_ip.replace('/32', '/24')

    # 生成客户端配置
    dns_line = f"DNS = {dns}\n" if dns else ""
    client_config = f"""[Interface]
Address = {client_address}
PrivateKey = {private_key}
{dns_line}
[Peer]
PublicKey = {server_config['public_key']}
PresharedKey = {psk}
AllowedIPs = {allowed_ips}
Endpoint = {server}:{server_config['port']}
PersistentKeepalive = 25
"""

    # 输出结果
    print()
    print(f"客户端 '{name}' 添加成功!")
    print(f"  IP: {new_ip}")
    print()
    print("--- 客户端配置（请保存，不会再次显示）---")
    print(client_config)

    return True
