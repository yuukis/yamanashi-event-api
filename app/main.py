import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from .service import config, preload_archive_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(preload_archive_indexes)
    yield


app = FastAPI(
    title=config["metadata"]["title"],
    description=config["metadata"]["description"],
    version=config["metadata"]["version"],
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Imported for its side effect: registers all routes and mounts MCP onto
# `app`. Must come after `app` is constructed above, since routes.py
# imports `app` back from this module.
from . import routes  # noqa: E402

lambda_handler = Mangum(app)
