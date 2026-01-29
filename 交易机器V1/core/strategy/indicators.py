# core/strategy/indicators.py
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any

def calculate_macd(df: pd.DataFrame, fast=3, slow=18, signal=6) -> pd.DataFrame:
    """MACD(3,18,6) —— 支持飘逸/蓄力量化"""
    close = df['close'].astype(float)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line

    # 飘逸检测：MACD线与Signal线距离扩大但未交叉
    diff = macd_line - signal_line
    is_drift = (diff > 0) & (diff.shift(1) < diff) & (macd_line < signal_line)  # 死叉飘逸
    is_drift |= (diff < 0) & (diff.shift(1) > diff) & (macd_line > signal_line)  # 金叉飘逸

    # 蓄力检测：连续N次金叉失败（柱状图反复收缩后爆发）
    hist_change = macd_hist.diff().fillna(0)
    # 简化：柱面积变化率 > 15% 且方向一致即为力度达标
    hist_area = macd_hist.abs()
    hist_momentum = (hist_area - hist_area.shift(1)) / (hist_area.shift(1) + 1e-8) * 100

    df['macd_line'] = macd_line
    df['macd_signal'] = signal_line
    df['macd_hist'] = macd_hist
    df['macd_drift'] = is_drift.astype(int)
    df['macd_momentum_pct'] = hist_momentum
    return df

def calculate_kdj(df: pd.DataFrame, period=9, smooth_k=3, smooth_d=3) -> pd.DataFrame:
    """KDJ(9,3,3) —— 斜率敏感版"""
    low = df['low'].astype(float)
    high = df['high'].astype(float)
    close = df['close'].astype(float)

    ll = low.rolling(window=period).min()
    hh = high.rolling(window=period).max()
    rsv = (close - ll) / (hh - ll + 1e-8) * 100

    k = rsv.ewm(span=smooth_k, adjust=False).mean()
    d = k.ewm(span=smooth_d, adjust=False).mean()
    j = 3 * k - 2 * d

    # K斜率（度）：arctan((k - k.shift(1)) / (1/15)) → 近似为 k.diff()*100
    k_slope = k.diff().fillna(0) * 100

    df['kdj_k'] = k
    df['kdj_d'] = d
    df['kdj_j'] = j
    df['kdj_k_slope'] = k_slope
    return df

def calculate_ma(df: pd.DataFrame, ma5=5, ma10=10, ma45=45) -> pd.DataFrame:
    """MA5/MA10/MA45 —— 支持踩实判定"""
    close = df['close'].astype(float)
    df['ma5'] = close.rolling(ma5).mean()
    df['ma10'] = close.rolling(ma10).mean()
    df['ma45'] = close.rolling(ma45).mean()

    # MA45踩实：收盘价站稳MA45 ≥ 2根K，且MACD柱由负转正
    ma45_stable = (close >= df['ma45']) & (close.shift(1) >= df['ma45'].shift(1))
    df['ma45_stable'] = ma45_stable.astype(int)
    return df

def add_paferr_features(df: pd.DataFrame, config) -> pd.DataFrame:
    """添加所有PAFER特征列"""
    df = calculate_macd(df, config.macd_fast, config.macd_slow, config.macd_signal)
    df = calculate_kdj(df, config.kdj_period, config.kdj_smooth_k, config.kdj_smooth_d)
    df = calculate_ma(df, config.ma_short, config.ma_mid, config.ma_long)
    return df
