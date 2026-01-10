"""命令行接口"""

import argparse
import sys

from .manager import WireGuardManager


class CancelInput(Exception):
    """用户取消输入"""
    pass


def get_input_required(prompt: str) -> str:
    """获取必填输入，Ctrl+C 取消"""
    try:
        value = input(f"{prompt}: ").strip()
        if not value:
            print("错误: 输入不能为空")
            raise CancelInput()
        return value
    except KeyboardInterrupt:
        print()
        raise CancelInput()


def get_input_optional(prompt: str, default: str = "") -> str:
    """获取可选输入，Ctrl+C 取消"""
    try:
        if default:
            value = input(f"{prompt} [{default}]: ").strip()
            return value if value else default
        else:
            return input(f"{prompt}: ").strip()
    except KeyboardInterrupt:
        print()
        raise CancelInput()


def interactive_menu(manager: WireGuardManager):
    """交互式菜单"""
    while True:
        # 清屏效果
        print("\n" * 2)

        # 标题
        print("┌" + "─" * 48 + "┐")
        print("│" + " " * 14 + "WireGuard 管理工具" + " " * 16 + "│")
        print("└" + "─" * 48 + "┘")

        # 状态栏
        servers = manager.get_servers()
        if servers:
            server_info = f"当前: {manager.server.endpoint}:{manager.server.interface}"
            peer_info = f"{len(manager.peers)} 个客户端"
            if len(servers) > 1:
                peer_info += f" | 共 {len(servers)} 个服务端"
        else:
            server_info = "未配置服务端"
            peer_info = ""

        ssh_icon = "●" if manager.get_ssh_client() else "○"
        ssh_status = "SSH 已连接" if manager.get_ssh_client() else "SSH 未配置"

        print(f"\n  {server_info}")
        if peer_info:
            print(f"  {peer_info}")
        print(f"  {ssh_icon} {ssh_status}")

        # 菜单
        print("\n┌─ 服务端 " + "─" * 39 + "┐")
        print("│  1. 初始化新服务端      2. 从文件导入          │")
        print("│  3. 手动输入私钥导入    4. 查看配置            │")
        print("│  5. 切换服务端          6. 删除服务端          │")
        print("├─ 客户端 " + "─" * 39 + "┤")
        print("│  7. 添加客户端          8. 删除客户端          │")
        print("│  9. 启用/禁用          10. 列出所有            │")
        print("│ 11. 导出配置           12. 显示二维码          │")
        print("├─ 远程管理 " + "─" * 37 + "┤")
        print("│ 13. 配置 SSH           14. 从远程导入          │")
        print("│ 15. 同步到远程         16. 查看远程状态        │")
        print("├─ 其他 " + "─" * 41 + "┤")
        print("│ 17. 导出服务端配置      0. 退出                │")
        print("└" + "─" * 48 + "┘")
        try:
            choice = input("请选择 [0-17]: ").strip()
        except KeyboardInterrupt:
            print("\n再见!")
            break

        try:
            if choice == "0":
                print("再见!")
                break

            elif choice == "1":
                _menu_init_server(manager)

            elif choice == "2":
                _menu_import_from_file(manager)

            elif choice == "3":
                _menu_import_manual(manager)

            elif choice == "4":
                _menu_show_server(manager)

            elif choice == "5":
                _menu_switch_server(manager)

            elif choice == "6":
                _menu_delete_server(manager)

            elif choice == "7":
                _menu_add_peer(manager)

            elif choice == "8":
                _menu_remove_peer(manager)

            elif choice == "9":
                _menu_toggle_peer(manager)

            elif choice == "10":
                _menu_list_peers(manager)

            elif choice == "11":
                _menu_export_peer(manager)

            elif choice == "12":
                _menu_show_qrcode(manager)

            elif choice == "13":
                _menu_setup_ssh(manager)

            elif choice == "14":
                _menu_import_from_remote(manager)

            elif choice == "15":
                _menu_sync_remote(manager)

            elif choice == "16":
                _menu_remote_status(manager)

            elif choice == "17":
                _menu_export_server(manager)

            else:
                print("无效选择")

        except CancelInput:
            print("\n已取消")
        except Exception as e:
            print(f"错误: {e}")


def _menu_init_server(manager: WireGuardManager):
    print("\n--- 初始化新服务端 --- (Ctrl+C 返回菜单)")
    endpoint = get_input_required("公网 IP 或域名")
    address = get_input_optional("服务端内网地址", "10.0.0.1/24")
    port = get_input_optional("监听端口", "51820")
    interface = get_input_optional("接口名称", "wg0")

    server = manager.init_server(endpoint, address, int(port), interface)
    print(f"\n✓ 服务端初始化成功!")
    print(f"  公钥: {server.public_key}")


def _menu_import_from_file(manager: WireGuardManager):
    print("\n--- 从配置文件导入服务端 --- (Ctrl+C 返回菜单)")
    config_path = get_input_required("配置文件路径 (如 /etc/wireguard/wg0.conf)")
    endpoint = get_input_required("公网 IP 或域名")

    server, existing_peers = manager.import_server_from_config(config_path, endpoint)
    print(f"\n✓ 服务端导入成功!")
    print(f"  公钥: {server.public_key}")
    print(f"  地址: {server.address}")
    print(f"  端口: {server.listen_port}")

    _handle_existing_peers(manager, existing_peers)


def _menu_import_manual(manager: WireGuardManager):
    print("\n--- 手动导入服务端 --- (Ctrl+C 返回菜单)")
    private_key = get_input_required("服务端私钥")
    endpoint = get_input_required("公网 IP 或域名")
    address = get_input_optional("服务端内网地址", "10.0.0.1/24")
    port = get_input_optional("监听端口", "51820")
    interface = get_input_optional("接口名称", "wg0")

    server = manager.import_server(private_key, endpoint, address, int(port), interface)
    print(f"\n✓ 服务端导入成功!")
    print(f"  公钥: {server.public_key}")


def _menu_show_server(manager: WireGuardManager):
    if not manager.server.private_key:
        print("错误: 服务端未初始化")
        return
    print("\n--- 服务端配置 ---")
    print(f"公钥: {manager.server.public_key}")
    print(f"地址: {manager.server.address}")
    print(f"端口: {manager.server.listen_port}")
    print(f"Endpoint: {manager.server.endpoint}")
    print(f"接口: {manager.server.interface}")
    print(f"客户端数: {len(manager.peers)}")


def _menu_switch_server(manager: WireGuardManager):
    servers = manager.get_servers()
    if not servers:
        print("没有可用的服务端")
        return
    if len(servers) == 1:
        print("只有一个服务端，无需切换")
        return

    print("\n--- 切换服务端 --- (Ctrl+C 返回菜单)")
    for i, s in enumerate(servers, 1):
        current = " (当前)" if s.id == manager.server_id else ""
        peer_count = len(manager.db.get_peers(s.id))
        print(f"  {i}. {s.endpoint}:{s.interface} - {s.address} Port:{s.listen_port} ({peer_count} 客户端){current}")

    choice = get_input_required("选择服务端序号")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(servers):
            if manager.switch_server(servers[idx].id):
                print(f"✓ 已切换到服务端: {manager.server.endpoint}")
            else:
                print("切换失败")
        else:
            print("无效选择")
    except ValueError:
        print("请输入数字")


def _menu_delete_server(manager: WireGuardManager):
    servers = manager.get_servers()
    if not servers:
        print("没有可用的服务端")
        return

    print("\n--- 删除服务端 --- (Ctrl+C 返回菜单)")
    for i, s in enumerate(servers, 1):
        current = " (当前)" if s.id == manager.server_id else ""
        peer_count = len(manager.db.get_peers(s.id))
        print(f"  {i}. {s.endpoint}:{s.interface} - {s.address} Port:{s.listen_port} ({peer_count} 客户端){current}")

    choice = get_input_required("选择要删除的服务端序号")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(servers):
            server = servers[idx]
            confirm = get_input_optional(f"确定删除 '{server.endpoint}:{server.interface}' 及其所有客户端? (y/n)", "n")
            if confirm.lower() == 'y':
                if manager.delete_server(server.id):
                    print(f"✓ 已删除服务端: {server.endpoint}")
                else:
                    print("删除失败")
        else:
            print("无效选择")
    except ValueError:
        print("请输入数字")


def _menu_add_peer(manager: WireGuardManager):
    if not manager.server.private_key:
        print("错误: 请先初始化服务端")
        return
    print("\n--- 添加客户端 --- (Ctrl+C 返回菜单)")
    name = get_input_required("客户端名称")
    dns = get_input_optional("DNS 服务器 (留空不设置)")
    mtu = get_input_optional("MTU", "1280")

    peer = manager.add_peer(name, dns, int(mtu))
    print(f"\n✓ 客户端 '{name}' 添加成功!")
    print(f"  分配 IP: {peer.address}")
    print(f"  监听端口: {peer.listen_port}")

    # 自动显示客户端配置
    print("\n--- 客户端配置 ---")
    print(manager.get_client_config(name))


def _menu_remove_peer(manager: WireGuardManager):
    if not manager.peers:
        print("没有客户端")
        return
    print("\n--- 删除客户端 --- (Ctrl+C 返回菜单)")
    for i, p in enumerate(manager.peers, 1):
        print(f"  {i}. {p.name} ({p.address})")
    name = get_input_required("输入客户端名称")
    if manager.remove_peer(name):
        print(f"✓ 客户端 '{name}' 已删除")
    else:
        print(f"错误: 客户端 '{name}' 不存在")


def _menu_toggle_peer(manager: WireGuardManager):
    if not manager.peers:
        print("没有客户端")
        return
    print("\n--- 启用/禁用客户端 --- (Ctrl+C 返回菜单)")
    for p in manager.peers:
        status = "✓ 启用" if p.enabled else "✗ 禁用"
        print(f"  {p.name}: {status}")
    name = get_input_required("输入客户端名称")
    result = manager.toggle_peer(name)
    if result is not None:
        status = "启用" if result else "禁用"
        print(f"✓ 客户端 '{name}' 已{status}")
    else:
        print(f"错误: 客户端 '{name}' 不存在")


def _menu_list_peers(manager: WireGuardManager):
    print(f"\n--- 客户端列表 [{manager.server.endpoint}] ---")
    if not manager.peers:
        print("  (空)")
    else:
        for p in manager.peers:
            status = "✓" if p.enabled else "✗"
            imported = " [导入]" if not p.private_key else ""
            print(f"  {status} {p.name}{imported}")
            print(f"      IP: {p.address}")
            print(f"      监听端口: {p.listen_port}  MTU: {p.mtu}")
            print(f"      公钥: {p.public_key[:20]}...")
            print(f"      创建: {p.created_at[:10]}")


def _menu_export_peer(manager: WireGuardManager):
    if not manager.peers:
        print("没有客户端")
        return
    exportable = [p for p in manager.peers if p.private_key]
    if not exportable:
        print("没有可导出的客户端 (导入的客户端没有私钥)")
        return
    print("\n--- 导出客户端配置 --- (Ctrl+C 返回菜单)")
    for p in exportable:
        print(f"  - {p.name}")
    name = get_input_required("输入客户端名称")

    peer = manager.db.get_peer_by_name(name, manager.server_id)
    if not peer:
        print(f"错误: 客户端 '{name}' 不存在")
        return
    if not peer.private_key:
        print(f"错误: '{name}' 是导入的客户端，没有私钥，无法导出配置")
        return

    # 显示配置内容
    print("\n--- 配置内容 ---")
    print(manager.get_client_config(name))

    # 询问是否保存到文件
    save = get_input_optional("保存到文件? (y/n)", "n")
    if save.lower() == 'y':
        path = manager.export_client_config(name)
        print(f"✓ 已保存到: {path}")


def _menu_show_qrcode(manager: WireGuardManager):
    if not manager.peers:
        print("没有客户端")
        return
    exportable = [p for p in manager.peers if p.private_key]
    if not exportable:
        print("没有可导出的客户端 (导入的客户端没有私钥)")
        return
    print("\n--- 显示客户端二维码 --- (Ctrl+C 返回菜单)")
    for p in exportable:
        print(f"  - {p.name}")
    name = get_input_required("输入客户端名称")
    peer = manager.db.get_peer_by_name(name, manager.server_id)
    if peer and not peer.private_key:
        print(f"错误: '{name}' 是导入的客户端，没有私钥，无法生成二维码")
        return
    print(f"\n{name} 的配置二维码:\n")
    manager.export_client_qrcode(name)


def _prompt_import_remote_configs(manager: WireGuardManager, host: str):
    """SSH 连接成功后，询问用户是否要导入远程配置"""
    ssh_client = manager.get_ssh_client()
    if not ssh_client:
        return

    # 扫描远程配置文件
    print("\n正在扫描远程服务器上的 WireGuard 配置...")
    success, interfaces = ssh_client.scan_wireguard_configs()

    if not success or not interfaces:
        print("  未发现 WireGuard 配置文件")
        return

    print(f"  发现 {len(interfaces)} 个配置: {', '.join(interfaces)}")

    # 检查哪些已经导入过
    existing_servers = manager.get_servers()
    existing_interfaces = set()
    for s in existing_servers:
        if s.endpoint == host:
            existing_interfaces.add(s.interface)

    new_interfaces = [i for i in interfaces if i not in existing_interfaces]

    if not new_interfaces:
        print("  所有配置已导入，无需重复导入")
        return

    if existing_interfaces:
        print(f"  已导入: {', '.join(existing_interfaces)}")
        print(f"  待导入: {', '.join(new_interfaces)}")

    # 询问用户
    try:
        choice = input(f"\n是否导入这些配置? (y/n) [y]: ").strip().lower()
        if choice == 'n':
            print("已跳过导入")
            return
    except KeyboardInterrupt:
        print("\n已跳过导入")
        return

    # 逐个导入
    for interface in new_interfaces:
        try:
            print(f"\n正在导入 {interface}...")
            # 临时设置接口以读取配置
            from .ssh import RemoteWireGuard
            remote_wg = RemoteWireGuard(ssh_client, interface)
            success, content = remote_wg.get_config()

            if not success:
                print(f"  ✗ 读取 {interface} 配置失败: {content}")
                continue

            # 导入配置
            server, existing_peers = manager._parse_and_import_config(content, host, interface)
            print(f"  ✓ {interface} 导入成功 ({server.address}, 端口 {server.listen_port})")

            # 处理已有客户端
            if existing_peers:
                print(f"    发现 {len(existing_peers)} 个已有客户端")
                try:
                    import_choice = input(f"    是否导入这些客户端? (y/n) [n]: ").strip().lower()
                    if import_choice == 'y':
                        for p in existing_peers:
                            try:
                                manager.import_existing_peer(
                                    name=p['name'],
                                    public_key=p['public_key'],
                                    address=p['allowed_ips'],
                                    preshared_key=p.get('preshared_key', '')
                                )
                                print(f"      ✓ 导入 {p['name']}")
                            except Exception as e:
                                print(f"      ✗ 导入 {p['name']} 失败: {e}")
                except KeyboardInterrupt:
                    print("\n    跳过客户端导入")

        except Exception as e:
            print(f"  ✗ 导入 {interface} 失败: {e}")

    print("\n导入完成!")


def _menu_setup_ssh(manager: WireGuardManager):
    print("\n--- 配置 SSH 连接 --- (Ctrl+C 返回菜单)")
    host = get_input_required("服务器地址")
    port = get_input_optional("SSH 端口", "22")
    user = get_input_optional("用户名", "root")

    print(f"\n正在测试连接 {user}@{host}:{port} ...")
    success, msg = manager.setup_ssh(host, int(port), user)
    if success:
        print(f"✓ SSH 连接成功!")
        # 询问是否导入远程配置
        _prompt_import_remote_configs(manager, host)
    else:
        print(f"✗ SSH 连接失败: {msg}")


def _menu_import_from_remote(manager: WireGuardManager):
    if not manager.get_ssh_client():
        print("错误: 请先配置 SSH 连接")
        return
    print("\n--- 从远程服务器导入配置 --- (Ctrl+C 返回菜单)")
    endpoint = get_input_required("公网 IP 或域名")

    server, existing_peers = manager.import_server_from_remote(endpoint)
    print(f"\n✓ 服务端导入成功!")
    print(f"  公钥: {server.public_key}")
    print(f"  地址: {server.address}")
    print(f"  端口: {server.listen_port}")

    _handle_existing_peers(manager, existing_peers)


def _menu_sync_remote(manager: WireGuardManager):
    if not manager.get_ssh_client():
        print("错误: 请先配置 SSH 连接")
        return
    print("\n正在同步配置到远程服务器...")
    success, msg = manager.sync_to_remote()
    if success:
        print(f"✓ {msg}")
    else:
        print(f"✗ {msg}")


def _menu_remote_status(manager: WireGuardManager):
    if not manager.get_ssh_client():
        print("错误: 请先配置 SSH 连接")
        return
    print("\n--- 远程 WireGuard 状态 ---")
    success, output = manager.get_remote_status()
    print(output)


def _menu_export_server(manager: WireGuardManager):
    path = manager.export_server_config()
    print(f"\n✓ 服务端配置已导出到: {path}")
    print("\n使用以下命令部署到服务器:")
    print(f"  sudo cp {path} /etc/wireguard/")
    print(f"  sudo systemctl enable wg-quick@{manager.server.interface}")
    print(f"  sudo systemctl start wg-quick@{manager.server.interface}")


def _handle_existing_peers(manager: WireGuardManager, existing_peers: list[dict]):
    """处理导入时发现的已有客户端"""
    if existing_peers:
        print(f"\n发现 {len(existing_peers)} 个已有客户端:")
        for p in existing_peers:
            print(f"  - {p['name']}: {p['allowed_ips']}")
        import_choice = input("\n是否导入这些客户端? (y/n) [n]: ").strip().lower()
        if import_choice == 'y':
            for p in existing_peers:
                try:
                    manager.import_existing_peer(
                        name=p['name'],
                        public_key=p['public_key'],
                        address=p['allowed_ips'],
                        preshared_key=p.get('preshared_key', '')
                    )
                    print(f"  ✓ 导入 {p['name']}")
                except Exception as e:
                    print(f"  ✗ 导入 {p['name']} 失败: {e}")
            print("\n注意: 导入的客户端没有私钥，无法生成客户端配置文件")


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="WireGuard 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                                      # 交互式菜单
  %(prog)s servers                              # 列出所有服务端
  %(prog)s use example.com                      # 切换到指定服务端
  %(prog)s use example.com -i wg1               # 切换到指定服务端的 wg1 接口
  %(prog)s init -e example.com                  # 初始化新服务端 (wg0)
  %(prog)s init -e example.com -i wg1 -a 10.1.0.1/24  # 初始化同一服务器的 wg1 接口
  %(prog)s import -f /etc/wireguard/wg0.conf -e example.com  # 从配置文件导入
  %(prog)s import -k <私钥> -e example.com      # 手动输入私钥导入
  %(prog)s add -n phone                         # 添加客户端
  %(prog)s add -n phone --dns 1.1.1.1 --mtu 1420  # 添加客户端 (指定 DNS 和 MTU)
  %(prog)s list                                 # 列出客户端
  %(prog)s export -n phone                      # 显示客户端配置
  %(prog)s export -n phone --save               # 显示并保存到文件
  %(prog)s export -n phone --qr                 # 显示二维码
  %(prog)s server                               # 导出服务端配置
  %(prog)s ssh --host 1.2.3.4                   # 配置 SSH
  %(prog)s sync                                 # 同步到远程服务器
"""
    )

    # 全局选项
    parser.add_argument("-s", "--server", help="指定服务端 (endpoint)")

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # servers 命令
    subparsers.add_parser("servers", help="列出所有服务端")

    # use 命令
    use_parser = subparsers.add_parser("use", help="切换服务端")
    use_parser.add_argument("endpoint", help="服务端 endpoint")
    use_parser.add_argument("-i", "--interface", help="接口名称 (同一 endpoint 多接口时使用)")

    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化新服务端")
    init_parser.add_argument("-e", "--endpoint", required=True, help="公网 IP 或域名")
    init_parser.add_argument("-a", "--address", default="10.0.0.1/24", help="服务端地址")
    init_parser.add_argument("-p", "--port", type=int, default=51820, help="监听端口")
    init_parser.add_argument("-i", "--interface", default="wg0", help="接口名称")

    # import 命令
    import_parser = subparsers.add_parser("import", help="导入已有服务端")
    import_parser.add_argument("-e", "--endpoint", required=True, help="公网 IP 或域名")
    import_group = import_parser.add_mutually_exclusive_group(required=True)
    import_group.add_argument("-f", "--file", help="配置文件路径")
    import_group.add_argument("-k", "--private-key", help="服务端私钥")
    import_group.add_argument("--remote", action="store_true", help="从远程服务器导入")
    import_parser.add_argument("-a", "--address", default="10.0.0.1/24", help="服务端地址")
    import_parser.add_argument("-p", "--port", type=int, default=51820, help="监听端口")
    import_parser.add_argument("-i", "--interface", default="wg0", help="接口名称")
    import_parser.add_argument("--import-peers", action="store_true", help="同时导入客户端")

    # delete-server 命令
    delete_server_parser = subparsers.add_parser("delete-server", help="删除服务端")
    delete_server_parser.add_argument("endpoint", help="服务端 endpoint")
    delete_server_parser.add_argument("-y", "--yes", action="store_true", help="跳过确认")

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加客户端")
    add_parser.add_argument("-n", "--name", required=True, help="客户端名称")
    add_parser.add_argument("--dns", default="", help="DNS 服务器 (留空不设置)")
    add_parser.add_argument("--mtu", type=int, default=1280, help="MTU (默认 1280)")
    add_parser.add_argument("--no-sync", action="store_true", help="不同步到远程")

    # remove 命令
    remove_parser = subparsers.add_parser("remove", help="删除客户端")
    remove_parser.add_argument("-n", "--name", required=True, help="客户端名称")
    remove_parser.add_argument("--no-sync", action="store_true", help="不同步到远程")

    # list 命令
    subparsers.add_parser("list", help="列出客户端")

    # export 命令
    export_parser = subparsers.add_parser("export", help="导出客户端配置")
    export_parser.add_argument("-n", "--name", required=True, help="客户端名称")
    export_parser.add_argument("--qr", action="store_true", help="显示二维码")
    export_parser.add_argument("--save", action="store_true", help="保存到文件")

    # server 命令
    subparsers.add_parser("server", help="导出服务端配置")

    # show 命令
    subparsers.add_parser("show", help="显示服务端配置信息")

    # ssh 命令
    ssh_parser = subparsers.add_parser("ssh", help="配置 SSH 连接")
    ssh_parser.add_argument("--host", required=True, help="服务器地址")
    ssh_parser.add_argument("--port", type=int, default=22, help="SSH 端口")
    ssh_parser.add_argument("--user", default="root", help="用户名")

    # sync 命令
    subparsers.add_parser("sync", help="同步配置到远程服务器")

    # remote-status 命令
    subparsers.add_parser("remote-status", help="查看远程 WireGuard 状态")

    return parser


def main():
    """主入口"""
    import signal

    # 设置信号处理，优雅退出
    def signal_handler(sig, frame):
        print("\n再见!")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    parser = create_parser()
    args = parser.parse_args()

    # 根据 -s 参数选择服务端
    if hasattr(args, 'server') and args.server:
        manager = WireGuardManager()
        if not manager.switch_server_by_endpoint(args.server):
            print(f"错误: 服务端 '{args.server}' 不存在", file=sys.stderr)
            sys.exit(1)
    else:
        manager = WireGuardManager()

    if not args.command:
        interactive_menu(manager)
        return

    try:
        if args.command == "servers":
            servers = manager.get_servers()
            if not servers:
                print("没有服务端")
            else:
                print("服务端列表:")
                for s in servers:
                    current = " (当前)" if s.id == manager.server_id else ""
                    peer_count = len(manager.db.get_peers(s.id))
                    print(f"  {s.endpoint}:{s.interface}\t{s.address}\tPort:{s.listen_port}\t{peer_count} 客户端{current}")

        elif args.command == "use":
            if manager.switch_server_by_endpoint(args.endpoint, args.interface):
                if args.interface:
                    print(f"已切换到服务端: {args.endpoint}:{args.interface}")
                else:
                    print(f"已切换到服务端: {args.endpoint}:{manager.server.interface}")
            else:
                if args.interface:
                    print(f"错误: 服务端 '{args.endpoint}:{args.interface}' 不存在", file=sys.stderr)
                else:
                    print(f"错误: 服务端 '{args.endpoint}' 不存在", file=sys.stderr)
                sys.exit(1)

        elif args.command == "init":
            server = manager.init_server(args.endpoint, args.address, args.port, args.interface)
            print(f"服务端初始化成功!")
            print(f"公钥: {server.public_key}")

        elif args.command == "import":
            if args.file:
                server, existing_peers = manager.import_server_from_config(args.file, args.endpoint)
            elif args.remote:
                server, existing_peers = manager.import_server_from_remote(args.endpoint)
            else:
                server = manager.import_server(
                    args.private_key, args.endpoint, args.address, args.port, args.interface
                )
                existing_peers = []

            print(f"服务端导入成功!")
            print(f"公钥: {server.public_key}")

            if existing_peers:
                print(f"\n发现 {len(existing_peers)} 个已有客户端")
                if args.import_peers:
                    for p in existing_peers:
                        try:
                            manager.import_existing_peer(
                                name=p['name'],
                                public_key=p['public_key'],
                                address=p['allowed_ips'],
                                preshared_key=p.get('preshared_key', '')
                            )
                            print(f"  ✓ 导入 {p['name']}")
                        except Exception as e:
                            print(f"  ✗ 导入 {p['name']} 失败: {e}")

        elif args.command == "delete-server":
            server = manager.db.get_server_by_endpoint(args.endpoint)
            if not server:
                print(f"错误: 服务端 '{args.endpoint}' 不存在", file=sys.stderr)
                sys.exit(1)

            if not args.yes:
                peer_count = len(manager.db.get_peers(server.id))
                confirm = input(f"确定删除 '{args.endpoint}' 及其 {peer_count} 个客户端? (y/n) [n]: ").strip().lower()
                if confirm != 'y':
                    print("已取消")
                    sys.exit(0)

            if manager.delete_server(server.id):
                print(f"已删除服务端: {args.endpoint}")
            else:
                print("删除失败", file=sys.stderr)
                sys.exit(1)

        elif args.command == "add":
            # 多服务端时必须显式指定 -s 参数
            servers = manager.get_servers()
            if len(servers) > 1 and not (hasattr(args, 'server') and args.server):
                print("错误: 存在多个服务端，请使用 -s 参数指定目标服务端", file=sys.stderr)
                print("\n可用服务端:", file=sys.stderr)
                for s in servers:
                    peer_count = len(manager.db.get_peers(s.id))
                    print(f"  -s {s.endpoint}:{s.interface}  ({s.address}, {peer_count} 客户端)", file=sys.stderr)
                print(f"\n示例: wg-manager -s {servers[0].endpoint}:{servers[0].interface} add -n {args.name}", file=sys.stderr)
                sys.exit(1)

            peer = manager.add_peer(args.name, args.dns, args.mtu,
                                    sync_remote=not args.no_sync)
            print(f"客户端 '{args.name}' 添加成功!")
            print(f"IP: {peer.address}")
            print(f"监听端口: {peer.listen_port}")
            # 自动显示客户端配置
            print("\n--- 客户端配置 ---")
            print(manager.get_client_config(args.name))

        elif args.command == "remove":
            if manager.remove_peer(args.name, sync_remote=not args.no_sync):
                print(f"客户端 '{args.name}' 已删除")
            else:
                print(f"错误: 客户端 '{args.name}' 不存在", file=sys.stderr)
                sys.exit(1)

        elif args.command == "list":
            if not manager.peers:
                print(f"没有客户端 [{manager.server.endpoint}]")
            else:
                print(f"客户端列表 [{manager.server.endpoint}]:")
                for p in manager.peers:
                    status = "✓" if p.enabled else "✗"
                    imported = " [导入]" if not p.private_key else ""
                    port_info = f"Port:{p.listen_port}" if p.listen_port else ""
                    print(f"{status} {p.name}{imported}\t{p.address}\t{port_info}\tMTU:{p.mtu}\t{p.created_at[:10]}")

        elif args.command == "export":
            peer = manager.db.get_peer_by_name(args.name, manager.server_id)
            if not peer:
                print(f"错误: 客户端 '{args.name}' 不存在", file=sys.stderr)
                sys.exit(1)
            if not peer.private_key:
                print(f"错误: '{args.name}' 是导入的客户端，没有私钥", file=sys.stderr)
                sys.exit(1)
            if args.qr:
                manager.export_client_qrcode(args.name)
            else:
                print(manager.get_client_config(args.name))
                if args.save:
                    path = manager.export_client_config(args.name)
                    print(f"\n已保存到: {path}", file=sys.stderr)

        elif args.command == "server":
            path = manager.export_server_config()
            print(f"服务端配置已导出: {path}")
            print("\n" + manager.get_server_config())

        elif args.command == "show":
            if not manager.server.private_key:
                print("服务端未初始化", file=sys.stderr)
                sys.exit(1)
            print(f"接口: {manager.server.interface}")
            print(f"公钥: {manager.server.public_key}")
            print(f"地址: {manager.server.address}")
            print(f"端口: {manager.server.listen_port}")
            print(f"Endpoint: {manager.server.endpoint}")
            print(f"客户端数: {len(manager.peers)}")

        elif args.command == "ssh":
            success, msg = manager.setup_ssh(args.host, args.port, args.user)
            if success:
                print(f"SSH 连接配置成功!")
                # 询问是否导入远程配置
                _prompt_import_remote_configs(manager, args.host)
            else:
                print(f"SSH 连接失败: {msg}", file=sys.stderr)
                sys.exit(1)

        elif args.command == "sync":
            success, msg = manager.sync_to_remote()
            if success:
                print(msg)
            else:
                print(f"同步失败: {msg}", file=sys.stderr)
                sys.exit(1)

        elif args.command == "remote-status":
            success, output = manager.get_remote_status()
            if success:
                print(output)
            else:
                print(f"获取远程状态失败: {output}", file=sys.stderr)
                sys.exit(1)

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
