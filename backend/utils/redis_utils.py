"""
Redis工具类

Description:
    本系统使用Redis作为缓存层，处理与房间相关的临时数据和状态。
    主要保存（配合config.py查看）：
        1.房间信息
        2.邀请码->房间ID的索引
        3.房间内的消息
        4.公共房间ID
        5.用户在线状态
        6.在线用户ID
        7.用户所在的房间
        8.房间中的用户列表（为了快速查询）
        9.用户基本信息缓存

"""

import json
from typing import Dict, List, Optional, Set
import redis.asyncio as redis
from utils.logger_utils import get_logger
from config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB,
    ROOM_KEY_PREFIX, ROOM_CODE_KEY_PREFIX,
    ROOM_MESSAGES_KEY_PREFIX, PUBLIC_ROOMS_KEY, 
    USER_CURRENT_ROOM_KEY_PREFIX, USER_STATUS_KEY_PREFIX,
    ROOM_USERS_KEY_PREFIX, USER_INFO_KEY_PREFIX,
)

logger = get_logger(__name__)

class RedisClient:
    def __init__(self):
        self._redis = None
        self._pool = None

    async def connect(self):
        """连接Redis，使用连接池"""
        try:
            self._pool = redis.ConnectionPool(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                max_connections=100,  # 最大连接数
                decode_responses=True
            )
            self._redis = redis.Redis(connection_pool=self._pool)
            
            # 测试连接
            await self._redis.ping()
            logger.info(f"成功连接到Redis: {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            logger.error(f"连接Redis失败: {str(e)}")
            raise

    async def disconnect(self):
        """断开Redis连接，关闭redis示例+断开连接"""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.disconnect()

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

    # Room相关的操作
    async def save_room(self, room_id: str, room_data: Dict) -> None:
        """保存房间信息"""
        try:
            if self._redis is None:
                logger.error("Redis客户端未初始化，无法保存房间")
                raise Exception("Redis客户端未初始化")
                
            # 确保所有集合类型字段都转换为列表，因为Redis不能直接存储集合
            set_fields = ["users", "leaving_in_game_users", "ready_users"]
            for field in set_fields:
                if field in room_data and isinstance(room_data[field], set):
                    room_data[field] = list(room_data[field])

            # 检查room_data是否包含所有必要字段
            required_fields = ["id", "name", "host_id", "invitation_code"]
            missing_fields = [field for field in required_fields if field not in room_data]
            if missing_fields:
                error_msg = f"房间数据缺少必要字段: {', '.join(missing_fields)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # 将所有值转换为字符串，以避免Redis存储问题
            string_room_data = {k: str(v) for k, v in room_data.items()}
            
            logger.info(f"保存房间 {room_id} 数据: {string_room_data}")
            await self._redis.hset(f"{ROOM_KEY_PREFIX}{room_id}", mapping=string_room_data)
            
            # 设置更长的安全过期时间(24小时)，作为15min监听机制的安全措施
            await self._redis.expire(f"{ROOM_KEY_PREFIX}{room_id}", 86400)
        except Exception as e:
            logger.error(f"保存房间失败 {room_id}: {str(e)}")
            raise

    async def get_room(self, room_id: str) -> Optional[Dict]:
        """获取房间信息"""
        return await self._redis.hgetall(f"{ROOM_KEY_PREFIX}{room_id}")

    async def delete_room(self, room_id: str) -> None:
        """删除房间"""
        # 删除房间信息
        await self._redis.delete(f"{ROOM_KEY_PREFIX}{room_id}")
        # 从公开房间列表移除
        await self.remove_from_public_rooms(room_id)
        # 删除房间消息
        await self._redis.delete(f"{ROOM_MESSAGES_KEY_PREFIX}{room_id}")
        
        # 查找并更新所有在这个房间的用户
        all_user_keys = await self._redis.keys(f"{USER_CURRENT_ROOM_KEY_PREFIX}*")
        for user_key in all_user_keys:
            user_room_id = await self._redis.get(user_key)
            if user_room_id == room_id:
                user_id = user_key.replace(USER_CURRENT_ROOM_KEY_PREFIX, "")
                # 清除用户当前房间
                await self._redis.delete(user_key)
                # 更新用户状态为在线
                await self._redis.set(f"{USER_STATUS_KEY_PREFIX}{user_id}", "online")

    async def save_room_code(self, code: str, room_id: str) -> None:
        """保存邀请码到房间ID的映射"""
        await self._redis.set(f"{ROOM_CODE_KEY_PREFIX}{code}", room_id)
        await self._redis.expire(f"{ROOM_CODE_KEY_PREFIX}{code}", 900)

    async def get_room_by_code(self, code: str) -> Optional[str]:
        """通过邀请码获取房间ID"""
        return await self._redis.get(f"{ROOM_CODE_KEY_PREFIX}{code}")

    async def add_to_public_rooms(self, room_id: str) -> None:
        """添加房间到公开房间列表"""
        await self._redis.sadd(PUBLIC_ROOMS_KEY, room_id)

    async def remove_from_public_rooms(self, room_id: str) -> None:
        """从公开房间列表移除房间"""
        await self._redis.srem(PUBLIC_ROOMS_KEY, room_id)

    async def get_public_rooms(self) -> List[str]:
        """获取所有公开房间ID"""
        return await self._redis.smembers(PUBLIC_ROOMS_KEY)

    # 用户房间关系
    async def add_user_to_room(self, user_id: str, room_id: str) -> None:
        """添加用户到房间，同时设置用户当前房间"""
        # 设置用户当前房间
        await self._redis.set(f"{USER_CURRENT_ROOM_KEY_PREFIX}{user_id}", room_id)
        
        # 更新房间的users字段 (从房间哈希表中获取当前users，添加新用户后更新)
        room_data = await self.get_room(room_id)
        if room_data:
            # 解析当前users字段
            current_users = []
            if "users" in room_data:
                users_str = room_data["users"]
                if users_str.startswith("[") and users_str.endswith("]"):
                    import ast
                    try:
                        current_users = ast.literal_eval(users_str)
                    except:
                        pass
            
            # 添加新用户
            if user_id not in current_users:
                current_users.append(user_id)
                
            # 更新房间数据
            await self._redis.hset(f"{ROOM_KEY_PREFIX}{room_id}", "users", str(current_users))
        
        # 添加到房间用户集合（用于快速查询）
        await self._redis.sadd(f"{ROOM_USERS_KEY_PREFIX}{room_id}", user_id)

    async def remove_user_from_room(self, user_id: str, room_id: str) -> None:
        """从房间移除用户，清除用户当前房间"""
        # 清除用户当前房间
        await self._redis.delete(f"{USER_CURRENT_ROOM_KEY_PREFIX}{user_id}")
        
        # 更新房间的users字段
        room_data = await self.get_room(room_id)
        if room_data and "users" in room_data:
            # 解析当前users字段
            current_users = []
            users_str = room_data["users"]
            if users_str.startswith("[") and users_str.endswith("]"):
                import ast
                try:
                    current_users = ast.literal_eval(users_str)
                except:
                    pass
            
            # 移除用户
            if user_id in current_users:
                current_users.remove(user_id)
                
            # 更新房间数据
            await self._redis.hset(f"{ROOM_KEY_PREFIX}{room_id}", "users", str(current_users))
        
        # 从房间用户集合中移除
        await self._redis.srem(f"{ROOM_USERS_KEY_PREFIX}{room_id}", user_id)

    async def get_user_current_room(self, user_id: str) -> Optional[str]:
        """获取用户当前所在房间ID"""
        return await self._redis.get(f"{USER_CURRENT_ROOM_KEY_PREFIX}{user_id}")
    
    async def get_room_users(self, room_id: str) -> Set[str]:
        """获取房间内所有用户ID"""
        return await self._redis.smembers(f"{ROOM_USERS_KEY_PREFIX}{room_id}")
    
    # 用户信息缓存
    async def save_user_info(self, user_id: str, user_info: Dict) -> None:
        """缓存用户基本信息"""
        await self._redis.hset(f"{USER_INFO_KEY_PREFIX}{user_id}", mapping=user_info)
        # 设置过期时间（1天）
        await self._redis.expire(f"{USER_INFO_KEY_PREFIX}{user_id}", 86400)
    
    async def get_user_info(self, user_id: str) -> Dict:
        """获取用户基本信息"""
        return await self._redis.hgetall(f"{USER_INFO_KEY_PREFIX}{user_id}")

    # 消息相关操作
    async def save_message(self, room_id: str, message: Dict) -> None:
        """保存消息到房间消息列表"""
        await self._redis.lpush(f"{ROOM_MESSAGES_KEY_PREFIX}{room_id}", json.dumps(message))
        # 限制消息历史记录数量
        await self._redis.ltrim(f"{ROOM_MESSAGES_KEY_PREFIX}{room_id}", 0, 99)

    async def get_messages(self, room_id: str, limit: int = 50) -> List[Dict]:
        """获取房间的消息历史"""
        messages = await self._redis.lrange(f"{ROOM_MESSAGES_KEY_PREFIX}{room_id}", 0, limit - 1)
        return [json.loads(msg) for msg in messages]

    # 通用操作
    async def expire(self, key: str, seconds: int) -> None:
        """设置key的过期时间"""
        await self._redis.expire(key, seconds)

    async def exists(self, key: str) -> bool:
        """检查key是否存在"""
        return await self._redis.exists(key)