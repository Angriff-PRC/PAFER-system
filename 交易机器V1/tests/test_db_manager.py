### ✅ 最后交付：`tests/test_db_manager.py`

# tests/test_db_manager.py
import pytest
import os
from core.database.db_manager import DBManager

def test_db_init_and_save():
    # 清理测试DB
    if os.path.exists("data/pafar_trades.db"):
        os.remove("data/pafar_trades.db")

    db = DBManager()
    record = {
        'trade_id': 'TEST_001',
        'side': 'buy',
        'open_time': '2024-01-01T00:00:00',
        'open_price': 3000.0,
        'close_time': '2024-01-01T00:15:00',
        'close_price': 3010.0,
        'pnl': 10.0,
        'fee': 0.006,
        'net_pnl': 9.994,
        'balance_after': 109.994,
        'reason': 'PAFER Bullish Resonance',
        'is_virtual': True
    }
    db.save_virtual_trade(record)

    # 验证读取
    trades = db.get_recent_trades(limit=1)
    assert len(trades) == 1
    assert trades[0]['trade_id'] == 'TEST_001'
    assert trades[0]['net_pnl'] == '9.994'

    print("✅ DBManager test passed")

if __name__ == "__main__":
    test_db_init_and_save()
