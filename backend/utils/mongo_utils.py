"""
MongoDB工具类

Notes:
    类似持久层，提供service函数接口，系统仅有一种需要保存的持久数据（用户数据）。
    - 关于MongoDB 连接、断开、检查
    - 增加新用户
    - 根据用户id删除用户
    - 更新用户名、更新用户密码、更新用户状态
    - 根据id来查找用户所有信息

To-Do:
    - 修改用户的战绩以及画像
"""
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from utils.logger_utils import get_logger
from config import MONGO_URI, MONGO_DB
import time

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

    async def create_user(self, user_data):
        """创建新用户（接收user_service传来的一个完整用户字典）"""
        if self._db is None:
            return False

        try:
            # 确保用户数据包含必要字段
            required_fields = ["id", "username", "password_hash", "salt"]
            for field in required_fields:
                if field not in user_data:
                    logger.error(f"创建用户缺少必要字段: {field}")
                    return False

            current_time = int(time.time() * 1000)
            if "status" not in user_data:
                user_data["status"] = "online"
            if "last_active" not in user_data:
                user_data["last_active"] = current_time
            if "current_room" not in user_data:
                user_data["current_room"] = None

            # 初始化用户统计和画像数据
            if "statistics" not in user_data:
                user_data["statistics"] = {
                    "total_games": 0,
                    "win_rates": {
                        "civilian": 0.0,
                        "spy": 0.0
                    }
                }

            if "style_profile" not in user_data:
                user_data["style_profile"] = {
                    "summary": "",
                    "tags": [],
                    "vectors": {}
                }

            result = await self._db.users.insert_one(user_data)
            if result.inserted_id:
                logger.info(f"成功创建用户: {user_data['username']} (ID: {user_data['id']})")
                return True
            return False
        except Exception as e:
            logger.error(f"创建用户时出错: {str(e)}")
            return False

    async def delete_user(self, user_id):
        """根据用户id来删除用户"""
        if self._db is None:
            return False

        try:
            result = await self._db.users.delete_one({"id": user_id})
            if result.deleted_count > 0:
                logger.info(f"成功删除用户 {user_id}")
                return True
            else:
                logger.warning(f"未找到用户 {user_id}，无法删除")
                return False
        except Exception as e:
            logger.error(f"删除用户时出错: {str(e)}")
            return False

    async def update_username(self, user_id, new_username):
        """更新用户名"""
        if self._db is None:
            return False

        try:
            # 先检查新用户名是否已存在
            existing_user = await self.find_user_by_username(new_username)
            if existing_user and existing_user["id"] != user_id:
                logger.warning(f"用户名 {new_username} 已被使用")
                return False, "用户名已存在"

            # 更新用户名
            result = await self._db.users.update_one(
                {"id": user_id},
                {"$set": {"username": new_username}}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"用户 {user_id} 的用户名已更新为 {new_username}")
                return True, "更新成功"
            else:
                logger.warning(f"未找到用户 {user_id}，无法更新用户名")
                return False, "用户不存在"

        except Exception as e:
            logger.error(f"更新用户名时出错: {str(e)}")
            return False, f"更新失败: {str(e)}"

    async def update_password(self, user_id, password_hash, salt):
        """更新用户密码"""
        if self._db is None:
            return False

        try:
            result = await self._db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "password_hash": password_hash,
                    "salt": salt
                }}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"用户 {user_id} 的密码已更新")
                return True, "密码已更新"
            else:
                logger.warning(f"未找到用户 {user_id}，无法更新密码")
                return False, "用户不存在"

        except Exception as e:
            logger.error(f"更新密码时出错: {str(e)}")
            return False, f"更新失败: {str(e)}"

    async def update_user_status(self, user_id: str, status: str) -> tuple:
        """仅更新用户状态"""
        if self._db is None:
            return False, "MongoDB连接不可用"

        try:
            result = await self._db.users.update_one(
                {"id": user_id},
                {"$set": {"status": status}}
            )

            if result.matched_count == 0:
                logger.warning(f"未找到用户 {user_id}，无法更新状态")
                return False, "用户不存在"

            if result.modified_count > 0:
                logger.info(f"用户 {user_id} 状态已更新为 {status}")
                return True, "状态已更新"
            else:
                logger.info(f"用户 {user_id} 状态未变化，仍为 {status}")
                return True, "状态未变化"

        except Exception as e:
            error_msg = f"更新用户状态时出错: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def find_user(self, user_id):
        """通过ID查找用户"""
        if self._db is None:
            return None

        try:
            user = await self._db.users.find_one({"id": user_id})
            return user
        except Exception as e:
            logger.error(f"通过ID查找用户时出错: {str(e)}")
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

    async def check_connection_status(self) -> dict[str, Any]:
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