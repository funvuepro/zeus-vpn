from fastapi import FastAPI

from bot.database.session import AsyncSessionLocal


def create_app(session_factory=None) -> FastAPI:
    app = FastAPI()
    app.state.session_factory = session_factory or AsyncSessionLocal

    from bot.webhooks.cryptobot import router as crypto_router
    from bot.webhooks.lava import router as lava_router
    from bot.webhooks.freekassa import router as freekassa_router
    from bot.webhooks.subscription import router as sub_router

    app.include_router(crypto_router)
    app.include_router(lava_router)
    app.include_router(freekassa_router)
    app.include_router(sub_router)

    return app


app = create_app()
