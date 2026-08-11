from fastapi import FastAPI

from bot.database.session import AsyncSessionLocal


def create_app(session_factory=None) -> FastAPI:
    app = FastAPI()
    app.state.session_factory = session_factory or AsyncSessionLocal

    from bot.webhooks.yookassa import router as yookassa_router
    from bot.webhooks.subscription import router as sub_router

    app.include_router(yookassa_router)
    app.include_router(sub_router)

    return app


app = create_app()
