# utils/helpers.py
import numpy as np
from typing import Optional, Dict, Any
from config.settings import Config

def calculate_slippage(price: float, order_type: str = "market") -> float:
    """
    模拟火币市场单滑点（单位：小数，如 0.001 = 0.1%）
    火币永续合约典型滑点范围：0.02% ~ 0.15%（根据盘口深度动态）
    """
    if order_type == "market":
        # 基于价格波动率估算滑点（简化模型）
        vol_factor = np.random.uniform(0.0002, 0.0015)  # 0.02% ~ 0.15%
        return vol_factor * (1 + np.random.normal(0, 0.3))  # 加入随机扰动
    else:  # limit order
        return np.random.uniform(-0.0001, 0.0001)  # 限价单滑点极小（±0.01%）

def round_price(price: float, symbol: str = "ETH/USDT") -> float:
    """火币ETH/USDT价格精度：小数点后1位（如 3215.6）"""
    return round(price, 1)

def round_quantity(quantity: float, symbol: str = "ETH/USDT") -> float:
    """火币ETH/USDT最小下单量：0.001 ETH"""
    return round(quantity, 3)

def get_leverage_for_risk(balance_usd: float, risk_pct: float = 5.0, 
                         price: float = 3000.0, sl_distance_usd: float = 30.0) -> int:
    """
    根据风险计算推荐杠杆（防止爆仓）
    示例：余额100U，风险5% → 最大亏损5U；若SL距当前价30U → 可开仓 size = 5 / 30 * 3000 ≈ 500U → 杠杆 = 500 / 100 = 5x
    """
    max_loss_usd = balance_usd * (risk_pct / 100.0)
    if sl_distance_usd <= 0:
        return 20
    position_size_usd = max_loss_usd / (sl_distance_usd / price)  # USD名义价值
    leverage = int(min(50, max(20, position_size_usd / balance_usd)))
    return leverage

# 兼容旧版函数名（如果你在其他地方用了 calc_slippage）
calc_slippage = calculate_slippage
