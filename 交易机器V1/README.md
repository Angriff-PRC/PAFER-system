# PAFER Trading Tool v1.0  
**基于你定义的PAFER体系（Prediction→Act→Feel→End_Income→Rollback）构建的生产级ETH/USDT永续合约交易系统**

## ✅ 核心特性
- **双模式引擎**：实盘（Huobi API） + 虚拟（高保真费率/滑点/爆仓模拟）  
- **PAFER原生实现**：三线共振检测、MACD飘逸/蓄力量化、KDJ斜率爆发识别、MA45踩实判定、时效性（≤4K）校验  
- **安全第一**：API密钥Fernet加密存储于本地SQLite，内存零明文，所有交易前多重风控  
- **自我进化**：贝叶斯优化 + 遗传算法混合调参，优化成果实时同步实盘  
- **企业级可观测性**：完整SQLite交易日志、结构化日志（含trade_id追踪）、Streamlit实时仪表盘  

## 🚀 快速启动
```bash
# 1. 克隆 & 安装
git clone https://github.com/your/pafar-tool.git
cd pafar-tool
pip install -r requirements.txt

# 2. 初始化（首次运行）
python -c "from utils.crypto import init_key_db; init_key_db()"

# 3. 配置API密钥（需加密！）
#   创建 .env 文件，按 .env.example 填写加密后的密钥

# 4. 启动Web界面
streamlit run pafar_main.py
