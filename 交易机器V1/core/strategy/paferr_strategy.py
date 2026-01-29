# core/strategy/paferr_strategy.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from config.settings import Config  # ✅ 顶部导入
from core.strategy.indicators import add_paferr_features
from utils.logger import get_logger

logger = get_logger(__name__)

class PAFERStrategy:
    def __init__(self, config=None):
        self.config = config or Config.STRATEGY
        self.last_signal_time = None
        self.signal_cooldown = timedelta(minutes=15)

    def _check_resonance(self, df: pd.DataFrame, lookback: int = 4) -> Dict[str, bool]:
        """检测多周期共振（15/30/1H/4H）—— 对每个周期单独计算指标"""
        from core.strategy.indicators import add_paferr_features

        # 原始15m数据（已计算指标）
        df_15m = df.copy()
        if 'ma45' not in df_15m.columns:
            df_15m = add_paferr_features(df_15m, self.config)

        # 生成30m数据并计算指标
        df_30m = df.resample('30T', on='timestamp').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        }).dropna()
        if len(df_30m) >= 50:
            df_30m = add_paferr_features(df_30m, self.config)
        else:
            df_30m = pd.DataFrame()

        # 生成1h数据并计算指标
        df_1h = df.resample('1H', on='timestamp').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        }).dropna()
        if len(df_1h) >= 50:
            df_1h = add_paferr_features(df_1h, self.config)
        else:
            df_1h = pd.DataFrame()

        # 生成4h数据并计算指标
        df_4h = df.resample('4H', on='timestamp').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        }).dropna()
        if len(df_4h) >= 50:
            df_4h = add_paferr_features(df_4h, self.config)
        else:
            df_4h = pd.DataFrame()

        def get_trend_status(_df: pd.DataFrame) -> bool:
            if len(_df) < 2 or 'ma45' not in _df.columns or 'macd_hist' not in _df.columns:
                return False
            return (_df['close'].iloc[-1] > _df['ma45'].iloc[-1]) and (_df['macd_hist'].iloc[-1] > 0)

        return {
            '15m': get_trend_status(df_15m),
            '30m': get_trend_status(df_30m),
            '1h': get_trend_status(df_1h),
            '4h': get_trend_status(df_4h),
        }

    def _check_momentum(self, df: pd.DataFrame) -> bool:
        latest = df.iloc[-1]
        return (
            abs(latest['macd_momentum_pct']) > self.config.momentum_threshold_pct
            and abs(latest['kdj_k_slope']) > 25
        )

    def _check_timeliness(self, df: pd.DataFrame) -> bool:
        recent = df.tail(self.config.max_klines_for_resonance)
        return (recent['close'] > recent['ma45']).sum() >= self.config.max_klines_for_resonance

    def _check_drift_accumulation(self, df: pd.DataFrame, window=5) -> int:
        return df.tail(window)['macd_drift'].sum()

    def generate_signal(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        if len(df) < 50:
            return None

        df = add_paferr_features(df, self.config)

        now = pd.to_datetime(df['timestamp'].iloc[-1])
        if self.last_signal_time and (now - self.last_signal_time) < self.signal_cooldown:
            return None

        resonance = self._check_resonance(df)
        total_resonance = sum(resonance.values())
        is_bullish = total_resonance >= 3
        is_bearish = total_resonance == 0 and resonance['4h'] is False

        has_momentum = self._check_momentum(df)
        is_timely = self._check_timeliness(df)
        drift_count = self._check_drift_accumulation(df)

        if is_bullish and has_momentum and is_timely:
            latest = df.iloc[-1]
            # ✅ 修复：从 Config.RISK 读取 buffer
            sl = latest['ma45'] * (1 - Config.RISK.stop_loss_buffer)
            tp = latest['high'] + 1.5 * (latest['high'] - latest['low'])
            leverage = min(50, max(20, 20 + drift_count * 5))

            self.last_signal_time = now
            return {
                'action': 'buy',
                'reason': f"PAFER Bullish Resonance({total_resonance}/4)+Momentum+Timely",
                'confidence': 0.7 + 0.1 * drift_count,
                'stop_loss': sl,
                'take_profit': tp,
                'leverage': leverage
            }

        elif is_bearish and has_momentum and is_timely:
            latest = df.iloc[-1]
            # ✅ 修复：从 Config.RISK 读取 buffer
            sl = latest['ma45'] * (1 + Config.RISK.stop_loss_buffer)
            tp = latest['low'] - 1.5 * (latest['high'] - latest['low'])
            leverage = min(50, max(20, 20 + drift_count * 5))

            self.last_signal_time = now
            return {
                'action': 'sell',
                'reason': f"PAFER Bearish Resonance(0/4)+Momentum+Timely",
                'confidence': 0.65 + 0.1 * drift_count,
                'stop_loss': sl,
                'take_profit': tp,
                'leverage': leverage
            }

        return {'action': 'hold', 'reason': 'No valid PAFER signal'}

    def reset(self):
        self.last_signal_time = None
        logger.info("PAFERStrategy reset (Rollback executed)")
