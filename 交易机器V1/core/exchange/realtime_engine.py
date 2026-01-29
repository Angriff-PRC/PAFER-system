# core/exchange/realtime_engine.py
import threading
import time
import json
import websocket
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Any
from utils.logger import get_logger

logger = get_logger(__name__)

class RealtimeEngine:
    def __init__(self):
        self.ws = None
        self.is_connected = False
        self.kline_buffer = {}  # {timeframe: [kline_list]}
        self.callbacks = {"kline": []}
        self._stop_event = threading.Event()

    def connect(self):
        """连接火币 WebSocket（公共行情，无需API密钥）"""
        url = "wss://api.huobi.pro/ws"
        try:
            self.ws = websocket.WebSocketApp(
                url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            # 启动 WebSocket 线程
            wst = threading.Thread(target=self.ws.run_forever, daemon=True)
            wst.start()
            logger.info("✅ WebSocket connected to Huobi public feed")
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")

    def _on_open(self, ws):
        self.is_connected = True
        # 订阅 ETH/USDT 15m K线（可扩展多周期）
        sub_msg = {
            "sub": "market.ethusdt.kline.15min",
            "id": "id1"
        }
        ws.send(json.dumps(sub_msg))
        logger.info("📡 Subscribed to market.ethusdt.kline.15min")

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'ping' in data:
                # 心跳响应
                ws.send(json.dumps({"pong": data['ping']}))
                return
            if 'ch' in data and 'kline' in data['ch']:
                k = data['tick']
                timeframe = data['ch'].split('.')[-1]  # '15min'
                # 转换为标准格式
                df_row = {
                    'timestamp': datetime.fromtimestamp(k['id']),
                    'open': float(k['open']),
                    'high': float(k['high']),
                    'low': float(k['low']),
                    'close': float(k['close']),
                    'volume': float(k['vol'])
                }
                # 存入缓冲区（只存最新100根）
                if timeframe not in self.kline_buffer:
                    self.kline_buffer[timeframe] = []
                self.kline_buffer[timeframe].append(df_row)
                if len(self.kline_buffer[timeframe]) > 100:
                    self.kline_buffer[timeframe] = self.kline_buffer[timeframe][-100:]

                # 触发回调（供UI更新）
                for cb in self.callbacks["kline"]:
                    cb(timeframe, df_row)

        except Exception as e:
            logger.warning(f"⚠️  Invalid kline message: {e}")

    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.is_connected = False
        logger.warning("WebSocket closed")

    def subscribe_kline_callback(self, callback: Callable[[str, Dict], None]):
        """注册K线更新回调（UI层调用）"""
        self.callbacks["kline"].append(callback)

    def get_latest_klines(self, timeframe: str = "15min", limit: int = 100) -> pd.DataFrame:
        """获取当前缓冲区中的K线（供首次渲染）"""
        if timeframe not in self.kline_buffer:
            return pd.DataFrame()
        rows = self.kline_buffer[timeframe][-limit:]
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).sort_values('timestamp').reset_index(drop=True)

    def start_background_polling(self):
        """后台线程：定期检查虚拟交易新记录（用于实时更新UI）"""
        def poll_loop():
            from core.database.db_manager import DBManager
            db = DBManager()
            last_count = 0
            while not self._stop_event.is_set():
                try:
                    # 查询虚拟交易总数
                    conn = db._get_connection()
                    c = conn.cursor()
                    c.execute("SELECT COUNT(*) FROM trades WHERE is_virtual = 1")
                    count = c.fetchone()[0]
                    conn.close()
                    if count > last_count:
                        last_count = count
                        # 触发UI刷新事件（通过st.session_state标记）
                        import streamlit as st
                        if "virtual_updated_at" not in st.session_state:
                            st.session_state.virtual_updated_at = time.time()
                        else:
                            st.session_state.virtual_updated_at = time.time()
                except Exception as e:
                    logger.warning(f"DB poll error: {e}")
                time.sleep(5)  # 每5秒检查一次

        thread = threading.Thread(target=poll_loop, daemon=True)
        thread.start()

# 全局单例
_realtime_engine = None

def get_realtime_engine() -> RealtimeEngine:
    global _realtime_engine
    if _realtime_engine is None:
        _realtime_engine = RealtimeEngine()
        _realtime_engine.connect()
        _realtime_engine.start_background_polling()
    return _realtime_engine
