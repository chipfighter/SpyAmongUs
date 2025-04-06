"""
MongoDB工具类

Description:
    类似持久层，提供service函数接口，系统仅有一种需要保存的持久数据（用户数据）。
    该类封装了与MongoDB的异步操作，提供了连接、断开、查询、插入、更新和删除等功能。

Methods:
    connect: 连接到MongoDB数据库。
    disconnect: 断开MongoDB数据库连接。
    find_user: 根据用户ID查找用户信息。
    find_user_by_username: 根据用户名查找用户信息。
    create_user: 创建新用户。
    update_user: 更新用户信息。
    delete_user: 删除用户。
    check_connection_status: 检查MongoDB连接状态并返回诊断信息。
"""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from utils.logger_utils import get_logger
from config import MONGO_URI, MONGO_DB

logger = get_logger(__name__)

class MongoClient:
    def __init__(self):
        self._client = None
        self._db = None

    async def connect(self):
        """连接MongoDB"""
        try:
            self._client = AsyncIOMotorClient(MONGO_URI)    # 初始化MongoDB连接
            self._db = self._client[MONGO_DB]   # 初始化db配置
            
            # 使用ping测试连接
            await self._client.admin.command('ping')
            logger.info(f"成功连接到MongoDB: {MONGO_URI}")
            return True
        except ConnectionFailure as e:
            logger.error(f"无法连接到MongoDB: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"MongoDB连接错误: {str(e)}")
            return False

    async def disconnect(self):
        """断开MongoDB连接"""
        if self._client:
            self._client.close()
            logger.info("MongoDB连接已关闭")

    async def find_user(self, user_id):
        """通过ID查找用户"""
        if self._db is None:
            return None
        
        try:
            user = await self._db.users.find_one({"id": user_id})
            return user
        except Exception as e:
            logger.error(f"查找用户时出错: {str(e)}")
            return None

    async def find_user_by_username(self, username):
        """通过用户名查找用户"""
        if self._db is None:
            logger.error("MongoDB连接不可用，无法查找用户")
            return None
        
        try:
            user = await self._db.users.find_one({"username": username})
            return user
        except Exception as e:
            logger.error(f"通过用户名查找用户时出错: {str(e)}")
            return None

    async def create_user(self, user_data):
        """创建新用户（接收user_service传来的一个完整用户字典）"""
        if self._db is None:
            return None
        
        try:
            result = await self._db.users.insert_one(user_data)
            if result.inserted_id:
                return True
            return False
        except Exception as e:
            logger.error(f"创建用户时出错: {str(e)}")
            return False

    async def update_user(self, user_id, update_data):
        """更新用户信息（直接覆写）"""
        if self._db is None:
            return False
        
        try:
            result = await self._db.users.update_one(
                {"id": user_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"更新用户时出错: {str(e)}")
            return False

    async def delete_user(self, user_id):
        """根据用户id来删除用户"""
        if self._db is None:
            return False
        
        try:
            result = await self._db.users.delete_one({"id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"删除用户时出错: {str(e)}")
            return False

    async def check_connection_status(self):
        """检查MongoDB连接状态并返回诊断信息"""
        result = {
            "connected": False,
            "client_initialized": self._client is not None,
            "db_initialized": self._db is not None,
            "uri": MONGO_URI,
            "db_name": MONGO_DB,
            "error": None
        }
        
        try:
            if self._client is None:
                result["error"] = "MongoDB客户端未初始化"
                return result
                
            if self._db is None:
                result["error"] = "数据库对象未初始化"
                return result
                
            # 尝试ping测试
            await self._client.admin.command('ping')
            result["connected"] = True
            
            # 检查users集合是否存在
            collections = await self._db.list_collection_names()
            result["collections"] = collections
            result["users_collection_exists"] = "users" in collections
            
            # 尝试计数用户数量
            user_count = await self._db.users.count_documents({})
            result["user_count"] = user_count
            
            logger.info(f"MongoDB连接状态: {result}")
            return result
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"检查MongoDB连接时出错: {str(e)}")
            return result 