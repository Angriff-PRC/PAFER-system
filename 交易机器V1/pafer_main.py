#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAFER Trading Tool — Main Entry Point
Supports:
  --mode=full      : Launch Streamlit dashboard (default)
  --mode=optimize  : Run Bayesian + Genetic optimization in background
  --port=8501      : Custom Streamlit port (only for full mode)
"""

import argparse
import os
import sys
import signal
import time
from pathlib import Path

# 🔑 强制将项目根目录加入 Python 路径（Windows 中文路径安全）
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# --- 日志配置（早于任何导入）---
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("PAFER.MAIN")

def setup_signal_handlers():
    """注册 Ctrl+C 优雅退出"""
    def signal_handler(signum, frame):
        logger.info("🛑 Received SIGINT. Shutting down gracefully...")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

def run_dashboard(port: int = 8501):
    """启动 Streamlit Web 界面"""
    logger.info(f"Launching Streamlit dashboard on http://localhost:{port}")
    try:
        # 使用 streamlit.cli 启动（避免 subprocess.Popen 的跨平台问题）
        import streamlit.web.cli as stcli
        sys.argv = ["streamlit", "run", str(ROOT_DIR / "web" / "dashboard.py"), "--server.port", str(port)]
        sys.exit(stcli.main())
    except Exception as e:
        logger.error(f"❌ Failed to start Streamlit: {e}")
        raise

def run_optimizer():
    """启动后台优化引擎（贝叶斯 + 遗传混合）"""
    logger.info("🔬 Starting AutoOptimizer (Bayesian + Genetic Hybrid)...")
    
    # 延迟导入（避免 Streamlit 相关模块污染优化进程）
    from core.database.db_manager import DBManager
    from core.exchange.huobi_executor import TradeExecutor
    from core.strategy.paferr_strategy import PAFERStrategy
    from utils.optimization import AutoOptimizer

    # 初始化依赖（轻量级）
    db = DBManager()
    strategy = PAFERStrategy()
    executor = TradeExecutor(db, strategy)  # 虚拟模式，不依赖 API 密钥
    optimizer = AutoOptimizer(db, executor)

    # 运行混合优化（先贝叶斯快速收敛，再遗传精细搜索）
    try:
        logger.info("⏳ Phase 1: Bayesian Optimization (30 iterations)...")
        bayes_result = optimizer.run(method="bayesian", n_iter=30)
        
        logger.info("⏳ Phase 2: Genetic Algorithm (20 generations)...")
        genetic_result = optimizer.run(method="genetic", n_gen=20)
        
        # 保存最优结果
        best = bayes_result if (
            bayes_result and 
            'target' in bayes_result and 
            bayes_result['target'] > (optimizer._objective_function(**genetic_result) if genetic_result else -10)
        ) else genetic_result

        if best:
            logger.info(f"🏆 Optimization completed. Best config: {best}")
            # 同步到全局策略（供 future full mode 使用）
            for k, v in best.items():
                setattr(strategy.config, k, int(v) if isinstance(v, (int, float)) and k not in ['momentum_threshold_pct', 'max_klines_for_resonance'] else float(v))
            logger.info("✅ Best config applied to PAFERStrategy")
        else:
            logger.warning("⚠️  No valid config found during optimization.")

    except KeyboardInterrupt:
        logger.info("⏹️  Optimization interrupted by user.")
    except Exception as e:
        logger.error(f"💥 Optimization crashed: {e}", exc_info=True)
    finally:
        logger.info("✅ Optimizer shutdown complete.")

def main():
    parser = argparse.ArgumentParser(description="PAFER Trading Tool Launcher")
    parser.add_argument(
        "--mode",
        type=str,
        default="full",
        choices=["full", "optimize"],
        help="Run mode: 'full' (Web UI) or 'optimize' (background parameter tuning)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Streamlit server port (only used in 'full' mode)"
    )
    args = parser.parse_args()

    # 设置信号处理器
    setup_signal_handlers()

    logger.info(f"🚀 PAFER Trading Tool v2.0 starting in '{args.mode}' mode")
    logger.info(f"📁 Project root: {ROOT_DIR}")

    if args.mode == "full":
        run_dashboard(args.port)
    elif args.mode == "optimize":
        run_optimizer()
    else:
        logger.error(f"❌ Unknown mode: {args.mode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
 