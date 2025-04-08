"""
配置文件
"""
import os
from dotenv import load_dotenv


# 加载环境变量
load_dotenv()

# Redis配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Redis键前缀（房间相关）
ROOM_KEY_PREFIX = "room:"   # Hash| room:{room_id} -> hash{所有房间属性}
PUBLIC_ROOMS_KEY = "public_rooms"   # Set| 公共房间ID集合（快速查找当前公共房间）
ROOM_CODE_KEY_PREFIX = "room:by_code:"      # String| 邀请码->房间ID的集合（用于快速反向查找）
ROOM_MESSAGES_KEY_PREFIX = "room:messages:"     # List| 房间消息列表，使用列表类型存储，room:messages:{room_id} -> list[Message]
ROOM_USERS_KEY_PREFIX = "room:users:"       # Set| 房间用户id集合，room:users:{room_id} -> set[user_id]
# Redis键前缀（用户相关）
USER_ONLINE_SET_KEY = "users:online"    # Set| 所有在线用户的ID集合（用于快速查询谁在线）
USER_STATUS_KEY_PREFIX = "user:status:" # String| 用户状态，user:status:{user_id} -> string{"online"|"offline"|"in_room"|"playing"}
USER_CURRENT_ROOM_KEY_PREFIX = "user:current_room:" # String| 用户当前所在房间，user:current_room:{user_id} -> string{room_id}
USER_INFO_KEY_PREFIX = "user:info:"    # Hash| 用户基本信息缓存（仅仅在进入房间的时候记录），user:info:{user_id} -> hash{username, avatar...}

# MongoDB配置
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "spy_among_us")

# 应用配置
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# 用户状态常量
USER_STATUS_OFFLINE = "offline"
USER_STATUS_ONLINE = "online"
USER_STATUS_IN_ROOM = "in_room"
USER_STATUS_PLAYING = "playing"

