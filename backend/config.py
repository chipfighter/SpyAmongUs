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
USER_STATUS_KEY_PREFIX = "user:status:" # String| 用户状态，user:status:{user_id} -> string{"online"|"in_room"|"playing"}
USER_CURRENT_ROOM_KEY_PREFIX = "user:current_room:" # String| 用户当前所在房间，user:current_room:{user_id} -> string{room_id}
USER_INFO_KEY_PREFIX = "user:info:"    # Hash| 用户基本信息缓存（登录时记录），user:info:{user_id} -> hash{username, avatar...}
USER_LAST_ACTIVE_KEY_PREFIX = "user:last_active:" # String| 用户最后活跃时间，user:last_active:{user_id} -> timestamp
USER_STYLE_KEY_PREFIX = "user:style:"  # Hash| 用户风格画像缓存
USER_STATISTICS_KEY_PREFIX = "user:statistics:"  # Hash| 用户统计信息缓存

# MongoDB配置
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "spy_among_us")

# 应用配置
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# 用户状态常量
USER_STATUS_ONLINE = "online"
USER_STATUS_IN_ROOM = "in_room"
USER_STATUS_PLAYING = "playing"

# 用户活动检查配置
USER_ACTIVITY_CHECK_INTERVAL = 30  # 秒
USER_POSSIBLY_INACTIVE_THRESHOLD = 60  # 秒
USER_INACTIVE_CLEANUP_THRESHOLD = 300  # 秒

# 游戏相关常量
GAME_STATUS_WAITING = "waiting"
GAME_STATUS_PLAYING = "playing"

GAME_PHASE_SPEAKING = "speaking"
GAME_PHASE_VOTING = "voting"
GAME_PHASE_SECRET_CHAT = "secret_chat"
GAME_PHASE_LAST_WORDS = "last_words"

ROLE_CIVILIAN = "civilian"
ROLE_SPY = "spy"
ROLE_GOD = "god"

# 默认游戏参数
MIN_PLAYERS = 3
MAX_PLAYERS = 8
MIN_SPY_COUNT = 1
MAX_SPY_RATIO = 0.4
MAX_ROUNDS = 10
MAX_SPEAK_TIME = 60
MAX_LAST_WORDS_TIME = 60