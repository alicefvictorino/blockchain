"""Launcher da API para uso com scripts do Poetry."""

import os

import uvicorn


def main():
    """Sobe a API FastAPI com configuracao amigavel para desenvolvimento."""
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() in {"1", "true", "yes", "on"}

    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )
