from __future__ import annotations

import uvicorn

from bot.config import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        "bot.web.app:app",
        host=settings.web_admin_host,
        port=settings.web_admin_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
