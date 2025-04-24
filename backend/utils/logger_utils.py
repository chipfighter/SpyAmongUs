"""
logger_utils

Description:
    提供统一的日志记录接口，确保所有模块仅在程序启动时初始化一次 logger 实例
"""
import logging
from typing import Optional, Dict

# 内部缓存，避免重复创建 logger
_logger_cache: Dict[str, logging.Logger] = {}


def setup_logger(name: str, level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
    """创建并配置 logger 实例

    Args:
        name: 日志记录器名称，通常使用模块名
        level: 日志级别，默认 INFO
        log_file: 可选的日志文件路径（选）

    Returns:
        配置好的 logger 实例
    """
    if name in _logger_cache:
        return _logger_cache[name]  # 如果缓存中已存在，直接返回缓存的 logger，避免每个模块都加载一遍，单例模式实现logger

    # 创建新的 logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if not logger.handlers:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # 配置handler控制台输出
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # 文件输出（选）
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    logger.propagate = False  # 防止日志向上传播导致重复输出
    _logger_cache[name] = logger  # 初始化创建好的logger缓存
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取 logger 实例，用于模块中直接获取本模块专属 logger

    Args:
        name: logger 名称，默认使用当前模块名

    Returns:
        logger 实例

    Examples:
        logger = get_logger(__name__)
    """
    return logging.getLogger(name or __name__)
