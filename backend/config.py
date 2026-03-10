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
# 轮询状态相关
ROOM_POLL_STATE_KEY_PREFIX = "room:%s:poll_state"  # String| 轮询上帝状态的JSON
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
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-unsafe-key")
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

# 游戏阶段
GAME_PHASE_SPEAKING = "speaking"
GAME_PHASE_VOTING = "voting"
GAME_PHASE_LAST_WORDS = "last_words"
GAME_PHASE_SECRET_CHAT = "secret_chat"

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

# LLM调用场景常量
LLM_CONTEXT_NORMAL_CHAT = "normal_chat"         # 未开始游戏时的普通聊天@AI
LLM_CONTEXT_GAME_PLAYING = "game_playing"       # 游戏中轮到AI玩家发言
LLM_CONTEXT_SECRET_VOTE = "secret_vote"         # 游戏中秘密聊天室投票
LLM_CONTEXT_SECRET_CHAT = "secret_chat"         # 游戏中秘密聊天室聊天
LLM_CONTEXT_VOTING = "voting"                   # 游戏中普通投票场景
LLM_CONTEXT_LAST_WORDS = "last_words"           # 游戏中玩家被淘汰后的遗言
LLM_CONTEXT_GOD_WORDS = "god_words"             # 上帝分发词语

# 投票相关
VOTE_TIMEOUT = 10  # 投票超时时间（秒）
VOTE_SERVER_TIMEOUT = 11.5  # 服务器投票超时时间（秒）