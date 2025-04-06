"""
logger_utils

Description:
    提供统一的日志记录接口
"""
import logging
from typing import Optional

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """创建并配置logger实例
    
    Args:
        name: 日志记录器名称，通常使用模块名
        level: 日志级别，默认INFO
        
    Returns:
        配置好的logger实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加handler
    if not logger.handlers:
        handler = logging.StreamHandler()
        # logger的格式设定
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取logger实例，如果不存在则创建
    
    Args:
        name: 日志记录器名称，默认为调用模块名
        
    Returns:
        logger实例

    Examples:
        需要的模块中初始化logger记录，然后正常使用logger即可
        logger = get_logger(__name__)
    """
    return logging.getLogger(name or __name__) 