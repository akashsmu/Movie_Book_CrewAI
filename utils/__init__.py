"""Utility modules for the Movie/Book Recommender application."""

from utils.http_session import get_http_session, _session
from utils.cache_decorator import cache_api_call

__all__ = ['get_http_session', '_session', 'cache_api_call']
