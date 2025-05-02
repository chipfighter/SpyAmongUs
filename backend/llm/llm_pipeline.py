"""
llm_pipeline

Description:
    LLM转发层的相关流程，处理API调用和消息转发

Notes:
    完成API调用+LLM流式调用，返回原始流式响应
    不做任何额外处理，仅组装消息格式并调用API
"""

from typing import AsyncGenerator, List, Dict, Any
from models.message import Message
from llm.api_pool import api_pool
from llm.http_client import generate, preprocess_send, http_send
from utils.logger_utils import get_logger
from llm.prompts_manager import PromptsManager
import json
import random
import asyncio

# 创建全局实例
prompts_manager = PromptsManager()
logger = get_logger(__name__)

class LLM_Pipeline:
    def __init__(self):
        self.prompts_manager = prompts_manager  # 添加类属性引用
        self.game_service = None  # 后续通过set_game_service设置
        logger.info("LLM Pipeline已初始化")

    def set_game_service(self, game_service):
        """设置游戏服务引用，避免循环依赖"""
        self.game_service = game_service
        logger.info("LLM Pipeline已连接到GameService")

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
            history += f"{prefix}[{msg.timestamp}] {msg.username}: {msg.content}\n"
            
        return history

    async def chat_completion(
        self,
        messages: List[Message],
        current_message: str,
        context_type: str,
        game_info: Dict[str, Any] = None
    ) -> AsyncGenerator[str, None]:
        """
        组装消息并调用API获取流式响应
        
        Args:
            messages: 消息列表，包含历史消息
            current_message: 当前消息内容
            context_type: 上下文类型
            game_info: 游戏相关信息，用于游戏场景的提示词生成
        """
        try:
            # 1. 获取对应场景的prompt
            prompt = self.prompts_manager.get_prompt_for_context(context_type, game_info)
            
            # 2. 格式化历史消息
            chat_history_str = self._format_chat_history(messages)
            
            # 添加聊天历史到游戏信息中(如果是游戏场景)
            if game_info is not None and context_type == "game_playing":
                # 避免重复的聊天历史
                if "chat_history" not in game_info:
                    game_info["chat_history"] = chat_history_str
                    # 重新获取包含聊天历史的提示词
                    prompt = self.prompts_manager.get_prompt_for_context(context_type, game_info)
            
            # 3. 组装消息格式
            formatted_messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"请根据游戏状态和聊天历史，给出你的回应:\n {current_message}"}
            ]
            
            # 添加函数定义（如果是投票阶段）
            functions = None
            if context_type == "voting":
                functions = [
                    {
                        "name": "vote",
                        "description": "投票给指定玩家",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "target_id": {
                                    "type": "string",
                                    "description": "被投票玩家的ID"
                                },
                                "reason": {
                                    "type": "string", 
                                    "description": "投票理由"
                                }
                            },
                            "required": ["target_id"]
                        }
                    }
                ]
            
            # 4. 从API池获取API并调用
            provider, api_key = await api_pool.get_api()
            try:
                # 如果是投票阶段且支持函数调用，则传入函数定义
                if functions:
                    # 非流式调用，直接获取完整响应
                    url, headers, payload = await preprocess_send(provider, api_key, formatted_messages, stream=False)
                    payload["functions"] = functions
                    payload["function_call"] = "auto"
                    
                    response, session = await http_send(url, headers, payload)
                    response_json = await response.json()
                    await session.close()
                    
                    # 处理函数调用
                    if "choices" in response_json and response_json["choices"]:
                        choice = response_json["choices"][0]
                        message = choice.get("message", {})
                        function_call = message.get("function_call")
                        
                        if function_call and function_call.get("name") == "vote":
                            try:
                                # 解析函数参数
                                args = json.loads(function_call.get("arguments", "{}"))
                                target_id = args.get("target_id")
                                reason = args.get("reason", "")
                                
                                # 获取AI用户ID
                                ai_user_id = game_info.get("user_id") if game_info else None
                                
                                if ai_user_id and target_id and self.game_service:
                                    # 执行投票
                                    room_id = game_info.get("room_id") if game_info else None
                                    if room_id:
                                        logger.info(f"AI玩家 {ai_user_id} 投票给 {target_id}，理由: {reason}")
                                        
                                        # 添加随机延迟，模拟思考时间 (2-5秒)
                                        voting_delay = random.uniform(2.0, 5.0)
                                        logger.info(f"AI玩家 {ai_user_id} 正在思考投票，延迟 {voting_delay:.2f} 秒")
                                        await asyncio.sleep(voting_delay)
                                        
                                        # 执行投票
                                        await self.game_service.handle_player_vote(room_id, ai_user_id, target_id)
                                        
                                        # 返回投票消息
                                        yield f"我投票给了 {target_id}。{reason}"
                                    else:
                                        yield f"无法执行投票，缺少房间ID"
                                else:
                                    yield f"无法执行投票，缺少必要参数"
                            except Exception as e:
                                logger.error(f"处理AI投票失败: {str(e)}")
                                yield f"投票处理失败: {str(e)}"
                        else:
                            # 如果没有函数调用，返回普通响应
                            content = message.get("content", "AI未能给出有效回复")
                            
                            # 分块处理文本，每块添加短暂延迟
                            chunk_size = 15  # 每块大约15个字符
                            chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
                            
                            for chunk in chunks:
                                yield chunk
                                # 添加短暂延迟，模拟打字效果 (0.1-0.3秒)
                                typing_delay = random.uniform(0.1, 0.3)
                                await asyncio.sleep(typing_delay)
                    else:
                        yield "AI未能给出有效回复"
                else:
                    # 流式响应
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
