# web/components/timeframe_screen.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from core.exchange.kline_fetcher import get_kline_fetcher
from core.strategy.indicators import add_paferr_features
from config.settings import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class TimeframeScreen:
    def __init__(self, screen_id: int, timeframe: str = "15m"):
        self.screen_id = screen_id
        self.timeframe = timeframe
        self.key_prefix = f"screen_{screen_id}_"

    def render(self):
        """渲染单个时间级别屏幕"""
        st.subheader(f"⏱️ {self.timeframe} — 屏幕 #{self.screen_id}")

        # 时间级别选择器（独立下拉）
        all_timeframes = [
            '1m','3m','5m','10m','15m','30m',
            '1h','2h','3h','4h','6h','12h',
            '1d','2d','3d','5d','1w','1M','3M'
        ]
        new_tf = st.selectbox(
            "选择时间级别",
            options=all_timeframes,
            index=all_timeframes.index(self.timeframe),
            key=f"{self.key_prefix}tf_select"
        )
        if new_tf != self.timeframe:
            self.timeframe = new_tf
            st.rerun()  # 重新加载该屏数据

        # 获取K线数据（带缓存）
        try:
            df = self._fetch_klines()
            if df.empty:
                st.warning("⚠️ 未获取到K线数据，使用模拟数据")
                df = self._simulate_klines()
        except Exception as e:
            logger.error(f"Kline fetch failed for {self.timeframe}: {e}")
            df = self._simulate_klines()

        # 计算指标
        df = add_paferr_features(df, Config.STRATEGY)

        # 渲染三联图
        self._render_kline_chart(df)
        self._render_macd_chart(df)
        self._render_kdj_chart(df)

    def _fetch_klines(self) -> pd.DataFrame:
        """从火币获取指定周期K线"""
        fetcher = get_kline_fetcher()
        # 映射 timeframes 到 ccxt 格式
        tf_map = {
            '1m': '1m', '3m': '3m', '5m': '5m', '10m': '10m', '15m': '15m', '30m': '30m',
            '1h': '1h', '2h': '2h', '3h': '3h', '4h': '4h', '6h': '6h', '12h': '12h',
            '1d': '1d', '2d': '2d', '3d': '3d', '5d': '5d', '1w': '1w', '1M': '1M', '3M': '3M'
        }
        ccxt_tf = tf_map.get(self.timeframe, '15m')
        return fetcher.fetch_recent_klines(limit=100, timeframe=ccxt_tf)

    def _simulate_klines(self) -> pd.DataFrame:
        """降级模拟：生成带BOLL/MA结构的合理价格序列"""
        import numpy as np
        now = pd.Timestamp.now()
        freq = self.timeframe.replace('m', 'T').replace('h', 'H').replace('d', 'D').replace('w', 'W').replace('M', 'MS')
        dates = pd.date_range(now - pd.Timedelta(minutes=1500), periods=100, freq=freq)
        
        # 模拟趋势+波动+BOLL通道
        base = 3200.0
        trend = np.linspace(0, 30, 100) * np.random.choice([1, -1])
        noise = np.cumsum(np.random.normal(0, 2, 100))
        close = base + trend + noise
        
        # BOLL(10,2) 计算
        rolling_close = pd.Series(close).rolling(10)
        mid = rolling_close.mean()
        std = rolling_close.std()
        upper = mid + 2 * std
        lower = mid - 2 * std
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': close - np.random.uniform(1, 3, 100),
            'high': close + np.random.uniform(2, 5, 100),
            'low': close - np.random.uniform(2, 5, 100),
            'close': close,
            'volume': np.random.randint(500, 3000, 100),
            'boll_upper': upper,
            'boll_mid': mid,
            'boll_lower': lower,
        })
        return df.fillna(method='bfill')

    #被下方的方法替代
    '''
    def _render_kline_chart(self, df: pd.DataFrame):
        """主K线图：含BOLL + MA5/10/30/45"""
        fig = make_subplots(
            rows=1, cols=1,
            shared_xaxes=True,
            specs=[[{"secondary_y": False}]]
        )

        # K线
        fig.add_trace(go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='K线',
            increasing_line_color='red',
            decreasing_line_color='green'
        ))

        # BOLL通道（蓝色系）
        if 'boll_upper' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['boll_upper'],
                mode='lines', name='BOLL(10,2) 上轨',
                line=dict(color='blue', width=1, dash='dot')
            ))
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['boll_mid'],
                mode='lines', name='BOLL 中轨',
                line=dict(color='lightblue', width=2)
            ))
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['boll_lower'],
                mode='lines', name='BOLL 下轨',
                line=dict(color='blue', width=1, dash='dot')
            ))

        # MA线（专业配色）
        ma_configs = [
            ('ma5', 'red', 'MA5'),
            ('ma10', 'orange', 'MA10'),
            ('ma30', 'green', 'MA30'),
            ('ma45', 'black', 'MA45')
        ]
        for col, color, name in ma_configs:
            if col in df.columns and not df[col].isna().all():
                fig.add_trace(go.Scatter(
                    x=df['timestamp'], y=df[col],
                    mode='lines', name=name,
                    line=dict(color=color, width=1.5)
                ))

        fig.update_layout(
            height=300,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=30, b=10),
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True, width='stretch')
    '''

    def _render_kline_chart(self, df: pd.DataFrame):
        """主K线图：K线+土黄BOLL+红/靛蓝/黄/紫MA线"""
        fig = make_subplots(
            rows=1, cols=1,
            shared_xaxes=True,
            specs=[[{"secondary_y": False}]]
        )

        # ✅ K线：涨=绿色，跌=红色（严格按你要求）
        fig.add_trace(go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='K线',
            increasing_line_color='green',      # ✅ 涨 = 绿
            decreasing_line_color='red',        # ✅ 跌 = 红
            increasing_fillcolor='lightgreen', # 可选：填充浅绿
            decreasing_fillcolor='lightsalmon'  # 可选：填充浅红
        ))

        # ✅ BOLL通道：土黄色（#CC9900）
        if 'boll_upper' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['boll_upper'],
                mode='lines', name='BOLL(10,2) 上轨',
                line=dict(color='#CC9900', width=1.2, dash='dot')  # ✅ 土黄
            ))
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['boll_mid'],
                mode='lines', name='BOLL 中轨',
                line=dict(color='red', width=2.5)  # ✅ 中轨 = 红色（同MA10）
            ))
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['boll_lower'],
                mode='lines', name='BOLL 下轨',
                line=dict(color='#CC9900', width=1.2, dash='dot')  # ✅ 土黄
            ))

        # ✅ MA线：严格按你指定颜色
        ma_configs = [
            ('ma5', '#4B0082', 'MA5（靛蓝）'),       # ✅ 靛蓝
            ('ma10', 'red', 'MA10（红）'),           # ✅ 红（同中轨）
            ('ma30', 'goldenrod', 'MA30（黄）'),     # ✅ 黄（goldenrod 是标准黄色）
            ('ma45', '#9400D3', 'MA45（亮紫）'),    # ✅ 亮紫（Indigo Violet）
        ]
        for col, color, name in ma_configs:
            if col in df.columns and not df[col].isna().all():
                fig.add_trace(go.Scatter(
                    x=df['timestamp'], y=df[col],
                    mode='lines', name=name,
                    line=dict(color=color, width=1.8, shape='spline')  # 平滑曲线更美观
                ))

        fig.update_layout(
            height=300,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=30, b=10),
            hovermode='x unified',
            font=dict(size=11)
        )
        st.plotly_chart(fig, use_container_width=True, width='stretch')

    def _render_macd_chart(self, df: pd.DataFrame):
        """MACD(3,18,6) 副图"""
        if 'macd_hist' not in df.columns:
            st.caption("MACD: 数据不足")
            return

        fig = make_subplots(
            rows=1, cols=1,
            shared_xaxes=True,
            specs=[[{"secondary_y": False}]]
        )

        # MACD柱状图（红绿）
        colors = ['red' if x < 0 else 'green' for x in df['macd_hist']]
        fig.add_trace(go.Bar(
            x=df['timestamp'], y=df['macd_hist'],
            name='MACD Hist',
            marker_color=colors,
            showlegend=False
        ))

        # MACD线 & Signal线
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['macd_line'],
            mode='lines', name='MACD Line',
            line=dict(color='orange', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['macd_signal'],
            mode='lines', name='Signal Line',
            line=dict(color='purple', width=2, dash='dot')
        ))

        # 零轴线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Zero")

        fig.update_layout(
            height=180,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=20, b=10),
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True, width='stretch')

    def _render_kdj_chart(self, df: pd.DataFrame):
        """KDJ(9,3,3) 副图"""
        if 'kdj_k' not in df.columns:
            st.caption("KDJ: 数据不足")
            return

        fig = make_subplots(
            rows=1, cols=1,
            shared_xaxes=True,
            specs=[[{"secondary_y": False}]]
        )

        # K/D/J线（专业配色）
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['kdj_k'],
            mode='lines', name='K',
            line=dict(color='purple', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['kdj_d'],
            mode='lines', name='D',
            line=dict(color='pink', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['kdj_j'],
            mode='lines', name='J',
            line=dict(color='yellow', width=2, dash='dot')
        ))

        # 超买超卖区（灰色背景）
        fig.add_hrect(y0=80, y1=100, fillcolor="red", opacity=0.1, layer="below", line_width=0)
        fig.add_hrect(y0=0, y1=20, fillcolor="green", opacity=0.1, layer="below", line_width=0)

        fig.update_layout(
            height=180,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=20, b=10),
            hovermode='x unified',
            yaxis=dict(range=[0, 100])
        )
        st.plotly_chart(fig, use_container_width=True, width='stretch')
