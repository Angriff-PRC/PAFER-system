# config/settings.py
import os
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class ExchangeConfig:
    symbol: str = "ETH/USDT"
    timeframe: str = "15m"  # PAFER主级别
    leverage_range: tuple = (20, 50)
    fee_rate_taker: float = 0.0006  # 火币P0市价费率
    fee_rate_maker: float = 0.0002
    min_notional: float = 5.0  # USDT

@dataclass
class RiskConfig:
    max_loss_percent: float = 5.0  # 全仓最大5%
    max_position_size_usd: float = 500.0
    stop_loss_buffer: float = 0.003  # ✅ 已添加：0.3% 插针缓冲（防假突破）

@dataclass
class StrategyConfig:
    # PAFER核心参数（可被AutoOptimizer优化）
    macd_fast: int = 3
    macd_slow: int = 18
    macd_signal: int = 6
    kdj_period: int = 9
    kdj_smooth_k: int = 3
    kdj_smooth_d: int = 3
    ma_short: int = 5
    ma_mid: int = 10
    ma_long: int = 45
    # 时效性约束（K线根数）
    max_klines_for_resonance: int = 4
    # 力度阈值（MACD柱面积变化率 %）
    momentum_threshold_pct: float = 15.0

@dataclass
class DatabaseConfig:
    db_path: str = "data/pafar_trades.db"

@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/pafar.log"

class Config:
    EXCHANGE = ExchangeConfig()
    RISK = RiskConfig()
    STRATEGY = StrategyConfig()
    DB = DatabaseConfig()
    LOGGING = LoggingConfig()

    @classmethod
    def from_env(cls):
        if os.getenv("DEBUG") == "1":
            cls.LOGGING.level = "DEBUG"
        return cls()
