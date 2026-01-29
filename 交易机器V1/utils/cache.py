# utils/cache.py
import functools
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

# K线缓存装饰器（5分钟内相同参数不重复请求）
@functools.lru_cache(maxsize=128)
def cached_kline(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        # 注入时间戳（供UI显示）
        if hasattr(result, 'attrs'):
            result.attrs['last_fetched'] = datetime.now().isoformat()
        return result
    return wrapper
