# __main__.py （项目根目录下）
import sys
from pathlib import Path

# ✅ 强制将根目录加入 sys.path（在任何 import 前！）
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ✅ 现在可以安全导入并启动
if __name__ == "__main__":
    from web.dashboard import main
    main()
