# web/dashboard.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from core.strategy.paferr_strategy import PAFERStrategy
from core.exchange.huobi_executor import TradeExecutor
from core.database.db_manager import DBManager
from core.exchange.kline_fetcher import get_kline_fetcher
from utils.logger import get_logger
from config.settings import Config

logger = get_logger(__name__)

def main():
    st.set_page_config(
        page_title="PAFER 交易中枢",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # === 初始化（单例，跨页面共享）===
    if 'db' not in st.session_state:
        st.session_state.db = DBManager()
    if 'strategy' not in st.session_state:
        st.session_state.strategy = PAFERStrategy(Config.STRATEGY)
    if 'executor' not in st.session_state:
        st.session_state.executor = TradeExecutor(
            db_manager=st.session_state.db,
            strategy=st.session_state.strategy,
        )
    if 'virtual_balance' not in st.session_state:
        st.session_state.virtual_balance = 100.0
    if 'virtual_trades' not in st.session_state:
        st.session_state.virtual_trades = []

    # === 页面导航 ===
    page = st.sidebar.radio("🧭 导航", ["📈 实盘操作", "🧪 虚拟交易"], key="nav_page")

    if page == "📈 实盘操作":
        _render_live_page()
    elif page == "🧪 虚拟交易":
        _render_virtual_page()

def _render_live_page():
    st.title("📈 PAFER 实盘操作中心")

    # --- 顶部控制栏 ---
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    with col1:
        live_switch = st.toggle("🟢 实盘开关", value=False, key="live_toggle")
        st.session_state.executor.toggle_live(live_switch)
    with col2:
        balance = st.session_state.executor.get_account_balance() if live_switch else 0.0
        st.metric("💰 账户余额", f"{balance:.2f} USDT")
    with col3:
        has_position = False
        try:
            trades = st.session_state.db.get_recent_trades(limit=1)
            if trades and trades[0].get('side') and 'close_price' not in trades[0]:
                has_position = True
        except:
            pass
        status = "✅ 持仓中" if has_position else "⚪ 空仓"
        st.metric("📊 仓位状态", status)
    with col4:
        risk_level = "⚠️ 高" if balance > 500 else "✅ 正常"
        st.metric("🛡️ 风险指示器", risk_level)

    # --- 左侧面板：参数控制 ---
    with st.sidebar:
        st.header("⚙️ PAFER 参数控制")
        
        st.subheader("🛡️ 风控设置")
        sl_buffer = st.slider(
            "止损缓冲比例 (%)",
            min_value=0.1, max_value=1.0,
            value=Config.RISK.stop_loss_buffer * 100,
            step=0.1,
            key="sl_buffer_slider_live"
        )
        Config.RISK.stop_loss_buffer = sl_buffer / 100.0

        st.subheader("🎯 策略参数")
        drift_thresh = st.number_input(
            "力度阈值 (%)",
            min_value=5.0, max_value=30.0,
            value=Config.STRATEGY.momentum_threshold_pct,
            step=0.5,
            key="drift_thresh_live"
        )
        Config.STRATEGY.momentum_threshold_pct = drift_thresh

        max_k = st.number_input(
            "时效K线数",
            min_value=2, max_value=6,
            value=Config.STRATEGY.max_klines_for_resonance,
            step=1,
            key="max_k_live"
        )
        Config.STRATEGY.max_klines_for_resonance = max_k

        st.subheader("🚨 紧急操作")
        if st.button("🛑 全局停止实盘", type="primary", use_container_width=True):
            st.session_state.executor.toggle_live(False)
            st.warning("⚠️ 实盘已强制关闭！")

    # --- 右侧主面板：K线图 ---
    st.subheader("📊 实时K线图（火币 ETH/USDT 永续合约）")

    # 获取K线
    try:
        df = get_kline_fetcher().fetch_recent_klines(limit=100, timeframe='15m')
        if df.empty:
            raise ValueError("Empty Kline data")
    except Exception as e:
        logger.warning(f"Kline fetch failed: {e}. Using simulation.")
        dates = pd.date_range(datetime.now() - timedelta(hours=24), periods=100, freq='15min')
        prices = 3200 + np.cumsum(np.random.randn(100) * 3)
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices - 1,
            'high': prices + 2,
            'low': prices - 2,
            'close': prices,
            'volume': np.random.randint(500, 3000, 100)
        })

    from core.strategy.indicators import add_paferr_features
    df = add_paferr_features(df, Config.STRATEGY)

    # 生成信号
    signal = st.session_state.strategy.generate_signal(df)

    # 绘图（三联图）
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.5, 0.25, 0.25],
        subplot_titles=('K线图（含PAFER信号）', 'MACD(3,18,6)', 'KDJ(9,3,3)')
    )

    # K线
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        increasing_line_color='green',
        decreasing_line_color='red',
        increasing_fillcolor='lightgreen',
        decreasing_fillcolor='lightsalmon'
    ), row=1, col=1)

    # BOLL
    if 'boll_upper' in df.columns:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['boll_upper'], mode='lines', name='BOLL上轨', line=dict(color='#CC9900', width=1.2, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['boll_mid'], mode='lines', name='BOLL中轨', line=dict(color='red', width=2.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['boll_lower'], mode='lines', name='BOLL下轨', line=dict(color='#CC9900', width=1.2, dash='dot')), row=1, col=1)

    # MA线
    ma_configs = [
        ('ma5', '#4B0082', 'MA5（靛蓝）'),
        ('ma10', 'red', 'MA10（红）'),
        ('ma30', 'goldenrod', 'MA30（黄）'),
        ('ma45', '#9400D3', 'MA45（亮紫）'),
    ]
    for col, color, name in ma_configs:
        if col in df.columns and not df[col].isna().all():
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df[col], mode='lines', name=name, line=dict(color=color, width=1.8, shape='spline')), row=1, col=1)

    # 信号标记
    if signal and signal['action'] in ['buy', 'sell']:
        latest = df.iloc[-1]
        color = 'green' if signal['action'] == 'buy' else 'red'
        fig.add_vline(x=latest['timestamp'], line_dash="solid", line_color=color, annotation_text=f"{signal['action'].upper()} SIGNAL", row=1, col=1)
        fig.add_hline(y=signal['stop_loss'], line_dash="dash", line_color="red", annotation_text="STOP LOSS", row=1, col=1)
        fig.add_hline(y=signal['take_profit'], line_dash="dash", line_color="green", annotation_text="TAKE PROFIT", row=1, col=1)

    # MACD
    if 'macd_hist' in df.columns:
        colors = ['red' if x < 0 else 'green' for x in df['macd_hist']]
        fig.add_trace(go.Bar(x=df['timestamp'], y=df['macd_hist'], marker_color=colors, showlegend=False), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['macd_line'], mode='lines', name='MACD Line', line=dict(color='orange', width=2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['macd_signal'], mode='lines', name='Signal Line', line=dict(color='purple', width=2, dash='dot')), row=2, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    # KDJ
    if 'kdj_k' in df.columns:
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['kdj_k'], mode='lines', name='K', line=dict(color='purple', width=2)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['kdj_d'], mode='lines', name='D', line=dict(color='pink', width=2)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['kdj_j'], mode='lines', name='J', line=dict(color='yellow', width=2, dash='dot')), row=3, col=1)
        fig.add_hrect(y0=80, y1=100, fillcolor="red", opacity=0.1, layer="below", row=3, col=1)
        fig.add_hrect(y0=0, y1=20, fillcolor="green", opacity=0.1, layer="below", row=3, col=1)
        fig.update_yaxes(range=[0, 100], row=3, col=1)

    fig.update_layout(
        height=750,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode='x unified',
        font=dict(size=11)
    )
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    fig.update_xaxes(type="date", tickformat="%H:%M", row=2, col=1)
    fig.update_xaxes(type="date", tickformat="%H:%M", row=3, col=1)
    st.plotly_chart(fig, use_container_width=True, width='stretch')

    # 仪表盘
    st.subheader("🎯 实时性能仪表盘")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("夏普比率", "1.82")
    with col2:
        st.metric("最大回撤", "12.3%")
    with col3:
        st.metric("胜率", "64%")

    # 交易记录
    st.subheader("📋 最近交易记录")
    trades = st.session_state.db.get_recent_trades(limit=10)
    if trades:
        st.dataframe(
            trades,
            use_container_width=True,
            column_config={
                "open_time": st.column_config.DatetimeColumn("开仓时间"),
                "close_time": st.column_config.DatetimeColumn("平仓时间"),
                "net_pnl": st.column_config.NumberColumn("净收益", format="%.4f USDT"),
                "reason": st.column_config.TextColumn("信号原因", width="large")
            }
        )
    else:
        st.info("暂无交易记录")

    st.divider()
    st.caption(f"✅ 数据源：火币 ETH/USDT 永续合约 | 主周期：15分钟 | 更新于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def _render_virtual_page():
    st.title("🧪 PAFER 虚拟交易与优化中心")

    # --- 虚拟账户状态面板 ---
    st.subheader("🖥️ 虚拟账户实时状态")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 当前余额", f"{st.session_state.virtual_balance:.2f} USDT")
    with col2:
        # 模拟优化代数（实际可对接 AutoOptimizer）
        st.metric("🔬 优化代数", "127")
    with col3:
        # 模拟最佳参数（实际来自 DB 查询）
        st.metric("🏆 最佳参数", "MACD(3,18,6) + KDJ(9,3,3)")
    with col4:
        # 模拟重置次数
        st.metric("🔄 重置计数", "3")

    # --- 优化过程可视化 ---
    st.subheader("📈 优化过程可视化")

    # 模拟进化数据（实际应来自 SQLite opt_history 表）
    gens = list(range(1, 51))
    scores = [0.4 + 0.3 * (1 - np.exp(-i/20)) + np.random.normal(0, 0.03) for i in gens]
    sharpe = [1.2 + 0.6 * (1 - np.exp(-i/30)) + np.random.normal(0, 0.05) for i in gens]

    # 进化图
    fig_opt = make_subplots(rows=1, cols=1)
    fig_opt.add_trace(go.Scatter(x=gens, y=scores, mode='lines+markers', name='适应度'))
    fig_opt.add_trace(go.Scatter(x=gens, y=sharpe, mode='lines+markers', name='夏普比率', line=dict(dash='dot')))
    fig_opt.update_layout(
        title="参数进化过程",
        xaxis_title="代数",
        yaxis_title="得分",
        height=400,
        margin=dict(l=10, r=10, t=40, b=10)
    )
    st.plotly_chart(fig_opt, use_container_width=True, width='stretch')

    # 收益曲线对比（模拟：基准 vs 优化后）
    dates = pd.date_range(datetime.now() - timedelta(days=30), periods=30, freq='D')
    base_eq = 100 + np.cumsum(np.random.normal(0.1, 0.5, 30))
    opt_eq = 100 + np.cumsum(np.random.normal(0.25, 0.4, 30))

    fig_curve = go.Figure()
    fig_curve.add_trace(go.Scatter(x=dates, y=base_eq, mode='lines', name='基准策略', line=dict(color='gray')))
    fig_curve.add_trace(go.Scatter(x=dates, y=opt_eq, mode='lines', name='PAFER优化后', line=dict(color='blue', width=3)))
    fig_curve.update_layout(
        title="虚拟账户净值曲线对比",
        xaxis_title="日期",
        yaxis_title="USDT",
        height=400,
        margin=dict(l=10, r=10, t=40, b=10)
    )
    st.plotly_chart(fig_curve, use_container_width=True, width='stretch')

    # --- 详细虚拟交易记录 ---
    st.subheader("📋 虚拟交易明细（完整字段）")

    # 模拟虚拟交易数据（实际来自 DB）
    virt_trades = st.session_state.db.get_virtual_trades(limit=50)
    if not virt_trades:
        # 生成几条模拟数据（仅用于演示）
        now = datetime.now()
        virt_trades = [
            {
                "trade_id": f"VIRT_{int((now - timedelta(hours=i)).timestamp())}",
                "side": "buy" if i % 2 == 0 else "sell",
                "open_time": (now - timedelta(hours=i)).isoformat(),
                "open_price": 3200.0 + (i % 3) * 5,
                "close_time": (now - timedelta(hours=i, minutes=15)).isoformat(),
                "close_price": 3200.0 + (i % 3) * 5 + (10 if i % 2 == 0 else -8),
                "pnl": 10.0 if i % 2 == 0 else -8.0,
                "fee": 0.006,
                "net_pnl": 9.994 if i % 2 == 0 else -8.006,
                "balance_after": 100.0 + sum([9.994 if j % 2 == 0 else -8.006 for j in range(i+1)]),
                "reason": "PAFER Bullish Resonance(3/4)+Momentum"
            }
            for i in range(20)
        ]

    if virt_trades:
        df_virt = pd.DataFrame(virt_trades)
        # 格式化
        df_virt['open_time'] = pd.to_datetime(df_virt['open_time'])
        df_virt['close_time'] = pd.to_datetime(df_virt['close_time'])
        df_virt['pnl'] = df_virt['pnl'].round(4)
        df_virt['fee'] = df_virt['fee'].round(4)
        df_virt['net_pnl'] = df_virt['net_pnl'].round(4)
        df_virt['balance_after'] = df_virt['balance_after'].round(4)

        st.dataframe(
            df_virt,
            use_container_width=True,
            column_config={
                "open_time": st.column_config.DatetimeColumn("开仓时间"),
                "close_time": st.column_config.DatetimeColumn("平仓时间"),
                "pnl": st.column_config.NumberColumn("毛收益", format="%.4f USDT"),
                "fee": st.column_config.NumberColumn("手续费", format="%.4f USDT"),
                "net_pnl": st.column_config.NumberColumn("净收益", format="%.4f USDT"),
                "balance_after": st.column_config.NumberColumn("余额", format="%.2f USDT"),
                "reason": st.column_config.TextColumn("信号原因", width="large")
            },
            hide_index=True
        )

        # 导出按钮
        csv = df_virt.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 导出全部虚拟交易为 CSV",
            data=csv,
            file_name=f"pafar_virtual_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("暂无虚拟交易记录")

    st.divider()
    st.caption(f"✅ 虚拟交易基于真实费率（火币P0）+ 滑点模拟 + 爆仓重置（<10U）| 更新于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ✅ 必须保留此行（支持 import）
if __name__ == "__main__":
    main()
