"""供 Spring Boot Docker 内部调用的每日热门生成接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from third.news_focus import NewsFocusGenerationError, generate_news_focus, refresh_news_focus_catalog


class GenerateNewsFocusRequest(BaseModel):
    recent_fingerprints: list[str] = Field(default_factory=list, alias="recentFingerprints")
    hours: int = Field(default=24, ge=1, le=72)


def create_news_focus_router() -> APIRouter:
    """这个函数创建不暴露到浏览器的内部生成路由。"""
    router = APIRouter(tags=["internal-news-focus"])

    @router.post("/internal/news-focus/generate")
    async def generate(request: GenerateNewsFocusRequest) -> dict[str, Any]:
        try:
            return await generate_news_focus(request.recent_fingerprints, request.hours)
        except NewsFocusGenerationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"每日热门生成失败：{str(exc)[:300]}") from exc

    @router.post("/internal/news-focus/sources/refresh")
    async def refresh_sources() -> dict[str, Any]:
        try:
            return await refresh_news_focus_catalog()
        except NewsFocusGenerationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"每日热门来源刷新失败：{str(exc)[:300]}") from exc

    return router
