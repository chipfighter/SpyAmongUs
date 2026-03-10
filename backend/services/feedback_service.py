import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from utils.mongo_utils import MongoClient
import time

logger = logging.getLogger(__name__)

class FeedbackService:
    """
    反馈服务 - 负责处理用户反馈的提交和管理
    """
    
    def __init__(self, mongo_client: MongoClient):
        """
        初始化反馈服务
        
        Args:
            mongo_client: MongoDB客户端实例
        """
        self.mongo_client = mongo_client
        self.feedbacks_collection = self.mongo_client.db['feedbacks']
        logger.info("反馈服务初始化完成")
    
    async def submit_feedback(self, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        提交用户反馈
        
        Args:
            feedback_data: 包含反馈内容的字典，必须包含type和content字段
            
        Returns:
            包含操作结果的字典
        """
        try:
            # 验证必要字段
            if not feedback_data.get('type') or not feedback_data.get('content'):
                return {
                    "success": False,
                    "message": "反馈类型和内容不能为空"
                }
            
            # 生成当前时间戳（毫秒）
            current_timestamp = feedback_data.get('created_at', int(time.time() * 1000))
            
            # 生成自定义ID - 使用用户ID和时间戳组合，而不是MongoDB的ObjectId
            user_id = feedback_data.get('user_id', 'anonymous')
            custom_id = f"feedback_{user_id}_{current_timestamp}"
            
            # 准备存储的反馈数据
            feedback_record = {
                "_id": custom_id,  # 使用自定义ID
                "type": feedback_data.get('type'),
                "content": feedback_data.get('content'),
                "user_id": user_id,
                "username": feedback_data.get('username', '匿名用户'),
                "created_at": current_timestamp,  # 使用毫秒级时间戳
                "resolved_at": None,  # 解决时间，初始为空
                "status": "pending",  # 初始状态：pending（待处理）
            }
            
            # 打印存储数据，便于调试
            logger.info(f"存储反馈数据: {feedback_record}")
            
            # 存储到MongoDB
            try:
                result = await self.feedbacks_collection.insert_one(feedback_record)
                inserted_id = result.inserted_id
            except Exception as db_error:
                # 如果是主键冲突，尝试添加随机后缀
                if "duplicate key error" in str(db_error):
                    import random
                    custom_id = f"{custom_id}_{random.randint(1000, 9999)}"
                    feedback_record["_id"] = custom_id
                    result = await self.feedbacks_collection.insert_one(feedback_record)
                    inserted_id = result.inserted_id
                else:
                    raise
            
            if inserted_id:
                logger.info(f"用户反馈提交成功: {inserted_id}")
                return {
                    "success": True,
                    "message": "反馈提交成功，感谢您的宝贵意见！",
                    "feedback_id": str(inserted_id)
                }
            else:
                logger.error("反馈提交失败，无法插入数据")
                return {
                    "success": False,
                    "message": "反馈提交失败，请稍后重试"
                }
        except Exception as e:
            logger.exception(f"提交反馈时发生错误: {str(e)}")
            return {
                "success": False,
                "message": f"处理反馈时发生错误: {str(e)}"
            }
    
    async def get_all_feedbacks(self, status: Optional[str] = None, type: Optional[str] = None) -> Dict[str, Any]:
        """
        获取所有反馈（可根据状态和类型筛选）
        
        Args:
            status: 可选，反馈状态筛选（pending/resolved/rejected）
            type: 可选，反馈类型筛选
            
        Returns:
            包含反馈列表的结果字典
        """
        try:
            # 构建查询条件
            query = {}
            if status:
                query["status"] = status
            if type:
                query["type"] = type
            
            # 查询数据库 - 按created_at降序排序
            cursor = self.feedbacks_collection.find(query).sort("created_at", -1)
            feedbacks = await cursor.to_list(length=100)  # 限制最多返回100条
            
            # 处理ObjectId为字符串 - 确保_id都是字符串格式
            for feedback in feedbacks:
                # 确保_id是字符串格式，无论是什么类型的_id
                feedback["_id"] = str(feedback["_id"])
                
                # 添加额外的id字段，使前端使用更方便
                feedback["id"] = feedback["_id"]
                
                # 如果有用户ID，添加简短version
                if feedback.get("user_id") and feedback["user_id"] != "anonymous":
                    feedback["short_id"] = f"反馈-{feedback['user_id'][-4:]}-{str(feedback.get('created_at', ''))[-6:]}"
                else:
                    feedback["short_id"] = f"匿名反馈-{str(feedback.get('created_at', ''))[-6:]}"
            
            return {
                "success": True,
                "message": "获取反馈列表成功",
                "data": feedbacks,
                "count": len(feedbacks)
            }
        except Exception as e:
            logger.exception(f"获取反馈列表时发生错误: {str(e)}")
            return {
                "success": False,
                "message": f"获取反馈列表失败: {str(e)}"
            }
    
    async def update_feedback_status(self, feedback_id: str, new_status: str) -> Dict[str, Any]:
        """
        更新反馈状态
        
        Args:
            feedback_id: 反馈ID
            new_status: 新状态（pending/resolved/rejected）
            
        Returns:
            操作结果
        """
        try:
            # 验证状态值
            valid_statuses = ["pending", "resolved", "rejected"]
            if new_status not in valid_statuses:
                return {
                    "success": False,
                    "message": f"无效的状态值，有效值为: {', '.join(valid_statuses)}"
                }
            
            # 准备更新数据
            # 不再需要从bson.objectid导入ObjectId
            current_timestamp = int(time.time() * 1000)
            update_data = {"status": new_status}
            
            # 如果状态是resolved，添加解决时间
            if new_status == "resolved":
                update_data["resolved_at"] = current_timestamp
                
            # 更新数据库 - 使用字符串ID而不是ObjectId
            result = await self.feedbacks_collection.update_one(
                {"_id": feedback_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return {
                    "success": True,
                    "message": f"反馈状态更新为 {new_status}"
                }
            else:
                # 尝试使用旧的ObjectId格式（向后兼容）
                try:
                    from bson.objectid import ObjectId
                    legacy_result = await self.feedbacks_collection.update_one(
                        {"_id": ObjectId(feedback_id)},
                        {"$set": update_data}
                    )
                    
                    if legacy_result.modified_count > 0:
                        return {
                            "success": True,
                            "message": f"反馈状态更新为 {new_status} (旧ID格式)"
                        }
                except Exception:
                    pass
                    
                return {
                    "success": False,
                    "message": "未找到指定反馈或状态未发生变化"
                }
        except Exception as e:
            logger.exception(f"更新反馈状态时发生错误: {str(e)}")
            return {
                "success": False,
                "message": f"更新反馈状态失败: {str(e)}"
            } 