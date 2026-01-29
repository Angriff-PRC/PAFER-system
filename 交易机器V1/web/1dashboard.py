# web/dashboard.py
import streamlit as st
import pandas as pd   # ← 新增
import numpy as np     # ← 新增
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from core.strategy.paferr_strategy import PAFERStrategy
from core.exchange.huobi_executor import TradeExecutor
from core.database.db_manager import DBManager
from utils.logger import get_logger
from config.settings import Config

logger = get_logger(__name__)

st.set_page_config(page_title="PAFER Trading Tool", layout="wide")

# 初始化
db = DBManager()
strategy = PAFERStrategy(Config.STRATEGY)
executor = TradeExecutor(db, strategy)

# 页面选择
page = st.sidebar.radio("导航", ["📈 实盘操作", "🧪 虚拟优化"])

if page == "📈 实盘操作":
    st.title("PAFER 实盘操作中心")

    # 控制栏
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        live_switch = st.toggle("🟢 实盘开关", value=False, key="live_toggle")
        executor.toggle_live(live_switch)
    with col2:
        balance = executor.get_account_balance() if live_switch else 0.0
        st.metric("账户余额", f"{balance:.2f} USDT")
    with col3:
        st.metric("仓位状态", "空仓" if balance > 0 else "无持仓")
    with col4:
        risk_level = "⚠️ 高" if balance > 500 else "✅ 正常"
        st.metric("风险指示器", risk_level)

   
  # 参数面板
    st.subheader("⚙️ PAFER参数控制")
    col1, col2 = st.columns(2)
    with col1:
        drift_thresh = st.number_input(
        "力度阈值 (%)",
        min_value=5.0, max_value=30.0, value=Config.STRATEGY.momentum_threshold_pct,
        step=0.5, key="drift_thresh"
    )
    Config.STRATEGY.momentum_threshold_pct = drift_thresh

    with col2:
        max_k = st.number_input(
        "时效K线数",
        min_value=2, max_value=6, value=Config.STRATEGY.max_klines_for_resonance,
        step=1, key="max_k"
    )
    Config.STRATEGY.max_klines_for_resonance = max_k

    # ✅ 新增：风控参数滑块（stop_loss_buffer）
    st.subheader("🛡️ 风控参数")
    col1, col2 = st.columns(2)
    with col1:
        sl_buffer = st.slider(
        "止损缓冲比例 (%)",
        min_value=0.1, max_value=1.0, value=Config.RISK.stop_loss_buffer * 100,
        step=0.1, key="sl_buffer_slider"
    )
        Config.RISK.stop_loss_buffer = sl_buffer / 100.0
        st.caption(f"当前值: {Config.RISK.stop_loss_buffer:.3f} ({sl_buffer:.1f}%)")

    with col2:
        st.metric("当前MA45缓冲距离", f"±{sl_buffer:.1f}%")
        

    if st.button("🛑 紧急停止"):
        executor.toggle_live(False)
        st.warning("实盘已强制关闭！")

    # K线图（模拟数据）
    st.subheader("📊 实时K线图（演示）")
    # 生成模拟15m数据（实际应接入CCXT fetch_ohlcv）
    dates = pd.date_range(datetime.now() - timedelta(hours=24), periods=96, freq='15min')
    prices = 3000 + np.cumsum(np.random.randn(96) * 5)  # 模拟价格
    df_sim = pd.DataFrame({
        'timestamp': dates,
        'open': prices - 2,
        'high': prices + 3,
        'low': prices - 3,
        'close': prices,
        'volume': np.random.randint(100, 1000, 96)
    })

    # 生成信号
    signal = strategy.generate_signal(df_sim)
    st.write("当前信号:", signal or "无信号")

    # 绘图
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        subplot_titles=('K线图', 'MACD'))
    fig.add_trace(go.Candlestick(x=df_sim['timestamp'],
                                  open=df_sim['open'], high=df_sim['high'],
                                  low=df_sim['low'], close=df_sim['close']), row=1, col=1)
    if signal and 'stop_loss' in signal:
        fig.add_hline(y=signal['stop_loss'], line_dash="dash", line_color="red", annotation_text="SL", row=1, col=1)
        fig.add_hline(y=signal['take_profit'], line_dash="dash", line_color="green", annotation_text="TP", row=1, col=1)

    fig.add_trace(go.Scatter(x=df_sim['timestamp'], y=df_sim['macd_hist'], name='MACD Hist'), row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)

    # 性能仪表盘
    st.subheader("🎯 性能仪表盘")
    metrics = {"夏普比率": 1.8, "最大回撤": "12.3%", "胜率": "64%"}
    for k, v in metrics.items():
        st.metric(k, v)

    # 最近交易
    st.subheader("📋 最近交易记录")
    trades = db.get_recent_trades(limit=10)
    st.dataframe(trades)

elif page == "🧪 虚拟优化":
    st.title("PAFER 虚拟优化中心")

    st.subheader("🖥️ 虚拟账户状态")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("当前余额", f"{executor.virtual_balance:.2f} USDT")
    with col2:
        st.metric("优化代数", "127")
    with col3:
        st.metric("最佳参数", "MACD(3,18,6) + KDJ(9,3,3)")

    st.subheader("📈 优化过程可视化")
    # 模拟优化曲线
    gens = list(range(1, 101))
    scores = [0.5 + 0.3 * (1 - np.exp(-i/30)) + np.random.normal(0, 0.05) for i in gens]
    fig_opt = go.Figure()
    fig_opt.add_trace(go.Scatter(x=gens, y=scores, mode='lines+markers'))
    fig_opt.update_layout(title="收益适应度进化", xaxis_title="代数", yaxis_title="适应度")
    st.plotly_chart(fig_opt, use_container_width=True)

    st.subheader("📋 详细虚拟交易记录")
    virt_trades = db.get_virtual_trades(limit=20)
    st.dataframe(virt_trades)

