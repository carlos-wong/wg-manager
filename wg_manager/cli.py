"""命令行接口"""

import argparse
import sys

from .deploy import deploy_server
from .add_peer import add_peer


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="WireGuard 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s deploy root@1.2.3.4                    # 部署 WireGuard 服务（默认 wg0）
  %(prog)s deploy root@1.2.3.4 -a 10.1.0.1/24 -p 51821 -i wg1  # 自定义配置
  %(prog)s add root@1.2.3.4 -n phone              # 添加客户端
  %(prog)s add root@1.2.3.4 -n laptop --allowed-ips "0.0.0.0/0, ::/0"  # 全局代理
"""
    )

    subparsers = parser.add_subparsers(dest="command")

    # deploy 命令
    deploy_parser = subparsers.add_parser("deploy", help="部署新服务")
    deploy_parser.add_argument("host", help="服务器地址 (user@host)")
    deploy_parser.add_argument("-a", "--address", default="10.0.0.1/24", help="服务端内网地址 (默认: 10.0.0.1/24)")
    deploy_parser.add_argument("-p", "--port", type=int, default=51820, help="监听端口 (默认: 51820)")
    deploy_parser.add_argument("-i", "--interface", default="wg0", help="接口名称 (默认: wg0)")
    deploy_parser.add_argument("--ssh-port", type=int, default=22, help="SSH 端口 (默认: 22)")
    deploy_parser.add_argument("--key-file", help="SSH 私钥文件路径")

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加客户端节点")
    add_parser.add_argument("host", help="服务器地址 (user@host)")
    add_parser.add_argument("-n", "--name", required=True, help="客户端名称")
    add_parser.add_argument("--allowed-ips", default="", help="AllowedIPs (默认使用服务端网段)")
    add_parser.add_argument("-i", "--interface", help="指定接口名称 (多接口时可用)")
    add_parser.add_argument("--ssh-port", type=int, default=22, help="SSH 端口 (默认: 22)")
    add_parser.add_argument("--key-file", help="SSH 私钥文件路径")
    add_parser.add_argument("--dns", default="1.1.1.1", help="DNS 服务器 (默认: 1.1.1.1)")

    args = parser.parse_args()

    if args.command == "deploy":
        success = deploy_server(
            host=args.host,
            address=args.address,
            port=args.port,
            interface=args.interface,
            ssh_port=args.ssh_port,
            key_file=args.key_file
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

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
