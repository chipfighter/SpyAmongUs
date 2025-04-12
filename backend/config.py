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

# Redis键前缀（用户相关）
USER_KEY_PREFIX = "user:"  # Hash| 用户数据主键，user:{user_id} -> hash{所有用户信息}
# Redis键前缀（房间相关）
ROOM_KEY_PREFIX = "room:"  # Hash| 房间主键，room:{invite_code} -> hash{所有房间基本属性}
PUBLIC_ROOMS_KEY = "public_rooms"  # Set| 公共房间邀请码集合
# 房间用户相关
ROOM_USERS_KEY_PREFIX = "room:%s:users"  # Set| 房间用户id集合
ROOM_READY_USERS_KEY_PREFIX = "room:%s:ready_users"  # Set| 准备用户id集合
ROOM_ALIVE_PLAYERS_KEY_PREFIX = "room:%s:alive_players"  # Set| 存活玩家id集合
ROOM_ROLES_KEY_PREFIX = "room:%s:roles"  # Hash| 用户角色映射，{user_id: role}
# 房间消息相关
ROOM_MESSAGES_KEY_PREFIX = "room:%s:messages"  # List| 房间消息列表
ROOM_SECRET_CHAT_MESSAGES_KEY_PREFIX = "room:%s:secret_chat:messages"  # List| 秘密聊天消息
# 投票相关
ROOM_VOTES_KEY_PREFIX = "room:%s:votes:%s"  # Hash| 投票记录，%s分别是invite_code和round
ROOM_SECRET_VOTES_KEY_PREFIX = "room:%s:secret_votes:%s"  # Hash| 秘密聊天投票

# MongoDB配置
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DBNAME = os.getenv("MONGODB_DBNAME", "spy_among_us")

# 应用配置
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", 8000))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# JWT配置
JWT_SECRET_KEY = "Kj8#mP9$vL2@nX5&hQ7*wR4!tY6^cB3%fD1?gE9#iA2$jM5@kS7&lN4*wT6!xU8^yV3%zW1?bH9#"
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 25  # 与Redis TTL保持一致
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7     # 刷新令牌有效期7天

# 用户状态常量
USER_STATUS_ONLINE = "online"
USER_STATUS_IN_ROOM = "in_room"
USER_STATUS_PLAYING = "playing"

# 房间状态相关
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