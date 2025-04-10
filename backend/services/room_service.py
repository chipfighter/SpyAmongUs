"""
房间管理服务
"""
import time
import asyncio
from typing import Dict, List, Optional, Set, Tuple
from models.room import Room, MIN_PLAYERS, MAX_PLAYERS, MIN_SPY_COUNT, MAX_SPY_RATIO
from utils.redis_utils import RedisClient
from utils.logger_utils import get_logger
import random
import string
from datetime import datetime
import uuid
from config import (
    GAME_STATUS_WAITING, GAME_STATUS_PLAYING, GAME_STATUS_FINISHED,
    GAME_PHASE_SPEAKING, GAME_PHASE_VOTING, GAME_PHASE_SECRET_CHAT, GAME_PHASE_LAST_WORDS,
    ROLE_SPY
)

logger = get_logger(__name__)

class RoomService:
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
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
                    
                    # 检查房间最后活动时间
                    last_active = room.last_active
                    if last_active:
                        try:
                            last_active_time = time.mktime(time.strptime(last_active, "%Y-%m-%dT%H:%M:%S.%f"))
                            inactive_time = current_time - last_active_time
                            if inactive_time > 900:  # 15分钟 = 900秒
                                logger.info(f"房间 {room_id} (名称: {room.name}) 已超过15分钟未活动，准备删除")
                                await self.delete_room(room_id)
                        except Exception as e:
                            logger.error(f"解析房间最后活动时间失败: {str(e)}")
            except asyncio.CancelledError:
                # 任务被取消
                logger.info("房间检查任务被取消")
                break
            except Exception as e:
                logger.error(f"检查非活动房间时出错: {str(e)}")
                
            # 每分钟检查一次
            await asyncio.sleep(60)

    async def create_room(self, name: str, host_id: str, is_public: bool = True,
                 total_players: int = MIN_PLAYERS, spy_count: int = MIN_SPY_COUNT, max_rounds: int = 3,
                 speak_time: int = 60, last_words_time: int = 30, llm_free: bool = False) -> Room:
        """创建新房间"""
        try:
            logger.info(f"开始创建房间: name={name}, host_id={host_id}, is_public={is_public}")
            
            # 验证输入
            if not name or not host_id:
                error_msg = "房间名称或主持人ID不能为空"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # 创建房间
            room = Room.create_room(
                name=name,
                host_id=host_id,
                is_public=is_public,
                total_players=total_players,
                spy_count=spy_count,
                max_rounds=max_rounds,
                speak_time=speak_time,
                last_words_time=last_words_time,
                llm_free=llm_free
            )
            
            # 获取房间数据字典
            room_data = room.dict()
            logger.info(f"房间数据准备完毕: {room_data}")
            
            # 存储到Redis
            await self.redis.save_room(room.id, room_data)
            logger.info(f"房间数据已保存到Redis: {room.id}")
            
            await self.redis.save_room_code(room.invite_code, room.id)
            logger.info(f"邀请码映射已保存: {room.invite_code} -> {room.id}")

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

            # 处理集合类型字段
            if "users" in room_data:
                if room_data["users"] == "[]" or not room_data["users"]:
                    room_data["users"] = set()
                else:
                    try:
                        # 尝试解析字符串形式的列表
                        if room_data["users"].startswith("[") and room_data["users"].endswith("]"):
                            import ast
                            users_list = ast.literal_eval(room_data["users"])
                            room_data["users"] = set(users_list)
                        else:
                            # 直接按逗号分隔
                            room_data["users"] = set(room_data["users"].split(","))
                    except Exception as e:
                        logger.error(f"解析users列表失败: {str(e)}, 使用空集合")
                        room_data["users"] = set()
            
            # 处理其他集合字段
            set_fields = ["ready_users", "alive_players"]
            for field in set_fields:
                if field in room_data:
                    if room_data[field] == "[]" or not room_data[field]:
                        room_data[field] = set()
                    else:
                        try:
                            if room_data[field].startswith("[") and room_data[field].endswith("]"):
                                import ast
                                field_list = ast.literal_eval(room_data[field])
                                room_data[field] = set(field_list)
                            else:
                                room_data[field] = set(room_data[field].split(","))
                        except Exception as e:
                            logger.error(f"解析{field}列表失败: {str(e)}, 使用空集合")
                            room_data[field] = set()
            
            # 处理布尔值
            bool_fields = ["is_public", "llm_free", "secret_chat_active"]
            for field in bool_fields:
                if field in room_data:
                    room_data[field] = room_data[field].lower() == "true"
            
            # 处理整数值
            int_fields = ["total_players", "spy_count", "max_rounds", "speak_time", 
                         "last_words_time", "current_round"]
            for field in int_fields:
                if field in room_data:
                    try:
                        room_data[field] = int(room_data[field])
                    except Exception:
                        # 使用默认值
                        if field == "total_players":
                            room_data[field] = MIN_PLAYERS
                        elif field == "spy_count":
                            room_data[field] = MIN_SPY_COUNT
                        elif field == "max_rounds":
                            room_data[field] = 3
                        elif field == "speak_time":
                            room_data[field] = 60
                        elif field == "last_words_time":
                            room_data[field] = 30
                        elif field == "current_round":
                            room_data[field] = 0
            
            # 处理字典类型
            dict_fields = ["words", "roles", "votes", "secret_chat_votes"]
            for field in dict_fields:
                if field in room_data and room_data[field]:
                    try:
                        if isinstance(room_data[field], str) and room_data[field].startswith("{") and room_data[field].endswith("}"):
                            import ast
                            room_data[field] = ast.literal_eval(room_data[field])
                    except Exception as e:
                        logger.error(f"解析{field}字典失败: {str(e)}, 使用空字典")
                        room_data[field] = {}
                elif field in room_data:
                    room_data[field] = {}
            
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

    async def get_public_rooms(self) -> List[Room]:
        """获取所有公开房间"""
        room_ids = await self.redis.get_public_rooms()
        rooms = []
        for room_id in room_ids:
            room = await self.get_room_by_id(room_id)
            if room:
                rooms.append(room)
        return rooms

    async def update_room(self, room: Room) -> bool:
        """更新房间信息"""
        try:
            room_data = room.dict()
            await self.redis.save_room(room.id, room_data)
            logger.info(f"房间 {room.id} 信息已更新")
            return True
        except Exception as e:
            logger.error(f"更新房间 {room.id} 失败: {str(e)}")
            return False

    async def add_user_to_room(self, room_id: str, user_id: str) -> Optional[Room]:
        """添加用户到房间"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.warning(f"找不到房间: {room_id}")
            return None
            
        # 检查房间状态
        if room.status != GAME_STATUS_WAITING:
            logger.warning(f"房间 {room_id} 游戏已开始，不能加入")
            return None
            
        # 检查房间人数
        if len(room.users) >= room.total_players:
            logger.warning(f"房间 {room_id} 已满员，不能加入")
            return None
            
        # 添加用户到房间
        room.add_user(user_id)
        
        # 保存更新
        success = await self.update_room(room)
        if success:
            # 更新Redis中的房间-用户关系
            await self.redis.add_user_to_room(user_id, room_id)
            return room
        return None
        
    async def remove_user_from_room(self, room_id: str, user_id: str) -> Optional[Room]:
        """将用户从房间移除"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.warning(f"找不到房间: {room_id}")
            return None
            
        # 从房间移除用户
        room.remove_user(user_id)
        
        # 如果是房主离开，需要更换房主
        if user_id == room.host_id and room.users:
            # 从房间剩余用户中选择一位作为新房主
            new_host_id = next(iter(room.users))
            room.host_id = new_host_id
            logger.info(f"房间 {room_id} 的房主已更改为: {new_host_id}")
            
        # 如果房间没有用户，删除房间
        if not room.users:
            logger.info(f"房间 {room_id} 已没有用户，将被删除")
            await self.delete_room(room_id)
            return None
            
        # 保存更新
        success = await self.update_room(room)
        if success:
            # 更新Redis中的房间-用户关系
            await self.redis.remove_user_from_room(user_id, room_id)
            return room
        return None

    async def toggle_user_ready(self, room_id: str, user_id: str) -> Tuple[bool, Optional[Room]]:
        """切换用户准备状态"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.warning(f"找不到房间: {room_id}")
            return False, None
            
        # 切换准备状态
        ready = room.toggle_user_ready(user_id)
        
        # 保存更新
        success = await self.update_room(room)
        if success:
            return ready, room
        return False, None
        
    async def start_game(self, room_id: str) -> Optional[Room]:
        """开始游戏"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.warning(f"找不到房间: {room_id}")
            return None
            
        # 检查房间状态
        if room.status != GAME_STATUS_WAITING:
            logger.warning(f"房间 {room_id} 不是等待状态，无法开始游戏")
            return None
            
        # 检查房间人数
        if len(room.users) < MIN_PLAYERS:
            logger.warning(f"房间 {room_id} 人数不足，至少需要{MIN_PLAYERS}人")
            return None
            
        # 检查是否所有玩家都已准备
        if not room.is_all_ready():
            logger.warning(f"房间 {room_id} 有玩家未准备")
            return None
            
        # 开始游戏
        room.start_game()
        
        # 保存更新
        success = await self.update_room(room)
        if success:
            return room
        return None
        
    async def set_game_words(self, room_id: str, civilian_word: str, spy_word: str) -> Optional[Room]:
        """设置游戏词语"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.warning(f"找不到房间: {room_id}")
            return None
            
        # 设置词语
        room.set_words(civilian_word, spy_word)
        
        # 保存更新
        success = await self.update_room(room)
        if success:
            return room
        return None
        
    async def assign_roles(self, room_id: str, roles: Dict[str, str]) -> Optional[Room]:
        """分配角色"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.warning(f"找不到房间: {room_id}")
            return None
            
        # 分配角色
        room.assign_roles(roles)
        
        # 保存更新
        success = await self.update_room(room)
        if success:
            return room
        return None
        
    async def record_vote(self, room_id: str, round_num: int, voter_id: str, 
                         target_id: str, vote_speed: float = 0.0) -> Optional[Room]:
        """记录投票"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.warning(f"找不到房间: {room_id}")
            return None
            
        # 检查是否为投票阶段
        if room.current_phase != GAME_PHASE_VOTING:
            logger.warning(f"房间 {room_id} 不是投票阶段")
            return None
            
        # 检查投票者是否存活
        if voter_id not in room.alive_players:
            logger.warning(f"玩家 {voter_id} 已被淘汰，不能投票")
            return None
            
        # 检查目标是否存活
        if target_id not in room.alive_players:
            logger.warning(f"玩家 {target_id} 已被淘汰，不能被投票")
            return None
            
        # 记录投票
        room.record_vote(round_num, voter_id, target_id, vote_speed)
        
        # 保存更新
        success = await self.update_room(room)
        if success:
            return room
        return None
        
    async def process_vote_results(self, room_id: str) -> Optional[Dict]:
        """处理投票结果"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.warning(f"找不到房间: {room_id}")
            return None
            
        # 统计当前轮的投票结果
        vote_counts = room.count_votes(room.current_round)
        if not vote_counts:
            logger.warning(f"房间 {room_id} 轮次 {room.current_round} 没有投票记录")
            return {"status": "no_votes"}
            
        # 找出得票最多的玩家
        max_votes = 0
        eliminated_players = []
        for player_id, count in vote_counts.items():
            if count > max_votes:
                max_votes = count
                eliminated_players = [player_id]
            elif count == max_votes:
                eliminated_players.append(player_id)
                
        # 判断是否平票
        if len(eliminated_players) > 1:
            logger.info(f"房间 {room_id} 轮次 {room.current_round} 投票平局: {eliminated_players}")
            return {
                "status": "tie",
                "tied_players": eliminated_players
            }
            
        # 淘汰玩家
        eliminated_player = eliminated_players[0]
        room.eliminate_player(eliminated_player)
        
        # 获取被淘汰玩家的角色
        eliminated_role = room.roles.get(eliminated_player, "unknown")
        
        # 检查游戏是否结束
        game_over, winner = room.is_game_over()
        
        # 如果游戏未结束，进入下一轮
        if not game_over:
            room.current_round += 1
            room.current_phase = GAME_PHASE_SPEAKING
            
        # 如果游戏结束，更新状态
        else:
            room.status = GAME_STATUS_FINISHED
            room.current_phase = ""
            
        # 保存更新
        success = await self.update_room(room)
        if success:
            return {
                "status": "eliminated",
                "eliminated_player": eliminated_player,
                "role": eliminated_role,
                "game_over": game_over,
                "winner": winner if game_over else None
            }
        return None
        
    async def vote_secret_chat(self, room_id: str, spy_id: str, vote: bool) -> Optional[Dict]:
        """卧底投票开启秘密聊天室"""
        room = await self.get_room_by_id(room_id)
        if not room:
            logger.warning(f"找不到房间: {room_id}")
            return None
            
        # 检查玩家角色是否为卧底
        if room.roles.get(spy_id) != ROLE_SPY:
            logger.warning(f"玩家 {spy_id} 不是卧底，不能参与秘密聊天室投票")
            return None
            
        # 投票并获取结果
        is_active, agree_count, required_votes = room.vote_secret_chat(spy_id, vote)
        
        # 保存更新
        success = await self.update_room(room)
        if success:
            return {
                "is_active": is_active,
                "agree_count": agree_count,
                "required_votes": required_votes
            }
        return None