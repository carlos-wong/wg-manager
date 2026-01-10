# 研究报告：客户端添加时的同步机制分析

**日期**: 2026-01-10
**主题**: wg-manager 添加客户端节点时是否先同步服务器

## 结论

当前项目在添加客户端时**只依赖本地数据库分配 IP**，不会先从服务器同步获取最新状态。这存在潜在的本地与服务器数据不一致风险。

## 关键发现

### 本地仓库相关代码

**IP 分配机制** (`wg_manager/manager.py:312-324`)：
- `_get_next_ip()` 方法仅从本地 SQLite 数据库查询已使用的 IP
- 调用 `self.db.get_used_ips()` 获取本地记录的 IP 列表
- 从 2-254 范围内选择第一个未使用的 IP
- **不会从远程服务器获取当前实际的 peer 列表**

**添加客户端流程** (`wg_manager/manager.py:332-370`)：
```python
def add_peer(self, name: str, dns: str, mtu: int, sync_remote: bool = True) -> Peer:
    # 1. 仅检查本地数据库中名称是否存在
    if self.db.get_peer_by_name(name, self._server_id):
        raise ValueError(f"客户端名称 '{name}' 已存在")

    # 2. 从本地数据库分配 IP（不同步远程）
    address = self._get_next_ip()

    # 3. 先写入本地数据库
    peer = self.db.add_peer(peer)

    # 4. 最后才同步到远程（单向推送）
    if sync_remote:
        self._sync_peer_to_remote(peer, action="add")
```

**数据库 IP 查询** (`wg_manager/database.py:284-297`)：
- `get_used_ips()` 仅查询本地 `peers` 表
- 不涉及任何远程操作

### 潜在风险场景

1. **多端管理冲突**：如果有人直接在服务器上用 `wg` 命令添加了 peer，本地不知道
2. **数据库丢失**：重建本地数据库后，可能分配重复 IP
3. **同步失败**：如果远程同步失败，本地已有记录但服务器没有

### Web 搜索发现

业界类似工具的处理方式：
- [dsnet](https://github.com/naggie/dsnet) - 使用单一 JSON 文件作为权威数据源
- [wirey](https://github.com/influxdata/wirey) - 使用分布式后端(etcd/consul)同步 peer
- [wg-portal](https://github.com/h44z/wg-portal) - 使用数据库管理，支持 wgctrl 实时同步

WireGuard 官方立场："密钥分发和配置推送不在 WireGuard 范围内"，需要第三方工具处理。

### 现有缓解措施

项目已有 `import_server_from_remote()` 方法可导入远程配置，但：
- 需要手动调用
- 添加客户端时不会自动触发

## 建议

如需完全避免冲突，可考虑在 `add_peer()` 前先调用远程同步，但会增加延迟和复杂度。

## 参考

### 本地文件
- `wg_manager/manager.py:312-370` - IP 分配和客户端添加逻辑
- `wg_manager/database.py:284-297` - 本地 IP 查询

### Web 来源
- [dsnet - 集中式 WireGuard 管理](https://github.com/naggie/dsnet)
- [wirey - 分布式 WireGuard 同步](https://github.com/influxdata/wirey)
- [wg-portal - 带数据库的 WireGuard Portal](https://github.com/h44z/wg-portal)
