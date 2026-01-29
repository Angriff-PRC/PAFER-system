# utils/optimization.py
import numpy as np
import pandas as pd
from typing import Dict, Any, Callable, List, Tuple, Optional
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
        """贝叶斯优化目标函数：虚拟环境运行 + 夏普比率"""
        # 更新策略参数
        for k, v in params.items():
            if hasattr(self.strategy.config, k):
                setattr(self.strategy.config, k, int(v) if isinstance(v, (int, float)) and k not in [
                    'momentum_threshold_pct', 'max_klines_for_resonance'
                ] else float(v))

        # 模拟100根15m K线（真实场景应从 CCXT 获取）
        np.random.seed(hash(str(params)) % 1000000)
        dates = pd.date_range('2024-01-01', periods=100, freq='15min')
        prices = 3000 + np.cumsum(np.random.randn(100) * 3)
        df_sim = pd.DataFrame({
            'timestamp': dates,
            'open': prices - 1,
            'high': prices + 2,
            'low': prices - 2,
            'close': prices,
            'volume': np.random.randint(100, 500, 100)
        })

        # 执行虚拟交易（简化逻辑）
        trades = []
        balance = 100.0
        for i in range(10, len(df_sim)):  # 跳过冷启动
            window = df_sim.iloc[:i+1]
            signal = self.strategy.generate_signal(window)
            if signal and signal['action'] in ['buy', 'sell']:
                price = window['close'].iloc[-1]
                trade = self.executor.execute_virtual_trade(signal, price, window['timestamp'].iloc[-1])
                if 'pnl' in trade:
                    trades.append(trade)
                    balance = trade['balance_after']

        # 计算绩效（夏普为主）
        if len(trades) < 5:
            return -1.0

        pnls = [t['net_pnl'] for t in trades]
        returns = np.array(pnls) / 100.0
        if len(returns) == 0 or np.std(returns) == 0:
            return -1.0

        sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252*4)
        win_rate = len([p for p in pnls if p > 0]) / len(pnls)
        score = 0.7 * sharpe + 0.3 * win_rate  # 综合得分

        # 保存到数据库（轻量）
        try:
            config_id = self.db.save_strategy_config(params)
            self.db.save_optimization_result(0, config_id, {
                'fitness': score,
                'trade_count': len(trades),
                'win_rate': win_rate,
                'sharpe': sharpe,
                'max_drawdown': 0.0
            })
        except Exception as e:
            logger.warning(f"DB save failed: {e}")

        if score > self.best_score:
            self.best_score = score
            self.best_config = params.copy()
            logger.info(f"🏆 New best: {self.best_config} → Score={score:.3f}")

        return score

    def run_bayesian_opt(self, n_iter: int = 30):
        """贝叶斯优化（使用 bayesian-optimization 库）"""
        try:
            from bayesian_optimization import BayesianOptimization
        except ImportError:
            logger.error("❌ bayesian-optimization not installed. Run: pip install bayesian-optimization==1.4.3")
            return None

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
        """遗传算法优化（使用 deap）"""
        try:
            from deap import base, creator, tools, algorithms
        except ImportError:
            logger.error("❌ deap not installed. Run: pip install deap==1.4.1")
            return None

        # 定义适应度与个体
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        if not hasattr(creator, "Individual"):
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
        """统一入口：支持 'bayesian', 'genetic', 'hybrid'"""
        if method == "bayesian":
            result = self.run_bayesian_opt(**kwargs)
            return result["params"] if result else {}
        elif method == "genetic":
            result = self.run_genetic_opt(**kwargs)
            if result is None:
                return {}
            return dict(zip([
                'macd_fast', 'macd_slow', 'macd_signal',
                'kdj_period', 'kdj_smooth_k', 'kdj_smooth_d',
                'ma_short', 'ma_mid', 'ma_long',
                'momentum_threshold_pct', 'max_klines_for_resonance'
            ], result))
        else:  # hybrid
            bayes = self.run_bayesian_opt(n_iter=15)
            genetic = self.run_genetic_opt(n_gen=10)
            if bayes and genetic:
                bayes_score = bayes.get("target", -10)
                genetic_score = self._objective_function(**genetic) if genetic else -10
                return bayes["params"] if bayes_score > genetic_score else genetic
            return bayes["params"] if bayes else genetic
