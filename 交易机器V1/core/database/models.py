# core/database/models.py
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

@dataclass
class TradeRecord:
    trade_id: str
    side: str  # "buy" | "sell"
    open_time: str  # ISO format
    open_price: float
    close_time: str
    close_price: float
    pnl: float
    fee: float
    net_pnl: float
    balance_after: float
    reason: str
    is_virtual: bool = True

@dataclass
class VirtualTrade:
    trade_id: str
    side: str
    open_time: str
    open_price: float
    close_time: str
    close_price: float
    pnl: float
    fee: float
    net_pnl: float
    balance_after: float
    reason: str

@dataclass
class StrategyConfigRecord:
    id: int
    macd_fast: int
    macd_slow: int
    macd_signal: int
    kdj_period: int
    kdj_smooth_k: int
    kdj_smooth_d: int
    ma_short: int
    ma_mid: int
    ma_long: int
    momentum_threshold_pct: float
    max_klines_for_resonance: int
    updated_at: str

@dataclass
class OptimizationHistory:
    id: int
    generation: int
    config_id: int
    fitness_score: float
    trade_count: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    timestamp: str
