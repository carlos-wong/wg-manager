"""WireGuard 服务部署模块"""

import sys
from typing import Optional

from .config import DEFAULT_ADDRESS, DEFAULT_PORT, DEFAULT_INTERFACE, REMOTE_WG_DIR
from .crypto import generate_keypair
from .parser import parse_host
from .ssh import SSHClient, SSHConfig


def deploy_server(
    host: str,
    address: str = DEFAULT_ADDRESS,
    port: int = DEFAULT_PORT,
    interface: str = DEFAULT_INTERFACE,
    ssh_port: int = 22,
    key_file: Optional[str] = None
) -> bool:
    """在服务器上部署新的 WireGuard 接口

    Args:
        host: 服务器地址 (user@host 格式)
        address: 服务端内网地址，默认 10.0.0.1/24
        port: 监听端口，默认 51820
        interface: 接口名称，默认 wg0
        ssh_port: SSH 端口，默认 22
        key_file: SSH 私钥文件路径

    Returns:
        是否成功
    """
    user, server = parse_host(host)

    # 创建 SSH 客户端
    ssh_config = SSHConfig(host=server, port=ssh_port, user=user, key_file=key_file)
    ssh = SSHClient(ssh_config)

    # 测试连接
    print(f"连接到 {user}@{server}...")
    success, msg = ssh.test_connection()
    if not success:
        print(f"SSH 连接失败: {msg}", file=sys.stderr)
        return False
    print("SSH 连接成功")

    # 检查配置文件是否已存在
    config_path = f"{REMOTE_WG_DIR}/{interface}.conf"
    success, _ = ssh.run_command(f"test -f {config_path} && echo exists")
    if success:
        print(f"错误: 配置文件 {config_path} 已存在", file=sys.stderr)
        print(f"如需重新部署，请先删除: rm {config_path}", file=sys.stderr)
        return False

    # 生成密钥对
    print("生成密钥对...")
    private_key, public_key = generate_keypair()

    # 检测默认网卡
    print("检测默认网卡...")
    success, output = ssh.run_command("ip route show default | awk '{print $5}' | head -1")
    if success and output.strip():
        default_iface = output.strip()
    else:
        default_iface = "eth0"
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
    print(f"写入配置文件 {config_path}...")
    success, msg = ssh.write_remote_file(config_path, config)
    if not success:
        print(f"写入配置失败: {msg}", file=sys.stderr)
        return False

    # 设置权限
    ssh.run_command(f"chmod 600 {config_path}")

    # 启动服务
    print(f"启动 WireGuard 服务...")
    success, msg = ssh.run_command(f"systemctl enable wg-quick@{interface}")
    if not success:
        print(f"警告: 启用服务失败: {msg}", file=sys.stderr)

    success, msg = ssh.run_command(f"systemctl start wg-quick@{interface}")
    if not success:
        print(f"启动服务失败: {msg}", file=sys.stderr)
        return False

    # 验证服务状态
    success, _ = ssh.run_command(f"systemctl is-active wg-quick@{interface}")
    if not success:
        print("警告: 服务可能未正常启动", file=sys.stderr)

    # 输出结果
    print()
    print(f"WireGuard {interface} 部署成功!")
    print(f"  服务器: {server}")
    print(f"  地址: {address}")
    print(f"  端口: {port}")
    print(f"  公钥: {public_key}")

    return True
