from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from cr_portal.api.router import router
from cr_portal.core.config import settings
from cr_portal.core.logging import configure_logging
from cr_portal.db.redis import close_redis, init_redis
from cr_portal.middleware.request_id import RequestIDMiddleware
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await init_redis()
    yield
    await close_redis()
app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, debug=settings.DEBUG, lifespan=lifespan)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET, same_site="lax", https_only=settings.ENVIRONMENT=="production")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
