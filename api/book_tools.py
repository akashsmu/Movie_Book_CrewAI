"""Book-related API tools for Google Books."""

import os
import time
import logging
import requests
from typing import Dict, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from utils.cache_decorator import cache_api_call
from utils.http_session import _session

# Module logger
logger = logging.getLogger(__name__)


# Input schemas
class BookSearchInput(BaseModel):
    query: str = Field(description="Search query for books")
    genre: Optional[str] = Field(None, description="Genre filter")


class BookDetailsInput(BaseModel):
    book_id: str = Field(description="Google Books volume ID")


class BookSearchTool(BaseTool):
    name: str = "search_books"
    description: str = "Search for books using Google Books API"
    args_schema: type[BaseModel] = BookSearchInput
    
    @cache_api_call(ttl=600)
    def _run(self, query: str, genre: Optional[str] = None) -> str:
        try:
            api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
            if not api_key:
                return "Google Books API key not configured. Please set GOOGLE_BOOKS_API_KEY in your environment variables."
                
            params = {
                'q': query,
                'maxResults': 8,
                'printType': 'books',
                'key': api_key
            }
            
            logger.debug(f"BookSearchTool._run: searching books q={query}")
            start = time.time()
            response = _session.get('https://www.googleapis.com/books/v1/volumes', params=params, timeout=10)
            duration = time.time() - start
            logger.debug(f"BookSearchTool._run: Google Books responded status={getattr(response,'status_code',None)} in {duration:.3f}s")
            response.raise_for_status()
            data = response.json()
            
            books = []
            for item in data.get('items', [])[:5]:
                book_info = self._parse_book_data(item)
                if book_info:
                    if not genre or genre.lower() in book_info.get('genre', '').lower():
                        books.append(book_info)
            
            if not books:
                return f"No books found for query: '{query}'"
            
            formatted_results = []
            for book in books:
                formatted_results.append(
                    f"Title: {book['title']}\\n"
                    f"Author(s): {', '.join(book['authors'])}\\n"
                    f"Published: {book['published_year']}\\n"
                    f"Genre: {book['genre']}\\n"
                    f"Rating: {book['rating']}/5\\n"
                    f"Description: {book['description'][:200]}...\\n"
                    f"Image: {book['image_url']}\\n"
                    f"Preview: {book['preview_url']}"
                )
            
            return "\\n---\\n".join(formatted_results)
            
        except requests.exceptions.RequestException as e:
            return f"Network error searching books: {str(e)}"
        except Exception as e:
            return f"Error searching books: {str(e)}"

    def _parse_book_data(self, book_data: Dict) -> Optional[Dict]:
        try:
            volume_info = book_data.get('volumeInfo', {})
            
            return {
                'title': volume_info.get('title', 'Unknown Title'),
                'authors': volume_info.get('authors', ['Unknown Author']),
                'published_year': volume_info.get('publishedDate', '')[:4] if volume_info.get('publishedDate') else 'N/A',
                'genre': ', '.join(volume_info.get('categories', ['General'])),
                'description': volume_info.get('description', 'No description available.')[:300],
                'rating': volume_info.get('averageRating') if volume_info.get('averageRating') is not None else 'N/A',
                'image_url': volume_info.get('imageLinks', {}).get('thumbnail', '').replace('http://', 'https://') if volume_info.get('imageLinks', {}).get('thumbnail') else None,
                'preview_url': volume_info.get('previewLink') or volume_info.get('infoLink'),
            }
        except Exception as e:
            print(f"Error parsing book data: {e}")
            return None


class BookDetailsTool(BaseTool):
    name: str = "get_book_details"
    description: str = "Get detailed information about a specific book"
    args_schema: type[BaseModel] = BookDetailsInput
    
    @cache_api_call(ttl=3600)
    def _run(self, book_id: str) -> str:
        try:
            api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
            if not api_key:
                return "Google Books API key not configured. Please set GOOGLE_BOOKS_API_KEY in your environment variables."
                
            logger.debug(f"BookDetailsTool._run: fetching book_id={book_id}")
            start = time.time()
            response = _session.get(f'https://www.googleapis.com/books/v1/volumes/{book_id}', timeout=10)
            duration = time.time() - start
            logger.debug(f"BookDetailsTool._run: Google Books responded status={getattr(response,'status_code',None)} in {duration:.3f}s")
            response.raise_for_status()
            data = response.json()
            book_info = self._parse_book_data(data)
            
            if not book_info:
                return "Book details not found."
            
            return (
                f"Title: {book_info['title']}\\n"
                f"Author(s): {', '.join(book_info['authors'])}\\n"
                f"Published: {book_info['published_year']}\\n"
                f"Genre: {book_info['genre']}\\n"
                f"Rating: {book_info['rating']}/5\\n"
                f"Pages: {book_info.get('page_count', 'N/A')}\\n"
                f"Publisher: {book_info.get('publisher', 'Unknown')}\\n"
                f"Description: {book_info['description']}\\n"
                f"Image: {book_info.get('image_url')}"
            )
        except requests.exceptions.RequestException as e:
            return f"Network error getting book details: {str(e)}"
        except Exception as e:
            return f"Error getting book details: {str(e)}"

    def _parse_book_data(self, book_data: Dict) -> Optional[Dict]:
        try:
            volume_info = book_data.get('volumeInfo', {})
            
            return {
                'title': volume_info.get('title', 'Unknown Title'),
                'authors': volume_info.get('authors', ['Unknown Author']),
                'published_year': volume_info.get('publishedDate', '')[:4] if volume_info.get('publishedDate') else 'N/A',
                'genre': ', '.join(volume_info.get('categories', ['General'])),
                'description': volume_info.get('description', 'No description available.'),
                'rating': round(volume_info.get('averageRating'), 1) if volume_info.get('averageRating') is not None else 'N/A',
                'page_count': volume_info.get('pageCount'),
                'publisher': volume_info.get('publisher', 'Unknown'),
                'image_url': volume_info.get('imageLinks', {}).get('thumbnail'),
            }
        except Exception as e:
            print(f"Error parsing book data: {e}")
            return None
