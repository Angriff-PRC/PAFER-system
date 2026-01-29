# utils/logger.py
import logging
import sys
from datetime import datetime
from pathlib import Path
from config.settings import Config

# 创建 logs 目录
Path("logs").mkdir(exist_ok=True)

def get_logger(name: str = "PAFER"):
    """获取结构化日志器，支持 trade_id 上下文追踪"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, Config.LOGGING.level))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)

    # 文件输出
    file_handler = logging.FileHandler(
        f"logs/pafar_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

# 全局 logger 实例（供其他模块直接使用）
logger = get_logger()
