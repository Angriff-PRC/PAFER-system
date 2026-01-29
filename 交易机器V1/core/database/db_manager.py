# core/database/db_manager.py
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.database.models import TradeRecord, VirtualTrade, StrategyConfigRecord, OptimizationHistory
from utils.logger import get_logger

logger = get_logger(__name__)

class DBManager:
    def __init__(self):
        # ✅ 关键：必须定义 self.db_path
        self.db_path = "data/pafar_trades.db"
        
        # ✅ 确保 data/ 目录存在
        Path("data").mkdir(exist_ok=True)
        
        # ✅ 初始化数据库表
        self.init_db()

    def init_db(self):
        """创建所有必需的数据表"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 交易记录表（实盘 + 虚拟共用）
        c.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                side TEXT NOT NULL,
                open_time TEXT NOT NULL,
                open_price REAL NOT NULL,
                close_time TEXT NOT NULL,
                close_price REAL NOT NULL,
                pnl REAL NOT NULL,
                fee REAL NOT NULL,
                net_pnl REAL NOT NULL,
                balance_after REAL NOT NULL,
                reason TEXT,
                is_virtual BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 策略配置历史表
        c.execute("""
            CREATE TABLE IF NOT EXISTS strategy_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_hash TEXT UNIQUE NOT NULL,
                config_json TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 优化历史表
        c.execute("""
            CREATE TABLE IF NOT EXISTS opt_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generation INTEGER NOT NULL,
                config_id INTEGER NOT NULL,
                fitness_score REAL NOT NULL,
                trade_count INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                sharpe_ratio REAL DEFAULT 0.0,
                max_drawdown REAL DEFAULT 0.0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(config_id) REFERENCES strategy_configs(id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Database initialized at {self.db_path}")

    def _get_connection(self):
        """安全获取数据库连接（带重试）"""
        try:
            return sqlite3.connect(self.db_path)
        except Exception as e:
            logger.error(f"❌ Failed to connect to DB: {e}")
            raise

    def save_trade(self, record: TradeRecord):
        """保存单笔交易（实盘或虚拟）"""
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("""
                INSERT OR REPLACE INTO trades 
                (trade_id, side, open_time, open_price, close_time, close_price, pnl, fee, net_pnl, balance_after, reason, is_virtual)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.trade_id,
                record.side,
                record.open_time,
                record.open_price,
                record.close_time,
                record.close_price,
                record.pnl,
                record.fee,
                record.net_pnl,
                record.balance_after,
                record.reason,
                record.is_virtual
            ))
            conn.commit()
            logger.debug(f"✅ Trade saved: {record.trade_id}")
        except Exception as e:
            logger.error(f"❌ Save trade failed: {e}")
            raise
        finally:
            conn.close()

    def save_virtual_trade(self, trade: dict):
        """✅ 安全保存虚拟交易（兼容旧版字典格式）"""
        from core.database.models import TradeRecord
        try:
            record = TradeRecord(
                trade_id=trade.get('trade_id', f"VIRT_{int(datetime.now().timestamp())}"),
                side=trade.get('side', 'buy'),
                open_time=trade.get('open_time', datetime.now().isoformat()),
                open_price=float(trade.get('open_price', 3000.0)),
                close_time=trade.get('close_time', datetime.now().isoformat()),
                close_price=float(trade.get('close_price', 3000.0)),
                pnl=float(trade.get('pnl', 0.0)),
                fee=float(trade.get('fee', 0.0)),
                net_pnl=float(trade.get('net_pnl', 0.0)),
                balance_after=float(trade.get('balance_after', 100.0)),
                reason=trade.get('reason', 'Virtual trade'),
                is_virtual=True
            )
            self.save_trade(record)
        except Exception as e:
            logger.error(f"❌ save_virtual_trade failed: {e}", exc_info=True)

    def get_recent_trades(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近交易（用于UI表格）"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        try:
            c.execute("""
                SELECT trade_id, side, open_time, open_price, close_price, 
                       ROUND(net_pnl, 4) as net_pnl, reason, 
                       CASE WHEN is_virtual THEN 'VIRTUAL' ELSE 'LIVE' END as mode
                FROM trades 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            rows = [dict(row) for row in c.fetchall()]
            return rows
        except Exception as e:
            logger.error(f"❌ get_recent_trades failed: {e}")
            return []
        finally:
            conn.close()

    def get_virtual_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取虚拟交易详情（全字段）"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        try:
            c.execute("""
                SELECT trade_id, side, open_time, open_price, close_time, close_price,
                       ROUND(pnl, 4) as pnl, ROUND(fee, 4) as fee, ROUND(net_pnl, 4) as net_pnl,
                       ROUND(balance_after, 4) as balance_after, reason
                FROM trades 
                WHERE is_virtual = 1 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            rows = [dict(row) for row in c.fetchall()]
            return rows
        except Exception as e:
            logger.error(f"❌ get_virtual_trades failed: {e}")
            return []
        finally:
            conn.close()

    def get_virtual_balance(self) -> float:
        """✅ 获取最新虚拟账户余额（从 trades 表查最新一笔）"""
        conn = self._get_connection()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT balance_after FROM trades 
                WHERE is_virtual = 1 
                ORDER BY created_at DESC LIMIT 1
            """)
            row = c.fetchone()
            return float(row[0]) if row else 100.0
        except Exception as e:
            logger.error(f"❌ get_virtual_balance failed: {e}")
            return 100.0
        finally:
            conn.close()

    def save_strategy_config(self, config_dict: dict) -> int:
        """保存策略配置（返回config_id）"""
        config_json = json.dumps(config_dict)
        config_hash = str(hash(config_json))
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO strategy_configs (config_hash, config_json, is_active)
                VALUES (?, ?, 1)
            """, (config_hash, config_json))
            config_id = c.lastrowid
            # 将旧配置设为非活跃
            c.execute("UPDATE strategy_configs SET is_active = 0 WHERE id != ?", (config_id,))
            conn.commit()
            return config_id
        except Exception as e:
            logger.error(f"❌ save_strategy_config failed: {e}")
            raise
        finally:
            conn.close()

    def save_optimization_result(self, gen: int, config_id: int, metrics: dict):
        """保存优化结果"""
        conn = self._get_connection()
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO opt_history 
                (generation, config_id, fitness_score, trade_count, win_rate, sharpe_ratio, max_drawdown)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                gen,
                config_id,
                metrics.get('fitness', 0.0),
                metrics.get('trade_count', 0),
                metrics.get('win_rate', 0.0),
                metrics.get('sharpe', 0.0),
                metrics.get('max_drawdown', 0.0)
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"❌ save_optimization_result failed: {e}")
            raise
        finally:
            conn.close()
