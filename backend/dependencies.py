"""
服务依赖管理模块

集中初始化和管理所有服务实例，供 routers 模块导入使用。
将 main.py 中的服务初始化逻辑抽取到此处，解决 routers 与 main 之间的循环导入问题。
"""

from llm.llm_pipeline import llm_pipeline
from services.room_service import RoomService
from services.user_service import UserService
from services.auth_service import AuthService
from services.feedback_service import FeedbackService
from utils.redis_utils import RedisClient
from utils.mongo_utils import MongoClient
from utils.websocket_manager import WebSocketManager
from services.message_service import MessageService


# 初始化基础客户端
redis_client = RedisClient()
mongo_client = MongoClient()

# 初始化服务
user_service = UserService(redis_client, mongo_client)
websocket_manager = WebSocketManager()
message_service = MessageService(redis_client, websocket_manager, llm_pipeline)
room_service = RoomService(user_service, redis_client, websocket_manager)
auth_service = AuthService()
feedback_service = FeedbackService(mongo_client)

# 设置服务之间的依赖关系
room_service.set_message_service(message_service)
game_service = room_service.game_service
message_service.set_game_service(game_service)
game_service.set_message_service(message_service)
game_service.set_llm_pipeline(llm_pipeline)
