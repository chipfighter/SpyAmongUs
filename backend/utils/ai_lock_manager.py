"""
utils: ai_lock_manager

Description:
    管理房间级别的AI处理锁
"""

from typing import Optional
from utils.logger_utils import get_logger

logger = get_logger(__name__)

class AILockManager:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        
    async def acquire_lock(self, room_id: str, timeout: int = 60) -> bool:
        """
        获取房间的AI锁
        
        Args:
            room_id: 房间ID
            timeout: 锁超时时间（秒）
            
        Returns:
            bool: 是否成功获取锁
        """
        lock_key = f"room:{room_id}:ai_lock"
        return await self.redis_client.set_nx(lock_key, "1", expire=timeout)
        
    async def release_lock(self, room_id: str) -> None:
        """
        释放房间的AI锁
        
        Args:
            room_id: 房间ID
        """
        lock_key = f"room:{room_id}:ai_lock"
        await self.redis_client.delete(lock_key)
        logger.info(f"已释放房间 {room_id} 的AI锁")
        
    async def is_locked(self, room_id: str) -> bool:
        """
        检查房间是否被锁定
        
        Args:
            room_id: 房间ID
            
        Returns:
            bool: 是否被锁定
        """
        lock_key = f"room:{room_id}:ai_lock"
        return await self.redis_client.exists(lock_key) 