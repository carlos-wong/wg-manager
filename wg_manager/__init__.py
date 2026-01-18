"""WireGuard 管理工具"""

__version__ = "0.2.0"

from .deploy import deploy_server
from .add_peer import add_peer

__all__ = ["deploy_server", "add_peer"]
