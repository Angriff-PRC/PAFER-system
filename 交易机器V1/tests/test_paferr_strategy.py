def test_paferr_signal_generation():
    import pandas as pd
    import numpy as np
    from core.strategy.paferr_strategy import PAFERStrategy

    # 构造强多头数据
    dates = pd.date_range('2024-01-01', periods=100, freq='15T')
    prices = np.linspace(3000, 3200, 100) + np.random.normal(0, 2, 100)
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices - 1,
        'high': prices + 2,
        'low': prices - 2,
        'close': prices,
        'volume': np.random.randint(100, 500, 100)
    })

    strategy = PAFERStrategy()
    signal = strategy.generate_signal(df)
    assert signal['action'] in ['buy', 'sell', 'hold']
    print("✅ Strategy test passed:", signal['action'])
