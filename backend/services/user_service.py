"""
service: user_service
"""
from typing import Dict, Optional, List, Tuple
import uuid
from models.user import User
from utils.redis_utils import RedisClient
from utils.mongo_utils import MongoClient
from utils.logger_utils import get_logger
from config import (
    USER_STATUS_KEY_PREFIX, 
    USER_ONLINE_SET_KEY,
    USER_STATUS_ONLINE, 
    USER_STATUS_OFFLINE,
    USER_STATUS_IN_ROOM,
    USER_STATUS_PLAYING
)


logger = get_logger(__name__)

class UserService:
    def __init__(self, redis_client: RedisClient, mongo_client: MongoClient = None):
        self.redis = redis_client
        self.mongo = mongo_client
        # 存储用户WebSocket连接
        self.user_connections: Dict[str, any] = {}

    def register_connection(self, user_id: str, websocket: any) -> None:
        """注册用户WebSocket连接"""
        self.user_connections[user_id] = websocket

    def unregister_connection(self, user_id: str) -> None:
        """取消注册用户WebSocket连接"""
        if user_id in self.user_connections:
            del self.user_connections[user_id]

    def get_connection(self, user_id: str) -> Optional[any]:
        """获取用户的WebSocket连接"""
        return self.user_connections.get(user_id)

    async def create_temp_user(self, user_id: str, username: str) -> User:
        """创建临时用户"""
        user = User.create_temp_user(user_id, username)
        
        # 如果MongoDB可用，保存用户到数据库
        if self.mongo is not None and self.mongo._db is not None:
            # 检查用户是否已存在
            existing_user = await self.mongo.find_user(user_id)
            if not existing_user:
                # 创建新用户
                await self.mongo.create_user(user.dict())
        
        return user

    async def create_user(self, username: str, password: str) -> Tuple[bool, Optional[User], str]:
        """创建带密码的新用户"""
        if self.mongo is None or self.mongo._db is None:
            return False, None, "MongoDB未连接"
            
        # 检查用户名是否已存在
        existing_user = await self.mongo.find_user_by_username(username)
        if existing_user:
            return False, None, "用户名已存在"
            
        # 创建新用户
        user = User.create_user(username, password)
        
        # 保存到数据库
        result = await self.mongo.create_user(user.dict())
        if not result:
            return False, None, "创建用户失败"
            
        return True, user, "用户创建成功"

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过ID获取用户"""
        if self.mongo is None or self.mongo._db is None:
            return None
            
        user_data = await self.mongo.find_user(user_id)
        if user_data:
            return User(**user_data)
        return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        if self.mongo is None or self.mongo._db is None:
            return None
            
        user_data = await self.mongo.find_user_by_username(username)
        if user_data:
            return User(**user_data)
        return None

    async def login_user(self, username: str) -> Optional[User]:
        """用户登录（简化版，仅使用用户名）"""
        # 检查用户是否存在
        user = None
        if self.mongo is not None and self.mongo._db is not None:
            user_data = await self.mongo.find_user_by_username(username)
            if user_data:
                user = User(**user_data)
        
        # 如果用户不存在，创建新用户
        if not user:
            user_id = f"usr_{uuid.uuid4().hex[:12]}"
            user = await self.create_temp_user(user_id, username)
        
        # 更新用户状态为在线
        await self.set_user_online(user.id)
        
        return user

    async def login_with_password(self, username: str, password: str) -> Tuple[bool, Optional[User], str]:
        """使用密码登录"""
        try:
            # 检查MongoDB连接
            if self.mongo is None or self.mongo._db is None:
                logger.error("MongoDB未连接，登录失败")
                return False, None, "MongoDB未连接"
                
            # 查找用户（使用mongodb_utils根据用户名称来寻找对应的salt）
            user_data = await self.mongo.find_user_by_username(username)
            if not user_data:
                logger.warn(f"用户不存在: {username}")
                return False, None, "用户不存在"
            
            # 实例化用户对象
            user = User(**user_data)
            
            # 然后再调用user下的function来验证密码
            if not user.verify_password(password):
                logger.warn(f"密码验证失败: {username}")
                return False, None, "密码错误"
            
            # 更新用户状态为在线
            await self.set_user_online(user.id)
            
            logger.info(f"用户登录成功: {username}")
            return True, user, "登录成功"
            
        except Exception as e:
            logger.error(f"登录过程出错: {str(e)}")
            return False, None, f"登录失败: {str(e)}"

    async def update_user_status(self, user_id: str, status: str) -> None:
        """更新用户状态"""
        logger.info(f"更新用户状态：用户ID={user_id}, 状态={status}")
        
        # 更新Redis中的状态
        await self.redis.set(f"{USER_STATUS_KEY_PREFIX}{user_id}", status)
        
        # 根据状态管理在线用户集合
        if status == USER_STATUS_ONLINE:
            await self.redis.sadd(USER_ONLINE_SET_KEY, user_id)
        elif status == USER_STATUS_OFFLINE:
            await self.redis.srem(USER_ONLINE_SET_KEY, user_id)
        
        # 如果MongoDB可用，更新数据库
        if self.mongo is not None and self.mongo._db is not None:
            await self.mongo.update_user(user_id, {"status": status})

    async def set_user_online(self, user_id: str) -> None:
        """设置用户为在线状态"""
        await self.update_user_status(user_id, USER_STATUS_ONLINE)
        logger.info(f"用户 {user_id} 已上线")

    async def set_user_offline(self, user_id: str) -> None:
        """设置用户为离线状态"""
        await self.update_user_status(user_id, USER_STATUS_OFFLINE)
        logger.info(f"用户 {user_id} 已离线")

    async def set_user_in_room(self, user_id: str, room_id: str) -> None:
        """设置用户为在房间状态"""
        await self.update_user_status(user_id, USER_STATUS_IN_ROOM)
        logger.info(f"用户 {user_id} 已进入房间 {room_id}")

    async def set_user_playing(self, user_id: str) -> None:
        """设置用户为游戏中状态"""
        await self.update_user_status(user_id, USER_STATUS_PLAYING)
        logger.info(f"用户 {user_id} 已开始游戏")

    async def get_online_users(self) -> List[str]:
        """获取所有在线用户ID列表"""
        return await self.redis.smembers(USER_ONLINE_SET_KEY)

    async def is_user_online(self, user_id: str) -> bool:
        """检查用户是否在线"""
        return await self.redis.sismember(USER_ONLINE_SET_KEY, user_id)

    async def get_user_status(self, user_id: str) -> str:
        """获取用户状态"""
        status = await self.redis.get(f"{USER_STATUS_KEY_PREFIX}{user_id}")
        return status or USER_STATUS_OFFLINE

    async def update_user_room(self, user_id: str, room_id: Optional[str]) -> None:
        """更新用户当前所在房间"""
        # 更新Redis中的房间关系
        if room_id:
            await self.redis.set(f"user:current_room:{user_id}", room_id)
            await self.redis.add_user_to_room(user_id, room_id)
            # 更新用户状态为在房间
            await self.set_user_in_room(user_id, room_id)
        else:
            # 用户离开房间
            await self.redis.delete(f"user:current_room:{user_id}")
            # 更新用户状态为在线
            await self.set_user_online(user_id)
            
        # 如果MongoDB可用，更新数据库
        if self.mongo is not None and self.mongo._db is not None:
            await self.mongo.update_user(user_id, {"current_room_id": room_id})
