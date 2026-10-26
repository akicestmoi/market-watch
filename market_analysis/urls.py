"""HTTP routes under /analysis/ for recap, chat, and article cache."""

from django.urls import path

from market_analysis.views.analysis_cache import GetArticleAnalysisCacheView
from market_analysis.views.llm_chat import AnalysisChatView
from market_analysis.views.market_analysis import (
    GenerateDailyRecapView,
    GetDailyRecapView,
)

urlpatterns = [
    path("recap", GetDailyRecapView.as_view()),
    path("recap/generate", GenerateDailyRecapView.as_view()),
    path("chat", AnalysisChatView.as_view()),
    path("article-cache", GetArticleAnalysisCacheView.as_view()),
]
