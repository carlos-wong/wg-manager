# WireGuard Manager

简单的 WireGuard 管理工具，通过 SSH 远程管理服务器上的 WireGuard 配置。

## 功能特性

- **部署服务**: 一键在服务器上部署 WireGuard 服务
- **添加节点**: 添加客户端节点，自动分配 IP，热重载配置（不断线）
- **多接口支持**: 同一服务器可配置多个接口（wg0、wg1...）
- **零本地存储**: 所有配置存储在服务器上，无需本地数据库

## 安装

```bash
pip3 install wg-manager
```

或者使用 [uv](https://github.com/astral-sh/uv)（更快）：

```bash
uv tool install wg-manager
```

### 依赖

- Python 3.10+
- WireGuard 工具链（`wg` 命令，用于生成密钥）
- 系统 `ssh` 命令（用于远程管理）

## 使用方法

### 1. 部署新服务

在服务器上部署新的 WireGuard 接口：

```bash
# 使用默认配置部署 (wg0, 10.0.0.1/24, 端口 51820)
wg-manager deploy root@1.2.3.4

# 自定义配置
wg-manager deploy root@1.2.3.4 -a 10.1.0.1/24 -p 51821 -i wg1
```

**流程**：
1. SSH 连接服务器
2. 生成服务端密钥对
3. 创建 `/etc/wireguard/wgX.conf`
4. 启动服务 `systemctl enable/start wg-quick@wgX`
5. 输出服务端公钥

### 2. 添加客户端节点

添加客户端（如果服务器有多个接口会询问选择）：

```bash
# 添加客户端
wg-manager add root@1.2.3.4 -n phone

# 全局代理（所有流量走 VPN）
wg-manager add root@1.2.3.4 -n laptop --allowed-ips "0.0.0.0/0, ::/0"

# 指定接口
wg-manager add root@1.2.3.4 -n tablet -i wg1
```

**流程**：
1. SSH 连接服务器
2. 扫描 `/etc/wireguard/*.conf`
3. 如果有多个接口 → 询问用户选择（显示接口名+网段）
4. 解析配置，获取已用 IP，分配新 IP
5. 生成客户端密钥对
6. 更新服务器配置，热重载（wg syncconf）
7. 终端输出客户端配置

**注意**: 客户端配置只显示一次，请自行保存！

## 参数说明

### deploy 命令

| 参数 | 说明 | 默认值 |
|------|------|--------|
| host | 服务器地址 (user@host) | 必填 |
| -a, --address | 服务端内网地址 | 10.0.0.1/24 |
| -p, --port | 监听端口 | 51820 |
| -i, --interface | 接口名称 | wg0 |
| --ssh-port | SSH 端口 | 22 |
| --key-file | SSH 私钥文件路径 | - |

### add 命令

| 参数 | 说明 | 默认值 |
|------|------|--------|
| host | 服务器地址 (user@host) | 必填 |
| -n, --name | 客户端名称 | 必填 |
| --allowed-ips | AllowedIPs | 服务端网段 |
| -i, --interface | 指定接口名称 | 自动检测 |
| --ssh-port | SSH 端口 | 22 |
| --key-file | SSH 私钥文件路径 | - |
| --dns | DNS 服务器 | 1.1.1.1 |

## 使用示例

### 场景一：快速搭建 VPN

```bash
# 1. 部署服务
wg-manager deploy root@vpn.example.com

# 输出:
# WireGuard wg0 部署成功!
#   服务器: vpn.example.com
#   地址: 10.0.0.1/24
#   端口: 51820
#   公钥: xxxxxxxxxxxxxxxxxxxxxx

# 2. 添加手机客户端
wg-manager add root@vpn.example.com -n phone

# 输出:
# 客户端 'phone' 添加成功!
#   IP: 10.0.0.2/32
#
# --- 客户端配置（请保存，不会再次显示）---
# [Interface]
# Address = 10.0.0.2/24
# PrivateKey = xxxxx
# DNS = 1.1.1.1
#
# [Peer]
# PublicKey = xxxxx
# ...

# 3. 添加笔记本客户端（全局代理）
wg-manager add root@vpn.example.com -n laptop --allowed-ips "0.0.0.0/0, ::/0"
```

### 场景二：多网段配置

```bash
# 在同一服务器上配置多个 VPN 网段
wg-manager deploy root@vpn.example.com -a 10.0.0.1/24 -p 51820 -i wg0
wg-manager deploy root@vpn.example.com -a 10.1.0.1/24 -p 51821 -i wg1
wg-manager deploy root@vpn.example.com -a 10.2.0.1/24 -p 51822 -i wg2

# 添加客户端到指定接口
wg-manager add root@vpn.example.com -n dev-alice -i wg0
wg-manager add root@vpn.example.com -n ops-bob -i wg1
```

### 场景三：已有服务器添加客户端

如果服务器上已有 WireGuard 配置，直接添加客户端即可：

```bash
# 会自动扫描并使用现有配置
wg-manager add root@1.2.3.4 -n new-client
```

## 工作原理

### 热重载（不断线）

添加客户端时使用 `wg syncconf` 实现热重载：

```
wg-manager add    ──────►    1. 更新 /etc/wireguard/wgX.conf
                             2. wg syncconf wgX (热重载)
                             3. 新客户端立即生效
                             4. 现有连接不受影响
```

### AllowedIPs 说明

- **默认值**: 使用服务端网段（如 `10.0.0.0/24`），只有访问 VPN 内部的流量走 VPN
- **全局代理**: 设置为 `0.0.0.0/0, ::/0`，所有流量都走 VPN

## 项目结构

```
wg_manager/
├── __init__.py      # 导出主要函数
├── cli.py           # 命令行接口
├── deploy.py        # 部署服务逻辑
├── add_peer.py      # 添加节点逻辑
├── ssh.py           # SSH 远程操作
├── crypto.py        # 密钥生成
├── config.py        # 配置常量
└── parser.py        # WireGuard 配置文件解析器
```

## 许可证

MIT
