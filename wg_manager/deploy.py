"""WireGuard 服务部署模块"""

import sys
from typing import Optional

from .config import DEFAULT_ADDRESS, DEFAULT_PORT, DEFAULT_INTERFACE, REMOTE_WG_DIR
from .crypto import generate_keypair
from .parser import scan_interfaces
from .ssh import SSHClient, connect_ssh


def get_input(prompt: str, default: str = "") -> str:
    """获取用户输入"""
    try:
        if default:
            value = input(f"{prompt} [{default}]: ").strip()
            return value if value else default
        return input(f"{prompt}: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n已取消")
        sys.exit(0)


def check_port_in_use(ssh: SSHClient, port: int) -> bool:
    """检查端口是否被占用"""
    success, output = ssh.run_command(f"ss -tuln | grep -q ':{port} ' && echo used")
    return success and "used" in output


def check_network_conflict(ssh: SSHClient, address: str) -> Optional[str]:
    """检查网段是否与现有接口冲突，返回冲突的接口名"""
    interfaces = scan_interfaces(ssh)
    new_network = address.split('/')[0].rsplit('.', 1)[0]  # 10.0.0.1 -> 10.0.0

    for iface, net in interfaces:
        existing_network = net.split('/')[0].rsplit('.', 1)[0]
        if new_network == existing_network:
            return iface
    return None


def deploy_server(
    host: str,
    address: Optional[str] = None,
    port: Optional[int] = None,
    interface: Optional[str] = None,
    ssh_port: int = 22,
    key_file: Optional[str] = None,
    interactive: bool = True
) -> bool:
    """在服务器上部署新的 WireGuard 接口

    Args:
        host: 服务器地址 (user@host 格式)
        address: 服务端内网地址，默认询问用户
        port: 监听端口，默认询问用户
        interface: 接口名称，默认询问用户
        ssh_port: SSH 端口，默认 22
        key_file: SSH 私钥文件路径
        interactive: 是否交互式询问

    Returns:
        是否成功
    """
    ssh, server = connect_ssh(host, ssh_port, key_file)
    if ssh is None:
        return False

    # 扫描现有配置
    existing = scan_interfaces(ssh)
    if existing:
        print(f"\n已存在的 WireGuard 接口:")
        for iface, net in existing:
            print(f"  - {iface}: {net}")
        print()

    # 交互式获取配置
    if interactive:
        # 接口名称
        if interface is None:
            suggested_interface = DEFAULT_INTERFACE
            # 自动建议下一个可用接口
            existing_names = [i[0] for i in existing]
            for i in range(10):
                name = f"wg{i}"
                if name not in existing_names:
                    suggested_interface = name
                    break
            interface = get_input("接口名称", suggested_interface)

        # 检查配置文件是否已存在
        config_path = f"{REMOTE_WG_DIR}/{interface}.conf"
        success, _ = ssh.run_command(f"test -f {config_path} && echo exists")
        if success:
            print(f"错误: 配置文件 {config_path} 已存在", file=sys.stderr)
            return False

        # 网段
        if address is None:
            suggested_address = DEFAULT_ADDRESS
            # 自动建议下一个可用网段
            existing_networks = set()
            for _, net in existing:
                parts = net.split('/')[0].split('.')
                if len(parts) >= 3:
                    existing_networks.add(int(parts[2]))
            for i in range(256):
                if i not in existing_networks:
                    suggested_address = f"10.0.{i}.1/24"
                    break
            address = get_input("服务端内网地址", suggested_address)

        # 检查网段冲突
        conflict = check_network_conflict(ssh, address)
        if conflict:
            print(f"错误: 网段与接口 {conflict} 冲突", file=sys.stderr)
            return False

        # 端口
        if port is None:
            suggested_port = DEFAULT_PORT
            # 检查端口占用，自动建议下一个可用端口
            while check_port_in_use(ssh, suggested_port):
                suggested_port += 1
                if suggested_port > 65535:
                    suggested_port = 51820
                    break
            port = int(get_input("监听端口", str(suggested_port)))

        # 检查端口是否被占用
        if check_port_in_use(ssh, port):
            print(f"错误: 端口 {port} 已被占用", file=sys.stderr)
            return False
    else:
        # 非交互模式，使用默认值
        interface = interface or DEFAULT_INTERFACE
        address = address or DEFAULT_ADDRESS
        port = port or DEFAULT_PORT

        # 检查配置文件是否已存在
        config_path = f"{REMOTE_WG_DIR}/{interface}.conf"
        success, _ = ssh.run_command(f"test -f {config_path} && echo exists")
        if success:
            print(f"错误: 配置文件 {config_path} 已存在", file=sys.stderr)
            return False

        # 检查网段冲突
        conflict = check_network_conflict(ssh, address)
        if conflict:
            print(f"错误: 网段与接口 {conflict} 冲突", file=sys.stderr)
            return False

        # 检查端口是否被占用
        if check_port_in_use(ssh, port):
            print(f"错误: 端口 {port} 已被占用", file=sys.stderr)
            return False

    # 生成密钥对
    print("生成密钥对...")
    private_key, public_key = generate_keypair()

    # 检测默认网卡
    print("检测默认网卡...")
    success, output = ssh.run_command("ip route show default | awk '{print $5}' | head -1")
    default_iface = output.strip() if success and output.strip() else "eth0"
    print(f"默认网卡: {default_iface}")

    # 构建配置
    config = f"""[Interface]
PrivateKey = {private_key}
Address = {address}
ListenPort = {port}
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o {default_iface} -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o {default_iface} -j MASQUERADE
"""

    # 确保目录存在
    ssh.run_command(f"mkdir -p {REMOTE_WG_DIR}")

    # 写入配置文件
    config_path = f"{REMOTE_WG_DIR}/{interface}.conf"
    print(f"写入配置文件 {config_path}...")
    success, msg = ssh.write_remote_file(config_path, config)
    if not success:
        print(f"写入配置失败: {msg}", file=sys.stderr)
        return False

    # 设置权限
    ssh.run_command(f"chmod 600 {config_path}")

    # 启动服务
    print("启动 WireGuard 服务...")
    ssh.run_command(f"systemctl enable wg-quick@{interface}")
    success, msg = ssh.run_command(f"systemctl start wg-quick@{interface}")
    if not success:
        print(f"启动服务失败: {msg}", file=sys.stderr)
        return False

    # 输出结果
    print()
    print(f"WireGuard {interface} 部署成功!")
    print(f"  服务器: {server}")
    print(f"  地址: {address}")
    print(f"  端口: {port}")
    print(f"  公钥: {public_key}")

    return True
