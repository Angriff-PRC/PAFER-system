# web/components/kline_chart.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Optional, Dict, Any

def render_kline_chart(df: pd.DataFrame, signal: Optional[Dict[str, Any]] = None, 
                       title: str = "ETH/USDT 15m") -> go.Figure:
    """
    渲染带PAFER信号的K线图
    支持：MACD柱、MA线、止损/止盈线、共振标记
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(f'{title} - K线', 'MACD(3,18,6)'),
        row_heights=[0.7, 0.3]
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
    ), row=1, col=1)

    # MA线
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ma5'], mode='lines', name='MA5', line=dict(width=1, dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ma10'], mode='lines', name='MA10', line=dict(width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ma45'], mode='lines', name='MA45', line=dict(width=2, color='black')), row=1, col=1)

    # 信号标注
    if signal and signal['action'] in ['buy', 'sell']:
        latest = df.iloc[-1]
        color = 'green' if signal['action'] == 'buy' else 'red'
        fig.add_vline(x=latest['timestamp'], line_dash="dash", line_color=color, annotation_text=f"{signal['action'].upper()} Signal", row=1, col=1)
        fig.add_hline(y=signal['stop_loss'], line_dash="dash", line_color="red", annotation_text="SL", row=1, col=1)
        fig.add_hline(y=signal['take_profit'], line_dash="dash", line_color="green", annotation_text="TP", row=1, col=1)

    # MACD
    fig.add_trace(go.Bar(x=df['timestamp'], y=df['macd_hist'], name='MACD Hist', marker_color='blue'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['macd_line'], mode='lines', name='MACD Line', line=dict(color='orange')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['macd_signal'], mode='lines', name='Signal Line', line=dict(color='purple')), row=2, col=1)

    fig.update_layout(
        height=700,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        hovermode='x unified'
    )
    return fig
