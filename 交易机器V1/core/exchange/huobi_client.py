# core/exchange/huobi_client.py
import ccxt
from config.settings import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class HuobiClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.exchange = ccxt.huobipro({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'},
            'urls': {
                'api': 'https://api.hbdm.com' if not testnet else 'https://api.btcgateway.pro'
            }
        })
        self.symbol = Config.EXCHANGE.symbol
        self.leverage_range = Config.EXCHANGE.leverage_range

    def set_leverage(self, leverage: int):
        try:
            self.exchange.fapiPrivate_post_position_side_dual({'dualSidePosition': 'false'})
            self.exchange.fapiPrivate_post_leverage({'symbol': self.symbol.replace('/', ''), 'leverage': leverage})
        except Exception as e:
            logger.warning(f"Failed to set leverage {leverage}: {e}")

    def check_risk_before_trade(self, side: str, size_usd: float, price: float, sl_price: float) -> bool:
        """多重风控检查"""
        max_loss_usd = size_usd * (abs(price - sl_price) / price)
        max_loss_pct = (max_loss_usd / size_usd) * 100
        if max_loss_pct > Config.RISK.max_loss_percent:
            logger.error(f"Risk check failed: loss {max_loss_pct:.2f}% > {Config.RISK.max_loss_percent}%")
            return False
        if size_usd > Config.RISK.max_position_size_usd:
            logger.error(f"Size {size_usd} > max {Config.RISK.max_position_size_usd}")
            return False
        return True
