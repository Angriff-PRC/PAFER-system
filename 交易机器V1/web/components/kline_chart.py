# utils/optimization.py
import numpy as np
import pandas as pd
from bayesian_optimization import BayesianOptimization
from deap import base, creator, tools, algorithms
from typing import Dict, Any, Callable, List, Tuple
from core.strategy.paferr_strategy import PAFERStrategy
from core.exchange.huobi_executor import TradeExecutor
from core.database.db_manager import DBManager
from config.settings import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class AutoOptimizer:
    def __init__(self, db_manager: DBManager, virtual_executor: TradeExecutor):
        self.db = db_manager
        self.executor = virtual_executor
        self.strategy = virtual_executor.strategy
        self.best_score = -np.inf
        self.best_config = None

    def _objective_function(self, **params) -> float:
        """贝叶斯优化目标函数：在虚拟环境中运行N根K线，返回夏普比率"""
        # 更新策略参数
        for k, v in params.items():
            setattr(self.strategy.config, k, int(v) if k in ['macd_fast', 'macd_slow', 'macd_signal',
                                                              'kdj_period', 'kdj_smooth_k', 'kdj_smooth_d',
                                                              'ma_short', 'ma_mid', 'ma_long'] else float(v))

        # 模拟100根15m K线（实际应从CCXT fetch，此处简化）
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100, freq='15T')
        prices = 3000 + np.cumsum(np.random.randn(100) * 3)
        df_sim = pd.DataFrame({
            'timestamp': dates,
            'open': prices - 1,
            'high': prices + 2,
            'low': prices - 2,
            'close': prices,
            'volume': np.random.randint(100, 500, 100)
        })

        # 执行虚拟交易
        trades = []
        balance = 100.0
        for i in range(10, len(df_sim)):  # 跳过前10根（指标冷启动）
            window = df_sim.iloc[:i+1]
            signal = self.strategy.generate_signal(window)
            if signal and signal['action'] in ['buy', 'sell']:
                price = window['close'].iloc[-1]
                trade = self.executor.execute_virtual_trade(signal, price, window['timestamp'].iloc[-1])
                if 'pnl' in trade:
                    trades.append(trade)
                    balance = trade['balance_after']

        # 计算绩效指标
        if len(trades) < 5:
            return -1.0

        pnls = [t['net_pnl'] for t in trades]
        returns = np.array(pnls) / 100.0  # 基于100U初始资金
        if len(returns) == 0 or np.std(returns) == 0:
            return -1.0

        sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252*4)  # 年化（15m≈4*252）
        win_rate = len([p for p in pnls if p > 0]) / len(pnls)
        max_dd = self._calculate_max_drawdown([100] + [100 + sum(pnls[:i+1]) for i in range(len(pnls))])

        score = 0.5 * sharpe + 0.3 * win_rate - 0.2 * max_dd  # 综合打分
        logger.debug(f"Optimization trial: {params} → Sharpe={sharpe:.3f}, WinRate={win_rate:.3f}, Score={score:.3f}")

        # 保存到数据库
        config_id = self.db.save_strategy_config(params)
        self.db.save_optimization_result(0, config_id, {
            'fitness': score,
            'trade_count': len(trades),
            'win_rate': win_rate,
            'sharpe': sharpe,
            'max_drawdown': max_dd
        })

        if score > self.best_score:
            self.best_score = score
            self.best_config = params.copy()
            logger.info(f"🎉 New best config: {self.best_config} (Score: {score:.3f})")

        return score

    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """计算最大回撤"""
        peak = equity_curve[0]
        max_dd = 0.0
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def run_bayesian_opt(self, n_iter: int = 30):
        """贝叶斯优化主循环"""
        pbounds = {
            'macd_fast': (2, 5),
            'macd_slow': (15, 25),
            'macd_signal': (5, 9),
            'kdj_period': (7, 12),
            'kdj_smooth_k': (2, 5),
            'kdj_smooth_d': (2, 5),
            'ma_short': (3, 8),
            'ma_mid': (8, 15),
            'ma_long': (30, 60),
            'momentum_threshold_pct': (5.0, 25.0),
            'max_klines_for_resonance': (2.0, 6.0)
        }

        optimizer = BayesianOptimization(
            f=self._objective_function,
            pbounds=pbounds,
            random_state=42,
            verbose=2
        )
        optimizer.maximize(init_points=5, n_iter=n_iter)
        return optimizer.max

    def run_genetic_opt(self, n_gen: int = 20):
        """遗传算法优化（补充贝叶斯）"""
        # DEAP设置
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        creator.create("Individual", list, fitness=creator.FitnessMax)

        toolbox = base.Toolbox()
        toolbox.register("attr_macd_fast", np.random.randint, 2, 6)
        toolbox.register("attr_macd_slow", np.random.randint, 15, 26)
        toolbox.register("attr_macd_signal", np.random.randint, 5, 10)
        toolbox.register("attr_kdj_period", np.random.randint, 7, 13)
        toolbox.register("attr_kdj_smooth_k", np.random.randint, 2, 6)
        toolbox.register("attr_kdj_smooth_d", np.random.randint, 2, 6)
        toolbox.register("attr_ma_short", np.random.randint, 3, 9)
        toolbox.register("attr_ma_mid", np.random.randint, 8, 16)
        toolbox.register("attr_ma_long", np.random.randint, 30, 61)
        toolbox.register("attr_momentum", np.random.uniform, 5.0, 25.0)
        toolbox.register("attr_klines", np.random.uniform, 2.0, 6.0)

        toolbox.register("individual", tools.initCycle, creator.Individual,
                         (toolbox.attr_macd_fast, toolbox.attr_macd_slow, toolbox.attr_macd_signal,
                          toolbox.attr_kdj_period, toolbox.attr_kdj_smooth_k, toolbox.attr_kdj_smooth_d,
                          toolbox.attr_ma_short, toolbox.attr_ma_mid, toolbox.attr_ma_long,
                          toolbox.attr_momentum, toolbox.attr_klines), n=1)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        toolbox.register("evaluate", lambda ind: (self._objective_function(
            macd_fast=ind[0], macd_slow=ind[1], macd_signal=ind[2],
            kdj_period=ind[3], kdj_smooth_k=ind[4], kdj_smooth_d=ind[5],
            ma_short=ind[6], ma_mid=ind[7], ma_long=ind[8],
            momentum_threshold_pct=ind[9], max_klines_for_resonance=ind[10]
        ),))
        toolbox.register("mate", tools.cxBlend, alpha=0.5)
        toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=1, indpb=0.2)
        toolbox.register("select", tools.selTournament, tournsize=3)

        pop = toolbox.population(n=20)
        hof = tools.HallOfFame(1)
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("std", np.std)
        stats.register("min", np.min)
        stats.register("max", np.max)

        algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, ngen=n_gen,
                            halloffame=hof, verbose=True, stats=stats)
        return hof[0] if hof else None

    def run(self, method: str = "bayesian", **kwargs):
        """统一入口：支持贝叶斯/遗传/混合"""
        if method == "bayesian":
            result = self.run_bayesian_opt(**kwargs)
            return result["params"] if result else {}
        elif method == "genetic":
            result = self.run_genetic_opt(**kwargs)
            return dict(zip([
                'macd_fast', 'macd_slow', 'macd_signal',
                'kdj_period', 'kdj_smooth_k', 'kdj_smooth_d',
                'ma_short', 'ma_mid', 'ma_long',
                'momentum_threshold_pct', 'max_klines_for_resonance'
            ], result)) if result else {}
        else:  # hybrid
            bayes = self.run_bayesian_opt(n_iter=15)
            genetic = self.run_genetic_opt(n_gen=10)
            # 返回综合最优
            return bayes["params"] if bayes["target"] > (self._objective_function(**genetic) if genetic else -10) else genetic
