"""每日热门的公开 RSS 收集、规则筛选与中文编辑模块。"""

from .service import NewsFocusGenerationError, generate_news_focus, refresh_news_focus_catalog

__all__ = ["NewsFocusGenerationError", "generate_news_focus", "refresh_news_focus_catalog"]
