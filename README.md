# WireGuard Manager

一个 Python 命令行工具，用于管理 WireGuard VPN 服务端和客户端配置。

## 功能特性

- **多服务端管理**: 支持管理多个 WireGuard 服务端，按 `endpoint:interface` 组合区分
- **多网段支持**: 同一服务器可配置多个接口（wg0、wg1、wg2...），每个接口独立管理
- **客户端管理**: 添加、删除、启用/禁用客户端，添加后自动显示配置
- **配置导出**: 导出客户端配置内容和二维码，方便手机扫码连接
- **SSH 远程管理**: 通过 SSH 连接远程服务器，自动同步配置并热重载（不中断现有连接）
- **交互式菜单**: 美观的命令行交互界面，适合新手使用
- **命令行模式**: 支持脚本化操作，适合自动化场景

## 安装

```bash
# 克隆项目
git clone https://github.com/leaf0412/wg-manager.git
cd wg-manager

# 使用 uv 安装依赖
uv sync

# 或者使用 pip
pip install -e .
```

### 依赖

- Python 3.10+
- qrencode (用于生成二维码，可选): `brew install qrencode` 或 `apt install qrencode`
- 系统 `ssh` 和 `scp` 命令 (用于远程管理)

## 快速入门

### 场景一：全新搭建 VPN（5 分钟上手）

适用于：第一次搭建 WireGuard VPN，服务器上还没有配置。

```bash
# 第 1 步：初始化服务端（在本地执行）
# 将 1.2.3.4 替换为你的服务器公网 IP
uv run wg-manager init -e 1.2.3.4

# 输出:
# 服务端初始化成功!
# 公钥: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 第 2 步：添加客户端（会自动显示配置）
uv run wg-manager add -n my-phone

# 输出:
# 客户端 'my-phone' 添加成功!
# IP: 10.0.0.2/32
# 监听端口: 54321
#
# --- 客户端配置 ---
# [Interface]
# Address = 10.0.0.2/24
# ...（完整配置）

# 第 3 步：显示二维码，用手机 WireGuard App 扫码
uv run wg-manager export -n my-phone --qr

# 第 4 步：导出服务端配置
uv run wg-manager server

# 第 5 步：将服务端配置部署到服务器
# 方法 A：手动复制（显示的配置内容复制到服务器 /etc/wireguard/wg0.conf）
# 方法 B：使用 SSH 自动同步（见下方）
```

**服务器端部署命令：**

```bash
# 在服务器上执行
sudo cp wg0.conf /etc/wireguard/
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
```

### 场景二：导入现有配置 + SSH 自动同步

适用于：服务器上已有 WireGuard 配置，希望用本工具管理并自动同步。

```bash
# 第 1 步：配置 SSH 连接
uv run wg-manager ssh --host 1.2.3.4

# 输出: SSH 连接配置成功!

# 第 2 步：从远程服务器导入配置
uv run wg-manager import --remote -e 1.2.3.4

# 输出:
# 服务端导入成功!
# 公钥: xxxxxxxxxx
# 发现 3 个已有客户端
# 是否导入这些客户端? (y/n)

# 第 3 步：添加新客户端（自动同步到服务器，无需手动操作）
uv run wg-manager add -n new-laptop

# 输出:
# 客户端 'new-laptop' 添加成功!
# --- 客户端配置 ---
# ...
# （配置已自动同步到远程服务器）

# 第 4 步：查看远程服务器状态
uv run wg-manager remote-status
```

### 场景三：使用交互式菜单

适用于：不想记命令，喜欢菜单操作的用户。

```bash
uv run wg-manager
```

```
┌────────────────────────────────────────────────┐
│              WireGuard 管理工具                │
└────────────────────────────────────────────────┘

  当前: 1.2.3.4:wg0
  2 个客户端
  ● SSH 已连接

┌─ 服务端 ───────────────────────────────────────┐
│  1. 初始化新服务端      2. 从文件导入          │
│  3. 手动输入私钥导入    4. 查看配置            │
│  5. 切换服务端          6. 删除服务端          │
├─ 客户端 ───────────────────────────────────────┤
│  7. 添加客户端          8. 删除客户端          │
│  9. 启用/禁用          10. 列出所有            │
│ 11. 导出配置           12. 显示二维码          │
├─ 远程管理 ─────────────────────────────────────┤
│ 13. 配置 SSH           14. 从远程导入          │
│ 15. 同步到远程         16. 查看远程状态        │
├─ 其他 ─────────────────────────────────────────┤
│ 17. 导出服务端配置      0. 退出                │
└────────────────────────────────────────────────┘
请选择 [0-17]:
```

**常用操作：**
- 输入 `7` → 添加客户端 → 输入名称 → 自动显示配置
- 输入 `12` → 显示二维码 → 手机扫码连接
- 输入 `10` → 查看所有客户端列表

**提示**: 在任何输入环节，按 `Ctrl+C` 可返回主菜单或退出。

## 常用命令速查

| 功能 | 命令 |
|------|------|
| 交互式菜单 | `wg-manager` |
| 初始化服务端 | `wg-manager init -e <IP>` |
| 添加客户端 | `wg-manager add -n <名称>` |
| 显示二维码 | `wg-manager export -n <名称> --qr` |
| 列出客户端 | `wg-manager list` |
| 删除客户端 | `wg-manager remove -n <名称>` |
| 配置 SSH | `wg-manager ssh --host <IP>` |
| 同步到服务器 | `wg-manager sync` |
| 查看服务端列表 | `wg-manager servers` |
| 切换服务端 | `wg-manager use <endpoint> -i <接口>` |

## 完整命令参考

### 服务端管理

```bash
# 初始化新服务端
wg-manager init -e <IP或域名> [-a <地址>] [-p <端口>] [-i <接口名>]
# 示例:
wg-manager init -e vpn.example.com
wg-manager init -e vpn.example.com -a 10.1.0.1/24 -p 51821 -i wg1

# 从配置文件导入
wg-manager import -f <配置文件路径> -e <IP或域名>
# 示例:
wg-manager import -f /etc/wireguard/wg0.conf -e vpn.example.com

# 从远程服务器导入（需先配置 SSH）
wg-manager import --remote -e <IP或域名>

# 手动输入私钥导入
wg-manager import -k <私钥> -e <IP或域名>

# 查看所有服务端
wg-manager servers

# 切换服务端
wg-manager use <endpoint>
wg-manager use <endpoint> -i <接口名>  # 同一服务器多接口时

# 查看当前服务端配置
wg-manager show

# 导出服务端配置文件
wg-manager server

# 删除服务端
wg-manager delete-server <endpoint>
wg-manager delete-server <endpoint> -y  # 跳过确认
```

### 客户端管理

```bash
# 添加客户端（添加后自动显示配置）
wg-manager add -n <名称>
wg-manager add -n <名称> --dns 1.1.1.1  # 指定 DNS
wg-manager add -n <名称> --mtu 1420     # 指定 MTU
wg-manager add -n <名称> --no-sync      # 不自动同步到远程

# 列出所有客户端
wg-manager list

# 显示客户端配置
wg-manager export -n <名称>
wg-manager export -n <名称> --save  # 同时保存到文件
wg-manager export -n <名称> --qr    # 显示二维码

# 删除客户端
wg-manager remove -n <名称>
wg-manager remove -n <名称> --no-sync  # 不自动同步到远程
```

### SSH 远程管理

```bash
# 配置 SSH 连接
wg-manager ssh --host <IP> [--port <端口>] [--user <用户名>]
# 示例:
wg-manager ssh --host 1.2.3.4
wg-manager ssh --host 1.2.3.4 --port 2222 --user admin

# 手动同步配置到远程
wg-manager sync

# 查看远程 WireGuard 状态
wg-manager remote-status
```

### 指定服务端操作

使用 `-s` 参数指定要操作的服务端:

```bash
wg-manager -s vpn.example.com add -n phone
wg-manager -s vpn.example.com list
```

## 多网段场景

当一台服务器需要配置多个 WireGuard 网段时（如隔离不同团队或用途），可以使用多接口方式管理。

### 使用场景示例

假设有一台公网服务器 `vpn.example.com`，需要配置三个独立的 VPN 网段：

| 接口 | 网段 | 端口 | 用途 |
|------|------|------|------|
| wg0 | 10.0.0.0/24 | 51820 | 开发团队 |
| wg1 | 10.1.0.0/24 | 51821 | 运维团队 |
| wg2 | 10.2.0.0/24 | 51822 | 测试环境 |

### 配置步骤

```bash
# 1. 初始化三个服务端接口
wg-manager init -e vpn.example.com -a 10.0.0.1/24 -p 51820 -i wg0
wg-manager init -e vpn.example.com -a 10.1.0.1/24 -p 51821 -i wg1
wg-manager init -e vpn.example.com -a 10.2.0.1/24 -p 51822 -i wg2

# 2. 查看所有服务端
wg-manager servers
# 输出:
#   vpn.example.com:wg0    10.0.0.1/24    Port:51820    0 客户端 (当前)
#   vpn.example.com:wg1    10.1.0.1/24    Port:51821    0 客户端
#   vpn.example.com:wg2    10.2.0.1/24    Port:51822    0 客户端

# 3. 在 wg0 添加客户端
wg-manager add -n dev-alice
wg-manager add -n dev-bob

# 4. 切换到 wg1 并添加客户端
wg-manager use vpn.example.com -i wg1
wg-manager add -n ops-charlie

# 5. 切换到 wg2 并添加客户端
wg-manager use vpn.example.com -i wg2
wg-manager add -n test-server-1
```

### 从现有配置导入

```bash
# 导入多个配置文件（自动识别接口名）
wg-manager import -f /etc/wireguard/wg0.conf -e vpn.example.com
wg-manager import -f /etc/wireguard/wg1.conf -e vpn.example.com
wg-manager import -f /etc/wireguard/wg2.conf -e vpn.example.com
```

## 远程管理原理

配置 SSH 后，添加/删除客户端会自动同步到远程服务器:

```
本地操作                    远程服务器
───────                    ──────────
add -n phone    ──────►    1. 更新 /etc/wireguard/wg0.conf
                           2. 执行 wg syncconf wg0 (热重载)
                           3. 新客户端立即生效，现有连接不中断

remove -n phone ──────►    1. 更新 /etc/wireguard/wg0.conf
                           2. 执行 wg set wg0 peer <pubkey> remove
                           3. 客户端立即断开
```

**特点：**
- 使用 `wg syncconf` 实现热重载，**不会中断现有 VPN 连接**
- 配置文件和运行状态同时更新，重启后配置不丢失
- 如果 SSH 未配置，仅更新本地数据库，需手动同步

## 数据存储

配置数据保存在 `~/.wg_manager/` 目录:

```
~/.wg_manager/
├── wg_manager.db      # SQLite 数据库（服务端、客户端信息）
├── wg0.conf           # 导出的服务端配置
└── clients/           # 导出的客户端配置文件
    ├── phone.conf
    └── laptop.conf
```

**备份：** 只需备份 `~/.wg_manager/wg_manager.db` 文件即可恢复所有配置。

## 常见问题

### Q: 添加客户端后，手机如何连接？

```bash
# 显示二维码
wg-manager export -n phone --qr

# 手机打开 WireGuard App → 点击 + → 扫描二维码
```

### Q: 如何让客户端访问所有流量（全局代理）？

编辑客户端配置，将 `AllowedIPs` 改为 `0.0.0.0/0, ::/0`：

```ini
[Peer]
AllowedIPs = 0.0.0.0/0, ::/0  # 所有流量走 VPN
```

### Q: SSH 连接失败怎么办？

```bash
# 1. 确保能正常 SSH 登录
ssh root@1.2.3.4

# 2. 确保服务器上有 WireGuard
ssh root@1.2.3.4 "wg --version"

# 3. 重新配置 SSH
wg-manager ssh --host 1.2.3.4
```

### Q: 如何迁移到新电脑？

```bash
# 旧电脑：备份数据库
cp ~/.wg_manager/wg_manager.db /path/to/backup/

# 新电脑：恢复数据库
mkdir -p ~/.wg_manager
cp /path/to/backup/wg_manager.db ~/.wg_manager/
```

## 项目结构

```
wg-manager/
├── pyproject.toml      # 项目配置
├── README.md           # 说明文档
└── wg_manager/         # 源码目录
    ├── __init__.py     # 包初始化
    ├── cli.py          # 命令行接口
    ├── manager.py      # 核心管理逻辑
    ├── database.py     # SQLite 数据库操作
    ├── models.py       # 数据模型
    ├── config.py       # 配置常量
    ├── crypto.py       # WireGuard 密钥生成
    └── ssh.py          # SSH 远程管理
```

## 许可证

MIT
