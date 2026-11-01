"""Start the local Agent API server."""

import uvicorn


def main() -> int:
    uvicorn.run(
        "agent.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
    return 0
