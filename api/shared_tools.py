"""Shared API tools for media search (similar titles, news, trending)."""

import datetime
import os
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from serpapi import GoogleSearch


# Input schemas
class SimilarTitlesInput(BaseModel):
    title: str = Field(description="Title to find similar media for")
    media_type: str = Field(description="Type of media: 'movie' or 'book'")


class NewsSearchInput(BaseModel):
    query: str = Field(description="Search query for news")


class TrendingMediaInput(BaseModel):
    media_type: str = Field(description="Type of media: 'movie' or 'book'")


class SimilarTitlesTool(BaseTool):
    name: str = "find_similar_titles"
    description: str = "Find similar movies or books using search"
    args_schema: type[BaseModel] = SimilarTitlesInput
    
    def _run(self, title: str, media_type: str) -> str:
        try:
            api_key = os.getenv('SERPAPI_KEY')
            if not api_key:
                return "SerpAPI key not configured. Please set SERPAPI_KEY in your environment variables."
                
            query = f"{media_type}s similar to {title}"
            
            params = {
                'q': query,
                'api_key': api_key,
                'engine': 'google',
                'gl': 'us',
                'hl': 'en'
            }
            
            search = GoogleSearch(params)
            results = search.get_dict()
            
            organic_results = results.get('organic_results', [])
            if not organic_results:
                return f"No similar {media_type}s found for '{title}'."
            
            similar_titles = []
            for result in organic_results[:5]:
                title_text = result.get('title', '')
                title_text = title_text.replace(' - Similar movies', '').replace(' - Similar books', '')
                if title_text and title_text not in similar_titles:
                    similar_titles.append(title_text)
            
            if not similar_titles:
                return f"No similar {media_type}s found for '{title}'."
            
            return f"Similar {media_type}s to '{title}':\\n" + "\\n".join([f"• {title}" for title in similar_titles])
            
        except Exception as e:
            return f"Error finding similar titles: {str(e)}"


class NewsSearchTool(BaseTool):
    name: str = "search_news"
    description: str = "Search for recent news and articles about media"
    args_schema: type[BaseModel] = NewsSearchInput
    
    def _run(self, query: str) -> str:
        try:
            api_key = os.getenv('SERPAPI_KEY')
            if not api_key:
                return "SerpAPI key not configured. Please set SERPAPI_KEY in your environment variables."
                
            params = {
                'q': query,
                'api_key': api_key,
                'engine': 'google',
                'gl': 'us',
                'hl': 'en',
                'tbm': 'nws'
            }
            
            search = GoogleSearch(params)
            results = search.get_dict()
            
            news_results = results.get('news_results', [])
            if not news_results:
                return f"No recent news found for query: '{query}'"
            
            news_items = []
            for result in news_results[:3]:
                source_info = result.get('source', {})
                source_name = source_info.get('name', 'N/A') if isinstance(source_info, dict) else 'N/A'
                
                news_items.append(
                    f"Title: {result.get('title', 'N/A')}\\n"
                    f"Source: {source_name}\\n"
                    f"Date: {result.get('date', 'N/A')}\\n"
                    f"Snippet: {result.get('snippet', 'N/A')[:100]}..."
                )
            
            return "Recent News:\\n" + "\\n---\\n".join(news_items)
            
        except Exception as e:
            return f"Error searching news: {str(e)}"


class TrendingMediaTool(BaseTool):
    name: str = "search_trending_media"
    description: str = "Search for trending movies or books"
    args_schema: type[BaseModel] = TrendingMediaInput
    
    def _run(self, media_type: str = "movie") -> str:
        try:
            api_key = os.getenv('SERPAPI_KEY')
            if not api_key:
                return "SerpAPI key not configured. Please set SERPAPI_KEY in your environment variables."
                
            query = f"trending {media_type}s {datetime.datetime.now().year}" if media_type == "movie" else f"best selling books {datetime.datetime.now().year}"
            
            params = {
                'q': query,
                'api_key': api_key,
                'engine': 'google',
                'gl': 'us',
                'hl': 'en'
            }
            
            search = GoogleSearch(params)
            results = search.get_dict()
            
            organic_results = results.get('organic_results', [])
            if not organic_results:
                return f"No trending {media_type}s found."
            
            trending_items = []
            for result in organic_results[:5]:
                title = result.get('title', '')
                snippet = result.get('snippet', '')
                if title and not title.startswith('People also ask'):
                    trending_items.append(f"• {title}\\n  {snippet[:100]}...")
            
            if not trending_items:
                return f"No trending {media_type}s found."
            
            return f"Currently Trending {media_type.title()}s:\\n" + "\\n".join(trending_items)
            
        except Exception as e:
            return f"Error searching trending media: {str(e)}"
