from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import settings
from app.api.routes import router as http_router
from app.api.room_routes import router as room_router
from app.api.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Process pool for multiprocessing rollouts
    app.state.process_pool = ProcessPoolExecutor(max_workers=settings.workers)

    # Global semaphore to avoid CPU meltdown if multiple games run bots
    app.state.bot_sem = asyncio.Semaphore(settings.max_concurrent_bot_thinking)

    yield

    app.state.process_pool.shutdown(wait=True, cancel_futures=True)


app = FastAPI(title="28 Game Server", debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(http_router)
app.include_router(room_router)
app.include_router(ws_router)
