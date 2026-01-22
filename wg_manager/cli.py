"""命令行接口"""

import argparse
import sys

from .deploy import deploy_server
from .add_peer import add_peer
from .remove_peer import remove_peer, list_peers


def main() -> None:
    """主入口"""
    parser = argparse.ArgumentParser(
        description="WireGuard 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s deploy root@1.2.3.4                    # 部署（交互式询问配置）
  %(prog)s deploy root@1.2.3.4 -a 10.1.0.1/24 -p 51821 -i wg1  # 指定配置
  %(prog)s add root@1.2.3.4 -n phone              # 添加客户端
  %(prog)s add root@1.2.3.4 -n laptop --allowed-ips "0.0.0.0/0, ::/0"  # 全局代理
  %(prog)s remove root@1.2.3.4 -n phone           # 删除客户端
  %(prog)s list root@1.2.3.4                      # 列出所有客户端
"""
    )

    subparsers = parser.add_subparsers(dest="command")

    # deploy 命令
    deploy_parser = subparsers.add_parser("deploy", help="部署新服务")
    deploy_parser.add_argument("host", help="服务器地址 (user@host)")
    deploy_parser.add_argument("-a", "--address", help="服务端内网地址 (留空交互式询问)")
    deploy_parser.add_argument("-p", "--port", type=int, help="监听端口 (留空交互式询问)")
    deploy_parser.add_argument("-i", "--interface", help="接口名称 (留空交互式询问)")
    deploy_parser.add_argument("--ssh-port", type=int, default=22, help="SSH 端口 (默认: 22)")
    deploy_parser.add_argument("--key-file", help="SSH 私钥文件路径")
    deploy_parser.add_argument("--no-interactive", action="store_true", help="非交互模式，使用默认值")

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加客户端节点")
    add_parser.add_argument("host", help="服务器地址 (user@host)")
    add_parser.add_argument("-n", "--name", required=True, help="客户端名称")
    add_parser.add_argument("--allowed-ips", default="", help="AllowedIPs (默认使用服务端网段)")
    add_parser.add_argument("-i", "--interface", help="指定接口名称 (多接口时可用)")
    add_parser.add_argument("--ssh-port", type=int, default=22, help="SSH 端口 (默认: 22)")
    add_parser.add_argument("--key-file", help="SSH 私钥文件路径")
    add_parser.add_argument("--dns", default="", help="DNS 服务器（留空则不设置）")

    # remove 命令
    remove_parser = subparsers.add_parser("remove", help="删除客户端节点")
    remove_parser.add_argument("host", help="服务器地址 (user@host)")
    remove_parser.add_argument("-n", "--name", required=True, help="客户端名称")
    remove_parser.add_argument("-i", "--interface", help="指定接口名称 (多接口时可用)")
    remove_parser.add_argument("--ssh-port", type=int, default=22, help="SSH 端口 (默认: 22)")
    remove_parser.add_argument("--key-file", help="SSH 私钥文件路径")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有客户端")
    list_parser.add_argument("host", help="服务器地址 (user@host)")
    list_parser.add_argument("-i", "--interface", help="指定接口名称 (留空显示所有)")
    list_parser.add_argument("--ssh-port", type=int, default=22, help="SSH 端口 (默认: 22)")
    list_parser.add_argument("--key-file", help="SSH 私钥文件路径")

    args = parser.parse_args()

    if args.command == "deploy":
        # 判断是否为交互模式：如果没指定任何配置参数，则为交互模式
        interactive = not args.no_interactive
        success = deploy_server(
            host=args.host,
            address=args.address,
            port=args.port,
            interface=args.interface,
            ssh_port=args.ssh_port,
            key_file=args.key_file,
            interactive=interactive
        )
        sys.exit(0 if success else 1)

    elif args.command == "add":
        success = add_peer(
            host=args.host,
            name=args.name,
            allowed_ips=args.allowed_ips,
            interface=args.interface,
            ssh_port=args.ssh_port,
            key_file=args.key_file,
            dns=args.dns
        )
        sys.exit(0 if success else 1)

    elif args.command == "remove":
        success = remove_peer(
            host=args.host,
            name=args.name,
            interface=args.interface,
            ssh_port=args.ssh_port,
            key_file=args.key_file
        )
        sys.exit(0 if success else 1)

    elif args.command == "list":
        success = list_peers(
            host=args.host,
            interface=args.interface,
            ssh_port=args.ssh_port,
            key_file=args.key_file
        )
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
