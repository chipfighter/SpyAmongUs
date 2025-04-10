"""
utils: redis utils

Notes:
    仅仅提供关于房间、用户信息的基本增、删、改、查操作，具体的逻辑全部放到service层处理
    同时，尽可能保持mongodb的同步方法，先修改redis再修改磁盘mongodb
    - 关于Redis 连接、断开、检查
    - Redis的一系列基础操作
    - 将用户读入redis
    - 根据用户id删除用户
    - 更新用户名、更新用户密码、更新用户状态、更新用户当前房间
    - 根据id来查找用户所有信息
    - 检查用户是否存在、TTL刷新操作

To-Do:
    - 修改用户的战绩以及画像
"""

import time
from typing import Optional, Set, Dict, Any
import redis.asyncio as redis
from utils.logger_utils import get_logger
from config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB,
    USER_KEY_PREFIX, ROOM_KEY_PREFIX,
    PUBLIC_ROOMS_KEY, ROOM_USERS_KEY_PREFIX,
    ROOM_READY_USERS_KEY_PREFIX, ROOM_ALIVE_PLAYERS_KEY_PREFIX,
    ROOM_ROLES_KEY_PREFIX, ROOM_MESSAGES_KEY_PREFIX,
    ROOM_SECRET_CHAT_MESSAGES_KEY_PREFIX, ROOM_VOTES_KEY_PREFIX,
    ROOM_SECRET_VOTES_KEY_PREFIX, JWT_ACCESS_TOKEN_EXPIRE_MINUTES
)

logger = get_logger(__name__)

class RedisClient:
    def __init__(self):
        """初始化Redis客户端"""
        try:
            self._redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                max_connections=100,  # 最大连接数
                decode_responses=True
            )
            # 设置会话过期时间（与JWT访问令牌过期时间一致）
            self.SESSION_TTL = JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 转换为秒
            logger.info("Redis客户端初始化成功")
        except Exception as e:
            logger.error(f"Redis客户端初始化失败: {str(e)}")
            raise

    async def disconnect(self):
        """断开Redis连接"""
        if self._redis:
            await self._redis.close()
            logger.info("Redis连接已关闭")

    async def check_connection_status(self) -> Dict[str, Any]:
        """
        检查Redis连接状态并返回诊断信息
        
        Returns:
            Dict包含连接状态信息
        """
        result = {
            "connected": False,
            "client_initialized": self._redis is not None,
            "error": None
        }
        
        try:
            if self._redis is None:
                result["error"] = "Redis客户端未初始化"
                return result
                
            # 尝试ping测试
            await self._redis.ping()
            result["connected"] = True
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Redis连接检查失败: {str(e)}")
            
        return result

    # 所有Redis的基础操作
    async def set(self, key: str, value: str, ex: int = None) -> None:
        """设置键值对，可选过期的时间"""
        if ex:
            await self._redis.set(key, value, ex=ex)
        else:
            await self._redis.set(key, value)
            
    async def get(self, key: str) -> Optional[str]:
        """获取键值"""
        return await self._redis.get(key)
        
    async def delete(self, key: str) -> None:
        """删除键"""
        await self._redis.delete(key)
        
    async def sadd(self, key: str, *values) -> None:
        """向集合添加元素"""
        await self._redis.sadd(key, *values)
        
    async def srem(self, key: str, *values) -> None:
        """从集合移除元素"""
        await self._redis.srem(key, *values)
        
    async def smembers(self, key: str) -> Set[str]:
        """获取集合所有成员"""
        return await self._redis.smembers(key)
        
    async def sismember(self, key: str, value: str) -> bool:
        """检查值是否为集合成员"""
        return await self._redis.sismember(key, value)


    # 用户相关的操作
    async def cache_user(self, user_id: str, user_data: dict) -> bool:
        """将用户数据存入Redis缓存"""
        try:
            # 转换所有值为字符串
            string_data = {k: str(v) if v is not None else "" for k, v in user_data.items()}
            await self._redis.hmset(f"user:{user_id}", string_data)
            # 过期时间设置为TTL的时长
            await self._redis.expire(f"user:{user_id}", self.SESSION_TTL)
            return True
        except Exception as e:
            logger.error(f"缓存用户数据失败: {str(e)}")
            return False

    async def delete_user_cache(self, user_id: str) -> bool:
        """删除用户的所有缓存数据"""
        try:
            await self._redis.delete(f"user:{user_id}")
            return True
        except Exception as e:
            logger.error(f"删除用户缓存失败: {str(e)}")
            return False

    async def update_user_status(self, user_id: str, status: str) -> bool:
        """更新用户状态"""
        try:
            await self._redis.hset(f"user:{user_id}", "status", status)
            return True
        except Exception as e:
            logger.error(f"更新用户状态失败: {str(e)}")
            return False

    async def update_username(self, user_id: str, new_username: str) -> bool:
        """更新用户名"""
        try:
            await self._redis.hset(f"user:{user_id}", "username", new_username)
            return True
        except Exception as e:
            logger.error(f"更新用户名失败: {str(e)}")
            return False

    async def update_user_password(self, user_id: str, password_hash: str) -> bool:
        """更新用户密码哈希值"""
        try:
            await self._redis.hset(f"user:{user_id}", "password_hash", password_hash)
            return True
        except Exception as e:
            logger.error(f"更新用户密码失败: {str(e)}")
            return False
        
    async def update_user_room(self, user_id: str, room_id: str = None) -> bool:
        """更新用户当前房间"""
        try:
            if room_id:
                await self._redis.hset(f"user:{user_id}", "current_room", room_id)
            else:
                # 用户离开房间
                await self._redis.hdel(f"user:{user_id}", "current_room")
            return True
        except Exception as e:
            logger.error(f"更新用户房间失败: {str(e)}")
            return False

    async def get_user(self, user_id: str) -> dict:
        """获取用户所有缓存信息"""
        try:
            user_data = await self._redis.hgetall(f"user:{user_id}")
            return user_data
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return {}

    async def user_exists(self, user_id: str) -> bool:
        """检查用户是否存在于缓存"""
        try:
            return await self._redis.exists(f"user:{user_id}") > 0
        except Exception as e:
            logger.error(f"检查用户存在失败: {str(e)}")
            return False

    async def refresh_user_session(self, user_id: str) -> bool:
        """刷新用户会话TTL"""
        try:
            await self._redis.expire(f"user:{user_id}", self.SESSION_TTL)
            return True
        except Exception as e:
            logger.error(f"刷新用户会话TTL失败: {str(e)}")
            return False
