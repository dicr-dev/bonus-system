from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
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


@app.middleware("http")
async def require_session(request, call_next):
    path = request.url.path
    public = (
        path.endswith("/health")
        or path.startswith("/api/v1/auth/login")
        or path.startswith("/api/v1/auth/bitrix/login")
        or path.startswith("/api/v1/auth/bitrix/callback")
        or path.startswith("/api/v1/auth/bitrix/install")
        or path.startswith("/api/v1/auth/bitrix/app")
    )
    if path.startswith("/api/v1/") and not public and not (
        request.session.get("user_id") or request.session.get("bitrix_user_id")
    ):
        return JSONResponse({"detail": "Authentication required"}, status_code=401)
    return await call_next(request)

app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET, same_site="lax", https_only=settings.ENVIRONMENT=="production")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
