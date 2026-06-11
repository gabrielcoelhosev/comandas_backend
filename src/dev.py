import os

import uvicorn


def main() -> None:
    os.environ.setdefault("DB_SGDB", "sqlite")
    os.environ.setdefault("DB_NAME", "apiDatabase")

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=["src"],
    )
