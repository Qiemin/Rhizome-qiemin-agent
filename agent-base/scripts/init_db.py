"""初始化 PostgreSQL 消息表；不调用模型或创建数据库。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.config import load_database_url


def main() -> int:
    try:
        database_url = load_database_url()
    except ValueError as exc:
        print(f"数据库配置错误：{exc}")
        return 1

    try:
        from agent.storage.storage import init_db

        init_db(database_url)
    except ModuleNotFoundError as exc:
        if exc.name != "psycopg":
            raise
        print("缺少 PostgreSQL 驱动，请运行 .\\.venv\\Scripts\\python.exe -m pip install -e .")
        return 1
    except Exception as exc:
        # 连接地址可能包含密码；不打印原始异常或连接字符串。
        print(f"数据库初始化失败：{type(exc).__name__}")
        print("请检查 PostgreSQL 服务、DATABASE_URL、目标数据库和建表权限。")
        return 1

    print("表已就绪")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
