"""
llm_pipeline

Description:
    LLM转发层的相关流程，处理API调用和消息转发

Notes:
    完成API调用+LLM流式调用，返回原始流式响应
    不做任何额外处理，仅组装消息格式并调用API
"""

from typing import AsyncGenerator, List
from models.message import Message
from llm.api_pool import api_pool
from llm.http_client import generate
from utils.logger_utils import get_logger
from llm.prompts_manager import PromptsManager

# 创建全局实例
prompts_manager = PromptsManager()
logger = get_logger(__name__)

class LLM_Pipeline:
    def __init__(self):
        self.prompts_manager = prompts_manager  # 添加类属性引用
        logger.info("LLM Pipeline已初始化")

    def _format_chat_history(self, messages: List[Message], max_messages: int = 30) -> str:
        """
        将Message对象列表转换为字符串格式
        
        Args:
            messages: Message对象列表
            max_messages: 最大消息数量，缓存的消息，因为要转化格式，所以需要缓存
            
        Returns:
            格式化后的聊天历史字符串
        """
        # 只保留最近的消息
        recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages
        
        # 使用字符串拼接构建聊天历史
        history = ""
        for msg in recent_messages:
            # 判断是否为系统消息
            prefix = "[系统] " if msg.is_system else ""
            # 添加时间戳和用户名
            history += f"{prefix}[{msg.timestamp}] {msg.user_name}: {msg.content}\n"
            
        return history

    async def chat_completion(
        self,
        messages: List[Message],
        current_message: str,
        context_type: str
    ) -> AsyncGenerator[str, None]:
        """
        组装消息并调用API获取流式响应
        
        Args:
            messages: 消息列表，包含历史消息
            current_message: 当前消息内容
            context_type: 上下文类型
        """
        try:
            # 1. 获取对应场景的prompt
            prompt = self.prompts_manager.get_prompt_for_context(context_type)
            
            # 2. 格式化历史消息
            chat_history_str = self._format_chat_history(messages)
            
            # 3. 组装消息格式
            formatted_messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"以下是聊天历史：\n{chat_history_str}\n\n当前消息：{current_message}"}
            ]
            
            # 4. 从API池获取API并调用
            provider, api_key = await api_pool.get_api()
            try:
                async for chunk in generate(provider, api_key, formatted_messages):
                    yield chunk
            finally:
                # 确保释放API资源
                api_pool.release_api(provider, api_key)
                
        except Exception as e:
            logger.error(f"LLM请求处理失败: {str(e)}")
            yield f"AI助手遇到了问题: {str(e)}"
            
# 创建单例实例
llm_pipeline = LLM_Pipeline()
