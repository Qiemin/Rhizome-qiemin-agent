from fastapi import Request


def get_graph(request: Request):
    return request.app.state.graph

def get_database_url(request: Request) -> str:
    return request.app.state.database_url
