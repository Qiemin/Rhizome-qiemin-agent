from httpx import Client
from langchain_openai import ChatOpenAI

from ..config import Settings


def create_model(
    setting: Settings,
    http_client: Client    
) -> ChatOpenAI:
    return ChatOpenAI(
        model=setting.model,
        api_key=setting.api_key,
        base_url=setting.base_url,
        use_responses_api=True,
        http_client=http_client,
        http_socket_options=(),
        timeout=60,
        max_retries=1,
    )

