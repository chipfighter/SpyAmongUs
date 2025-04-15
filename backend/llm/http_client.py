"""
llm/http_client

Description:
    负责处理LLM的HTTP请求和响应解析
    仅仅处理http发送相关的预处理+流式消息处理，并不处理任何业务相关的逻辑。

Methods:
    - preprocess_send: 根据provider准备参数，然后输入给http_send发送
    - http_send: 仅仅实现发送http请求，然后得到response的操作，stream_process处理完后直接返回
    - stream_process: 统一处理所有流式返回为增量式

Notes:
    暂时不使用jwt来配合鉴权，使用最简单的API直接放请求头

TODO:
    1.重试机制+超时控制
    2.调整错误处理+日志统计
"""

import json
import aiohttp
from typing import Dict, Any, AsyncGenerator, Optional, List, Tuple

# 各提供商的API端点
LLM_ENDPOINTS = {
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4/chat/completions"
}

# 默认模型映射
DEFAULT_MODELS = {
    "deepseek": "deepseek-chat",
    "zhipu": "glm-4"
}


async def preprocess_send(provider: str, api_key: str, messages: List[Dict[str, str]], 
                         stream: bool = True, **kwargs) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """
    根据provider预处理请求参数
    
    Args:
        provider: LLM提供商名称
        api_key: API密钥
        messages: 消息列表 [{"role": "user", "content": "..."}]
        stream: 是否使用流式响应
        **kwargs: 其他参数，如temperature等
        
    Returns:
        (url, headers, payload) 元组
    """
    # 1. 确定端点URL
    url = LLM_ENDPOINTS.get(provider)
    if not url:
        raise ValueError(f"不支持的提供商: {provider}")
    
    # 2. 准备请求头
    headers = {
        "Content-Type": "application/json"
    }
    
    # 2. 不同提供商的认证方式（将API封装好）
    if provider in ["deepseek", "zhipu"]:
        headers["Authorization"] = f"Bearer {api_key}"
    
    # 3. 准备请求体
    model = kwargs.pop("model", DEFAULT_MODELS.get(provider))
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream
    }
    
    # 添加其他参数
    for key, value in kwargs.items():
        payload[key] = value
    
    return url, headers, payload


async def http_send(url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> aiohttp.ClientResponse:
    """
    发送HTTP请求
    
    Args:
        url: 需求官网
        headers: 请求头
        payload: 请求体
        
    Returns:
        HTTP响应对象

    Raises:
        Exception: 当请求失败时的报错
    """
    try:
        session = aiohttp.ClientSession()
        response = await session.post(url, headers=headers, json=payload)
        
        if response.status != 200:
            error_text = await response.text()
            await session.close()
            raise Exception(f"API请求失败: {response.status}, {error_text}")
        
        # session会在stream_process完成后关闭
        return response, session
    except Exception as e:
        # 确保出错时session也被关闭
        if 'session' in locals():
            await session.close()
        raise e


async def stream_process(provider: str, response: aiohttp.ClientResponse, 
                       session: aiohttp.ClientSession) -> AsyncGenerator[str, None]:
    """
    处理流式响应，返回统一的增量消息格式
    
    Args:
        provider: LLM提供商名称
        response: HTTP响应对象
        session: aiohttp会话对象，用于在处理完成后关闭
        
    Yields:
        增量文本片段
        
    Note:
        使用完毕后会自动关闭session
    """
    try:
        # 不同提供商的响应处理方式
        if provider in ["deepseek", "zhipu"]:
            # 这两个提供商使用相似的SSE格式
            last_content = ""  # 用于跟踪完整响应
            
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if not line or line == "data: [DONE]":
                    continue
                    
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        
                        # 提取当前文本
                        current_content = ""
                        if "choices" in data and data["choices"]:
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                # 对于非增量式API，计算增量部分
                                if provider == "deepseek" or provider == "zhipu":
                                    # 实际上，大多数现代API都使用增量式返回
                                    # 因此这里可能不需要计算增量，直接返回content即可
                                    # 但为了兼容性，我们仍然保留这个逻辑
                                    yield content
                    except json.JSONDecodeError as e:
                        # 忽略解析错误，继续处理下一行
                        pass
    finally:
        # 确保session被关闭
        await session.close()


async def generate(provider: str, api_key: str, messages: List[Dict[str, str]], 
                  stream: bool = True, **kwargs) -> AsyncGenerator[str, None]:
    """
    集成函数：预处理、发送请求并处理响应
    
    Args:
        provider: LLM提供商名称
        api_key: API密钥
        messages: 消息列表
        stream: 是否使用流式响应
        **kwargs: 其他参数
        
    Yields:
        增量文本片段
    """
    # 1. 预处理请求参数
    url, headers, payload = await preprocess_send(provider, api_key, messages, stream, **kwargs)
    
    # 2. 发送请求
    response, session = await http_send(url, headers, payload)
    
    # 3. 处理响应
    async for chunk in stream_process(provider, response, session):
        yield chunk
