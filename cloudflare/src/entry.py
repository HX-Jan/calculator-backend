"""Cloudflare Python Workers entrypoint; local uvicorn keeps using app.main."""

from workers import asgi

from app.cloudflare import app

Default = asgi.entrypoint(app)
