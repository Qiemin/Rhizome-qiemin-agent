import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# config.py 位于：项目根目录/src/agent_lab/config.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    model: str
    api_key: str = field(repr=False)
    base_url: str
    proxy: str | None
    database_url: str | None = field(default=None, repr=False)


def required_env(name: str) -> str:
    """读取必须填写的环境变量。"""
    value = os.getenv(name, "").strip()

    if not value:
        raise ValueError(f"请在 .env 中填写 {name}")

    return value


def load_settings() -> Settings:
    # 已存在的系统环境变量优先于 .env
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    return Settings(
        model=required_env("OPENAI_MODEL"),
        api_key=required_env("OPENAI_API_KEY"),
        base_url=(
            os.getenv("OPENAI_BASE_URL", "").strip()
            or "https://api.openai.com/v1"
        ),
        proxy=os.getenv("AGENT_PROXY", "").strip() or None,
        database_url=os.getenv("DATABASE_URL", "").strip() or None,
    )


def load_database_url() -> str:
    """独立读取数据库配置；建表不需要模型密钥。"""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    database_url = required_env("DATABASE_URL")
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise ValueError("DATABASE_URL 必须使用 postgresql:// 或 postgres://")
    return database_url
