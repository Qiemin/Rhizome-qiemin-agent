from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import Client

from ..config import load_settings
from ..graph.builder import build_graph
from ..llm.factory import create_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()

    if not settings.database_url:
        raise ValueError("请配置 DATABASE_URL")

    with Client(proxy=settings.proxy, timeout=60) as client:
        model = create_model(settings, client)
        graph = build_graph(model)

        app.state.graph = graph
        app.state.database_url = settings.database_url

        yield
