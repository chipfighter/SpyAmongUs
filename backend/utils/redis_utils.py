"""
utils: redis utils

Description:
    仅仅提供关于房间、用户信息的基本增、删、改、查操作，具体的逻辑全部放到service层处理

Notes:
    同时，尽可能保持mongodb的同步方法，先修改redis再修改磁盘mongodb
    - 关于Redis 连接、断开、检查
    - Redis的一系列基础操作
    - 检查用户是否存在、TTL刷新操作
    用户：
        - 将用户读入redis
        - 根据用户id删除用户
        - 更新用户名、更新用户头像、更新用户状态、更新用户当前房间
        - 根据id来查找用户所有信息
    房间：
        - 创建房间
        - 删除房间
        - 修改房间状态、加入新用户、删除房间用户（普通用户）、删除房间用户（房主）、更新房间活动时间
        - 查看当前房间的所有用户ID
    消息：
        - 添加消息（根据房间邀请码，是否secret channel）

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
    ROOM_SECRET_VOTES_KEY_PREFIX, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, MIN_PLAYERS, MIN_SPY_COUNT, MAX_SPEAK_TIME,
    MAX_LAST_WORDS_TIME, MAX_ROUNDS
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
        """检查Redis连接状态并返回诊断信息
        
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


    # 用户相关
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
        """删除用户的所有缓存数据

        Notes:
            这里的删除是删除redis缓存，即 用户退出系统/超过掉线时间 的时候执行
        """
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

    async def update_avatar(self, user_id: str, new_avatar_url: str) -> bool:
        """更新用户新头像"""
        try:
            await self._redis.hset(f"user:{user_id}", "avatar_url", new_avatar_url)
            return True
        except Exception as e:
            logger.error(f"更新用户头像失败: {str(e)}")
            return False

    async def update_current_room(self, user_id: str, room_id: str = None) -> bool:
        """更新用户当前所在房间"""
        try:
            # 如果room_id为None，表示用户离开房间
            value = room_id if room_id is not None else ""
            await self._redis.hset(f"user:{user_id}", "current_room", value)
            return True
        except Exception as e:
            logger.error(f"更新用户当前房间失败: {str(e)}")
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
        """检查用户是否存在于缓存

        Notes:
            这个功能主要是给前端断线以后重新进行的调用
        """
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


    # 房间相关
    async def cache_room(self, invite_code: str, room_data: dict) -> bool:
        """将房间数据存入Redis缓存

        Args:
            invite_code: 房间邀请码
            room_data: 房间数据字典（业务层实例化对象以后封装）

        Returns:
            bool: 操作是否成功

        Notes:
            与用户相关的初始化内容放到了service层，
            存活玩家、角色分配、投票纪录、秘密聊天投票、秘密聊天消息 在游戏开始的时候进行
        """
        try:
            # 转换所有值为字符串
            string_data = {k: str(v) if v is not None else "" for k, v in room_data.items()}

            # 1. 存储房间基本信息（哈希表）
            room_key = f"{ROOM_KEY_PREFIX}{invite_code}"
            await self._redis.hmset(room_key, string_data)

            # 2. 如果是公开房间，添加到公开房间集合
            if string_data.get("is_public") == "True":
                await self._redis.sadd(PUBLIC_ROOMS_KEY, invite_code)

            # 3. 创建房间的用户集合（只有房主）
            users_key = ROOM_USERS_KEY_PREFIX % invite_code
            await self._redis.sadd(users_key, room_data["host_id"])

            # 4. 初始化空的准备用户集合
            ready_users_key = ROOM_READY_USERS_KEY_PREFIX % invite_code
            await self._redis.delete(ready_users_key)  # 确保集合为空

            # 5. 初始化空的房间消息列表
            messages_key = ROOM_MESSAGES_KEY_PREFIX % invite_code
            await self._redis.delete(messages_key)  # 确保列表为空

            return True
        except Exception as e:
            logger.error(f"缓存房间数据失败: {str(e)}")
            return False

    async def delete_room(self, invite_code: str) -> bool:
        """删除Redis中的房间数据以及相关数据（仅处理房间的相关删除）"""
        try:
            # 删除房间基本信息
            room_key = f"{ROOM_KEY_PREFIX}{invite_code}"
            await self._redis.delete(room_key)

            # 从公开房间集合中移除
            await self._redis.srem(PUBLIC_ROOMS_KEY, invite_code)

            # 删除房间的其他集合
            keys_to_delete = [
                ROOM_USERS_KEY_PREFIX % invite_code,
                ROOM_READY_USERS_KEY_PREFIX % invite_code,
                ROOM_ALIVE_PLAYERS_KEY_PREFIX % invite_code,
                ROOM_ROLES_KEY_PREFIX % invite_code,
                ROOM_MESSAGES_KEY_PREFIX % invite_code,
                ROOM_SECRET_CHAT_MESSAGES_KEY_PREFIX % invite_code
            ]

            # 删除投票记录
            votes_key = ROOM_VOTES_KEY_PREFIX % (invite_code, "*")
            vote_keys = await self._redis.keys(votes_key)
            for key in vote_keys:
                await self._redis.delete(key)

            # 删除秘密投票记录
            secret_votes_key = ROOM_SECRET_VOTES_KEY_PREFIX % (invite_code, "*")
            secret_vote_keys = await self._redis.keys(secret_votes_key)
            for key in secret_vote_keys:
                await self._redis.delete(key)

            # 删除基本集合
            for key in keys_to_delete:
                await self._redis.delete(key)

            return True
        except Exception as e:
            logger.error(f"删除房间数据失败: {str(e)}")
            return False

    async def get_room_users(self, invite_code: str) -> Set[str]:
        """获取房间中的所有用户ID"""
        try:
            users_key = ROOM_USERS_KEY_PREFIX % invite_code
            return await self._redis.smembers(users_key)
        except Exception as e:
            logger.error(f"获取房间用户失败: {str(e)}")
            return set()

    async def get_room_host(self, invite_code: str) -> str:
        """获取房间房主ID"""
        try:
            room_key = f"{ROOM_KEY_PREFIX}{invite_code}"
            # 直接使用hget只获取房主ID字段
            host_id = await self._redis.hget(room_key, "host_id")
            return host_id if host_id else ""
        except Exception as e:
            logger.error(f"获取房间房主失败: {str(e)}")
            return ""

    async def get_room_basic_data(self, invite_code: str) -> dict:
        """
        获取房间基本数据信息

        返回 房间创建时的基本信息、房间中的用户列表

        Args:
            invite_code: 房间邀请码
            
        Returns:
            dict: 房间的完整数据字典，包括基本信息和关联数据集合
        """
        try:
            # 获取房间基本信息
            room_key = f"{ROOM_KEY_PREFIX}{invite_code}"
            room_data = await self._redis.hgetall(room_key)
            
            if not room_data:
                return {}
                
            # 获取房间用户列表
            users_key = ROOM_USERS_KEY_PREFIX % invite_code
            users = await self._redis.smembers(users_key)
            room_data["users"] = list(users)

            return room_data
        except Exception as e:
            logger.error(f"获取房间数据失败: {str(e)}")
            return {}
            
    async def check_room_exists(self, invite_code: str) -> bool:
        """检查房间是否存在"""
        try:
            room_key = f"{ROOM_KEY_PREFIX}{invite_code}"
            return await self._redis.exists(room_key) > 0
        except Exception as e:
            logger.error(f"检查房间是否存在失败: {str(e)}")
            return False
