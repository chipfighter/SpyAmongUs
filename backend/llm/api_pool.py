"""
llm/api_fetch

Description:
    LLM的API管理操作

Notes:
    统一管理所有API，使用单一队列，暂时不区分提供商

To-Do:
    （可选）API使用统计、失败率监控
"""
import json
import asyncio
import os
from typing import Dict, List, Tuple


class APIPool:
    def __init__(self):
        """初始化API池"""
        self.api_data = self._load_api_keys()
        self.api_queue = asyncio.Queue()
        self.total_apis = 0
        
        # 将所有API密钥放入统一队列（当前版本）
        for provider, keys in self.api_data.items():
            for key in keys:
                self.api_queue.put_nowait((provider, key))
                self.total_apis += 1
    
    def _load_api_keys(self) -> Dict[str, List[str]]:
        """从api_keys.json加载API密钥"""
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        api_keys_path = os.path.join(current_dir, "api_keys.json")

        try:
            with open(api_keys_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载API密钥文件失败: {e}")
            return {}
    
    async def get_api(self) -> Tuple[str, str]:
        """
        获取一个可用的API密钥

        如果没有可用的API，会阻塞直到有API被释放
        
        Returns:
            (provider, api_key)元组
        """
        # 直接调用queue.get()，当队列为空时会自动阻塞等待
        provider, api_key = await self.api_queue.get()
        return provider, api_key
    
    def release_api(self, provider: str, api_key: str) -> bool:
        """
        释放API，使其可以被其他请求使用
        
        Args:
            provider: API提供商名称（兼容性参数）
            api_key: 要释放的API密钥
            
        Returns:
            释放是否成功
        """
        # 将API放回队列，原子操作
        self.api_queue.put_nowait((provider, api_key))
        return True
    
    def get_status(self) -> Dict[str, int]:
        """
        获取API池状态信息
        
        Returns:
            Dict[total_apis, available_apis]
        """
        return {
            "total": self.total_apis,
            "available": self.api_queue.qsize()
        }


# 模块级单例，系统只用一个单例
api_pool = APIPool()
