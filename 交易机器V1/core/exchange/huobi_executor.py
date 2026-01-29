# core/exchange/huobi_executor.py
import pandas as pd
from typing import Optional, Dict, Any
from config.settings import Config
from core.strategy.paferr_strategy import PAFERStrategy
from core.database.db_manager import DBManager
from utils.logger import get_logger
from utils.helpers import calculate_slippage
from core.exchange.huobi_client import HuobiClient

logger = get_logger(__name__)

class TradeExecutor:
    def __init__(self, db_manager: DBManager, strategy: PAFERStrategy, 
                 api_key_encrypted: bytes = None, api_secret_encrypted: bytes = None):
        self.db = db_manager
        self.strategy = strategy
        self.is_live = False
        self.client = None
        self.virtual_balance = 100.0  # USDT
        self.virtual_trades = []
        self.reset_virtual_account()

        if api_key_encrypted and api_secret_encrypted:
            from utils.crypto import decrypt_data
            api_key = decrypt_data(api_key_encrypted)
            api_secret = decrypt_data(api_secret_encrypted)
            self.client = HuobiClient(api_key, api_secret)
            logger.info("Huobi client initialized (live mode ready)")

    def reset_virtual_account(self):
        self.virtual_balance = 100.0
        self.virtual_trades = []
    '''
    def execute_virtual_trade(self, signal: Dict[str, Any], price: float, timestamp: pd.Timestamp) -> Dict[str, Any]:
        """虚拟成交：模拟滑点、手续费、爆仓"""
        if signal['action'] == 'hold':
            return {'status': 'ignored'}

        size_usd = min(50.0, self.virtual_balance * 0.8)  # 80%仓位
        fee = size_usd * Config.EXCHANGE.fee_rate_taker
        slippage = calculate_slippage(price, 'market')
        exec_price = price * (1 + slippage) if signal['action'] == 'buy' else price * (1 - slippage)

        # 模拟止损/止盈触发（简化）
        pnl = 0.0
        if signal['action'] == 'buy':
            if exec_price <= signal['stop_loss']:
                pnl = -size_usd * (exec_price - signal['stop_loss']) / exec_price - fee
            elif exec_price >= signal['take_profit']:
                pnl = size_usd * (exec_price - signal['take_profit']) / exec_price - fee
            else:
                pnl = 0.0
        else:
            if exec_price >= signal['stop_loss']:
                pnl = -size_usd * (exec_price - signal['stop_loss']) / exec_price - fee
            elif exec_price <= signal['take_profit']:
                pnl = size_usd * (signal['take_profit'] - exec_price) / exec_price - fee
            else:
                pnl = 0.0

        new_balance = self.virtual_balance + pnl
        is_bankrupt = new_balance < 10.0
        if is_bankrupt:
            logger.warning("Virtual account bankrupt! Resetting to 100 USDT")
            self.reset_virtual_account()
            new_balance = 100.0

        trade = {
            'trade_id': f"VIRT_{int(timestamp.timestamp())}",
            'side': signal['action'],
            'open_time': timestamp.isoformat(),
            'open_price': exec_price,
            'close_time': timestamp.isoformat(),
            'close_price': exec_price,
            'pnl': pnl,
            'fee': fee,
            'net_pnl': pnl - fee,
            'balance_after': new_balance,
            'reason': signal['reason']
        }
        self.virtual_trades.append(trade)
        self.db.save_virtual_trade(trade)
        self.virtual_balance = new_balance
        return trade
        '''
    # core/exchange/huobi_executor.py （替换 execute_virtual_trade 方法）

    def execute_virtual_trade(self, signal: Dict[str, Any], price: float, timestamp: pd.Timestamp) -> Dict[str, Any]:
        """✅ 强化虚拟成交：确保写入DB + 日志 + 防空指针"""
        if signal['action'] == 'hold':
            return {'status': 'ignored'}

        try:
            size_usd = min(50.0, self.virtual_balance * 0.8)
            fee = size_usd * Config.EXCHANGE.fee_rate_taker
            slippage = calculate_slippage(price, 'market')
            exec_price = price * (1 + slippage) if signal['action'] == 'buy' else price * (1 - slippage)

            # 模拟盈亏（简化）
            pnl = 0.0
            if signal['action'] == 'buy':
                if exec_price <= signal['stop_loss']:
                    pnl = -size_usd * (exec_price - signal['stop_loss']) / exec_price - fee
                elif exec_price >= signal['take_profit']:
                    pnl = size_usd * (exec_price - signal['take_profit']) / exec_price - fee
            else:
                if exec_price >= signal['stop_loss']:
                    pnl = -size_usd * (exec_price - signal['stop_loss']) / exec_price - fee
                elif exec_price <= signal['take_profit']:
                    pnl = size_usd * (signal['take_profit'] - exec_price) / exec_price - fee

            new_balance = self.virtual_balance + pnl
            is_bankrupt = new_balance < 10.0
            if is_bankrupt:
                logger.warning("💸 Virtual account bankrupt! Resetting to 100 USDT")
                self.reset_virtual_account()
                new_balance = 100.0

            # ✅ 构造 trade dict（确保所有字段存在）
            trade = {
                'trade_id': f"VIRT_{int(timestamp.timestamp())}",
                'side': signal['action'],
                'open_time': timestamp.isoformat(),
                'open_price': round(exec_price, 4),
                'close_time': timestamp.isoformat(),  # 虚拟单立即平仓
                'close_price': round(exec_price, 4),
                'pnl': round(pnl, 6),
                'fee': round(fee, 6),
                'net_pnl': round(pnl - fee, 6),
                'balance_after': round(new_balance, 4),
                'reason': signal['reason']
            }

            # ✅ 写入数据库（使用增强版 save_virtual_trade）
            self.db.save_virtual_trade(trade)
            logger.info(f"📊 Virtual trade executed: {trade['side']} {trade['pnl']:.4f} USDT → Balance {trade['balance_after']:.2f}")

            self.virtual_balance = new_balance
            self.virtual_trades.append(trade)
            return trade

        except Exception as e:
            logger.error(f"❌ Virtual trade execution failed: {e}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    def execute_live_trade(self, signal: Dict[str, Any], price: float, timestamp: pd.Timestamp) -> Dict[str, Any]:
        """实盘下单（带完整风控）"""
        if not self.is_live or not self.client:
            return {'status': 'disabled'}

        try:
            # 风控检查
            size_usd = min(50.0, self.get_account_balance() * 0.8)
            if not self.client.check_risk_before_trade(signal['action'], size_usd, price, signal['stop_loss']):
                return {'status': 'risk_rejected'}

            # 设置杠杆
            self.client.set_leverage(signal['leverage'])

            # 下单
            order = self.client.exchange.create_order(
                symbol=self.client.symbol,
                type='market',
                side=signal['action'],
                amount=size_usd / price,
                params={'reduceOnly': False}
            )
            logger.info(f"Live order placed: {order['id']} {signal['action']} {size_usd} USD")

            return {
                'status': 'success',
                'order_id': order['id'],
                'exec_price': order['price'],
                'size_usd': size_usd
            }
        except Exception as e:
            logger.error(f"Live execution failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def get_account_balance(self) -> float:
        """获取账户余额（实盘）"""
        if not self.is_live:
            return 0.0
        try:
            balance = self.client.exchange.fetch_balance()
            return balance['USDT']['free']
        except:
            return 0.0

    def toggle_live(self, enable: bool):
        self.is_live = enable
        logger.info(f"Live trading {'ENABLED' if enable else 'DISABLED'}")
