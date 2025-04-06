"""
房间管理服务
"""
import time
import asyncio
from typing import Dict, List, Optional, Set
from models.room import Room
from utils.redis_utils import RedisClient
from utils.logger_utils import get_logger

logger = get_logger(__name__)

class RoomService:
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        # 存储用户WebSocket连接
        self.user_connections: Dict[str, any] = {}
        # 后台任务
        self.background_tasks = []

    async def start_background_tasks(self):
        """启动后台任务"""
        # 检查非活动房间任务
        inactive_rooms_task = asyncio.create_task(self._check_inactive_rooms())
        self.background_tasks.append(inactive_rooms_task)
        logger.info("后台房间清理任务已启动")

    async def stop_background_tasks(self):
        """停止所有后台任务"""
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        self.background_tasks = []
        logger.info("后台任务已停止")

    async def _check_inactive_rooms(self):
        """检查非活动房间并清理"""
        while True:
            try:
                # 获取所有公开房间ID
                public_room_ids = await self.redis.get_public_rooms()
                current_time = time.time()
                logger.debug(f"开始检查非活动房间，当前公开房间数: {len(public_room_ids)}")
                
                for room_id in public_room_ids:
                    room = await self.get_room_by_id(room_id)
                    if not room:
                        continue
                    
                    # 检查房间状态和计时器
                    if room.room_status == "waiting":
                        # 计算房间处于waiting状态的时间
                        waiting_time = current_time - room.timer
                        if waiting_time > 900:  # 15分钟 = 900秒
                            logger.info(f"房间 {room_id} (名称: {room.name}) 处于waiting状态超过15分钟 ({waiting_time:.1f}秒)，准备删除")
                            await self.delete_room(room_id)
                        elif waiting_time > 600:  # 10分钟 = 600秒 
                            # 提前记录日志但不删除
                            logger.debug(f"房间 {room_id} (名称: {room.name}) 处于waiting状态接近超时 ({waiting_time:.1f}秒)")
            except asyncio.CancelledError:
                # 任务被取消
                logger.info("房间检查任务被取消")
                break
            except Exception as e:
                logger.error(f"检查非活动房间时出错: {str(e)}")
                
            # 每分钟检查一次
            await asyncio.sleep(60)

    async def create_room(self, name: str, host_id: str, is_public: bool = True) -> Room:
        """创建新房间"""
        try:
            logger.info(f"开始创建房间: name={name}, host_id={host_id}, is_public={is_public}")
            
            # 验证输入
            if not name or not host_id:
                error_msg = "房间名称或主持人ID不能为空"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # 房间初始化
            room = Room.create_room(name, host_id, is_public)
            # 设置创建时间为当前时间
            room.timer = time.time()
            logger.info(f"房间对象创建成功: id={room.id}, invitation_code={room.invitation_code}")
            
            # 获取房间数据字典
            room_data = room.dict()
            logger.info(f"房间数据准备完毕: {room_data}")
            
            # 存储到Redis
            await self.redis.save_room(room.id, room_data)
            logger.info(f"房间数据已保存到Redis: {room.id}")
            
            await self.redis.save_room_code(room.invitation_code, room.id)
            logger.info(f"邀请码映射已保存: {room.invitation_code} -> {room.id}")

            # 如果是公开房间，添加到公开房间列表
            if is_public:
                await self.redis.add_to_public_rooms(room.id)
                logger.info(f"房间已添加到公开列表: {room.id}")

            return room
        except Exception as e:
            error_msg = f"创建房间失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def get_room_by_id(self, room_id: str) -> Optional[Room]:
        """通过ID获取房间"""
        try:
            room_data = await self.redis.get_room(room_id)
            if not room_data:
                logger.info(f"找不到房间: {room_id}")
                return None

            # 处理集合类型字段（users、leaving_in_game_users、ready_users）
            set_fields = ["users", "leaving_in_game_users", "ready_users"]
            for field in set_fields:
                if field in room_data:
                    if room_data[field] == "[]" or not room_data[field]:
                        room_data[field] = set()
                    else:
                        try:
                            # 尝试解析字符串形式的列表
                            if room_data[field].startswith("[") and room_data[field].endswith("]"):
                                import ast
                                users_list = ast.literal_eval(room_data[field])
                                room_data[field] = set(users_list)
                            else:
                                # 直接按逗号分隔
                                room_data[field] = set(room_data[field].split(","))
                        except Exception as e:
                            logger.error(f"解析{field}列表失败: {str(e)}, 使用空集合")
                            room_data[field] = set()
            
            # 处理布尔值
            if "is_public" in room_data:
                room_data["is_public"] = room_data["is_public"].lower() == "true"
            
            # 处理数值型字段
            if "timer" in room_data:
                try:
                    room_data["timer"] = float(room_data["timer"])
                except:
                    room_data["timer"] = time.time()  # 如果转换失败，使用当前时间
                
            logger.info(f"获取到房间信息: {room_id}")
            return Room.parse_obj(room_data)
        except Exception as e:
            logger.error(f"获取房间时出错 {room_id}: {str(e)}")
            raise

    async def get_room_by_code(self, invitation_code: str) -> Optional[Room]:
        """通过邀请码获取房间"""
        room_id = await self.redis.get_room_by_code(invitation_code)
        if not room_id:
            return None
        return await self.get_room_by_id(room_id)

    async def update_room_status(self, room_id: str, status: str) -> bool:
        """更新房间状态"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.error(f"更新房间状态失败: 找不到房间 {room_id}")
            return False
            
        old_status = room.room_status
        room.room_status = status
        
        # 如果状态发生变化，更新计时器
        if old_status != status:
            room.timer = time.time()
            logger.info(f"房间 {room_id} 状态从 {old_status} 变为 {status}，重置计时器")
        
        # 保存更新后的房间数据
        room_data = room.dict()
        await self.redis.save_room(room.id, room_data)
        
        return True

    async def delete_room(self, room_id: str) -> bool:
        """删除房间，同时清理相关资源"""
        try:
            # 获取房间信息，用于日志记录
            room = await self.get_room_by_id(room_id)
            if room:
                logger.info(f"正在删除房间: {room_id}, 名称: {room.name}, 房主: {room.host_id}")
                
                # 对房间中的每个用户，清除他们的当前房间关系
                for user_id in room.users:
                    await self.redis.remove_user_from_room(user_id, room_id)
                    logger.debug(f"已清除用户 {user_id} 与房间 {room_id} 的关联")
            
            # 删除房间所有数据
            await self.redis.delete_room(room_id)
            logger.info(f"房间 {room_id} 及其关联数据已完全删除")
            return True
        except Exception as e:
            logger.error(f"删除房间 {room_id} 失败: {str(e)}")
            return False

    async def add_user_to_room(self, room_id: str, user_id: str, username: str) -> bool:
        """添加用户到房间"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.error(f"添加用户到房间失败: 找不到房间 {room_id}")
            return False

        # 检查用户是否已经在其他房间
        current_room_id = await self.redis.get_user_current_room(user_id)
        if current_room_id and current_room_id != room_id:
            # 先从之前的房间移除
            logger.info(f"用户 {user_id} 已在房间 {current_room_id}，先移除")
            await self.remove_user_from_room(current_room_id, user_id)

        # 更新房间用户列表
        room.users.add(user_id)
        room_data = room.dict()

        # 保存更新后的房间数据
        await self.redis.save_room(room.id, room_data)
        logger.info(f"用户 {user_id} 已添加到房间 {room_id}")

        # 更新用户-房间关系
        await self.redis.add_user_to_room(user_id, room_id)

        return True

    async def remove_user_from_room(self, room_id: str, user_id: str) -> bool:
        """从房间移除用户"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.error(f"从房间移除用户失败: 找不到房间 {room_id}")
            return False

        # 更新房间用户列表
        room.users.discard(user_id)
        room_data = room.dict()

        # 保存更新后的房间数据
        await self.redis.save_room(room.id, room_data)
        logger.info(f"用户 {user_id} 已从房间 {room_id} 移除")

        # 更新用户-房间关系
        await self.redis.remove_user_from_room(user_id, room_id)

        # 如果房间空了，考虑删除房间
        if not room.users:
            logger.info(f"房间 {room_id} 已空，准备清理")
            if room.is_public:
                await self.redis.remove_from_public_rooms(room_id)
                logger.info(f"房间已从公开列表中移除: {room_id}")
            
            # 可选：完全删除房间
            # await self.delete_room(room_id)
            # logger.info(f"空房间已删除: {room_id}")

        return True

    async def get_user_current_room(self, user_id: str) -> Optional[Room]:
        """获取用户当前所在的房间"""
        room_id = await self.redis.get_user_current_room(user_id)
        if not room_id:
            return None
        return await self.get_room_by_id(room_id)

    async def get_room_users(self, room_id: str) -> Set[str]:
        """获取房间中的所有用户ID"""
        room = await self.get_room_by_id(room_id)
        if not room:
            return set()
        return room.users

    async def get_public_rooms(self) -> List[Room]:
        """获取所有公开房间"""
        room_ids = await self.redis.get_public_rooms()
        rooms = []
        for room_id in room_ids:
            room = await self.get_room_by_id(room_id)
            if room:
                rooms.append(room)
        return rooms

    def register_user_websocket(self, user_id: str, websocket: any) -> None:
        """注册用户WebSocket连接"""
        self.user_connections[user_id] = websocket

    def unregister_user_websocket(self, user_id: str) -> None:
        """取消注册用户WebSocket连接"""
        if user_id in self.user_connections:
            del self.user_connections[user_id]

    def get_user_websocket(self, user_id: str) -> Optional[any]:
        """获取用户的WebSocket连接"""
        return self.user_connections.get(user_id)