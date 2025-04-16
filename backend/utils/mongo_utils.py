"""
MongoDB工具类

Methods:
    - Python的list和Mongodb中的set的互相转化
    - 关于MongoDB的连接、断开、检查连接
    用户相关：
        - 创建用户
        - 删除用户
        - 更新用户名、更新用户密码、更新用户头像
        - 根据id查找用户信息、根据用户名查找用户信息

TODO:
    1.修改用户的战绩
    2.修改用户画像
"""

from typing import Dict, Optional, Any, List, Union
from motor.motor_asyncio import AsyncIOMotorClient
from utils.logger_utils import get_logger
from config import MONGODB_URL, MONGODB_DBNAME

logger = get_logger(__name__)

class MongoClient:
    def __init__(self):
        """初始化MongoDB客户端"""
        try:
            self.client = AsyncIOMotorClient(MONGODB_URL)
            self.db = self.client[MONGODB_DBNAME]
            logger.info("MongoDB客户端初始化成功")
        except Exception as e:
            logger.error(f"MongoDB客户端初始化失败: {str(e)}")
            raise

    def _convert_sets_to_lists(self, data: Union[Dict, list, set, Any]) -> Union[Dict, list, Any]:
        """
        递归地将字典中的set类型转换为list类型
        
        Args:
            data: 需要转换的数据
            
        Returns:
            转换后的数据
        """
        if isinstance(data, dict):
            return {k: self._convert_sets_to_lists(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [self._convert_sets_to_lists(item) for item in data]
        elif isinstance(data, set):
            return list(data)
        return data

    def _convert_lists_to_sets(self, data: Union[Dict, list, Any]) -> Union[Dict, list, set, Any]:
        """
        递归地将字典中的特定list类型转换回set类型
        
        Args:
            data: 需要转换的数据
            
        Returns:
            转换后的数据
        """
        if isinstance(data, dict):
            # 如果是style_profile中的tags字段，将list转换为set
            if "style_profile" in data and "tags" in data["style_profile"]:
                data["style_profile"]["tags"] = set(data["style_profile"]["tags"])
            return {k: self._convert_lists_to_sets(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_lists_to_sets(item) for item in data]
        return data

    async def create_user(self, user_data: Dict[str, Any]) -> bool:
        """
        创建新用户
        
        Args:
            user_data: 用户数据字典
            
        Returns:
            bool: 是否创建成功
        """
        try:
            # 转换set类型为list类型
            mongo_data = self._convert_sets_to_lists(user_data)
            result = await self.db.users.insert_one(mongo_data)
            return bool(result.inserted_id)
        except Exception as e:
            logger.error(f"创建用户失败: {str(e)}")
            return False

    async def delete_user(self, user_id):
        """
        根据用户id来删除用户

        Notes:
            注意这里的删除是将用户注销！
        """
        if self.db is None:
            return False

        try:
            result = await self.db.users.delete_one({"id": user_id})
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
        if self.db is None:
            return False, "MongoDB连接不可用"

        try:
            # 先检查新用户名是否已存在
            existing_user = await self.find_user_by_username(new_username)
            if existing_user and existing_user["id"] != user_id:
                logger.warning(f"用户名 {new_username} 已被使用")
                return False, "用户名已存在"

            # 更新用户名
            result = await self.db.users.update_one(
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
        if self.db is None:
            return False

        try:
            result = await self.db.users.update_one(
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

    async def update_avatar(self, user_id: str, avatar_url: str) -> tuple:
        """更新用户头像"""
        if self.db is None:
            return False, "MongoDB连接不可用"

        try:
            result = await self.db.users.update_one(
                {"id": user_id},
                {"$set": {"avatar_url": avatar_url}}
            )

            if result.matched_count == 0:
                logger.warning(f"未找到用户 {user_id}，无法更新头像")
                return False, "用户不存在"

            if result.modified_count > 0:
                logger.info(f"用户 {user_id} 头像已更新")
                return True, "头像已更新"
            else:
                logger.info(f"用户 {user_id} 头像未变化")
                return True, "头像未变化"

        except Exception as e:
            error_msg = f"更新用户头像时出错: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def find_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        根据用户ID查找用户

        Args:
            user_id: 用户ID

        Returns:
            Optional[Dict]: 用户数据字典，如果未找到则返回None
        """
        try:
            user = await self.db.users.find_one({"id": user_id})
            if user:
                # 转换list类型回set类型
                return self._convert_lists_to_sets(user)
            return None
        except Exception as e:
            logger.error(f"查找用户失败: {str(e)}")
            return None

    async def find_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        根据用户名查找用户

        Args:
            username: 用户名

        Returns:
            Optional[Dict]: 用户数据字典，如果未找到则返回None
        """
        try:
            user = await self.db.users.find_one({"username": username})
            if user:
                # 转换list类型回set类型
                return self._convert_lists_to_sets(user)
            return None
        except Exception as e:
            logger.error(f"根据用户名查找用户失败: {str(e)}")
            return None

    async def disconnect(self):
        """断开MongoDB连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB连接已关闭")

    async def check_connection_status(self) -> Dict[str, Any]:
        """
        检查MongoDB连接状态并返回诊断信息

        Returns:
            Dict包含连接状态信息
        """
        result = {
            "connected": False,
            "client_initialized": self.client is not None,
            "db_initialized": self.db is not None,
            "error": None
        }

        try:
            if self.client is None:
                result["error"] = "MongoDB客户端未初始化"
                return result

            # 尝试ping测试
            await self.client.admin.command('ping')
            result["connected"] = True

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"MongoDB连接检查失败: {str(e)}")

        return result