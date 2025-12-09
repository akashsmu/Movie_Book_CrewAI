import datetime
import functools
import os
from time import time
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Any, Dict, List, Optional
from tmdbv3api import TMDb, Movie, Search
from serpapi import GoogleSearch
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import urllib.parse

# Define input schemas
class MovieSearchInput(BaseModel):
    query: str = Field(description="Search query for movies")
    year: Optional[int] = Field(None, description="Release year filter")
    genre: Optional[str] = Field(None, description="Genre filter")

class MovieDetailsInput(BaseModel):
    movie_id: int = Field(description="TMDB movie ID")

class BookSearchInput(BaseModel):
    query: str = Field(description="Search query for books")
    genre: Optional[str] = Field(None, description="Genre filter")

class BookDetailsInput(BaseModel):
    book_id: str = Field(description="Google Books volume ID")

class SimilarTitlesInput(BaseModel):
    title: str = Field(description="Title to find similar media for")
    media_type: str = Field(description="Type of media: 'movie' or 'book'")

class NewsSearchInput(BaseModel):
    query: str = Field(description="Search query for news")

class TrendingMediaInput(BaseModel):
    media_type: str = Field(description="Type of media: 'movie' or 'book'")

# Simple in-memory cache for API responses
_api_cache: Dict[str, Any] = {}

# Module logger
logger = logging.getLogger(__name__)


# Shared HTTP session with retries and connection pooling
_session = requests.Session()
_retry = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
_adapter = HTTPAdapter(max_retries=_retry, pool_connections=10, pool_maxsize=10)
_session.mount('https://', _adapter)
_session.mount('http://', _adapter)

def cache_api_call(ttl: int = 300):  # 5 minute cache
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            # If this is a bound method, drop `self` from the args when forming the key
            key_args = args[1:] if (len(args) > 0 and hasattr(args[0], '__class__')) else args
            cache_key = f"{func.__name__}:{str(key_args)}:{str(kwargs)}"

            # Check cache
            if cache_key in _api_cache:
                cache_time, result = _api_cache[cache_key]
                if time.time() - cache_time < ttl:
                    logger.debug(f"cache_api_call: HIT {cache_key}")
                    return result
                else:
                    logger.debug(f"cache_api_call: STALE {cache_key}")
            else:
                logger.debug(f"cache_api_call: MISS {cache_key}")

            # Call function and cache result
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            logger.debug(f"cache_api_call: CALL {func.__name__} took {duration:.3f}s")
            _api_cache[cache_key] = (time.time(), result)
            return result
        return wrapper
    return decorator


# Movie Search Tool - FIXED VERSION
class MovieSearchTool(BaseTool):
    name: str = "search_movies"
    description: str = "Search for movies using TMDB API"
    args_schema: type[BaseModel] = MovieSearchInput
    
    @cache_api_call(ttl=300)  # Cache results for 5 minutes
    def _run(self, query: str, year: Optional[int] = None, genre: Optional[str] = None) -> str:
        try:
            # Initialize TMDB inside _run method
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return "TMDB API key not configured. Please set TMDB_API_KEY in your environment variables."
            
            base_url = "https://api.themoviedb.org/3"
            search_url = f"{base_url}/search/movie"
            
            params = {
                'api_key': api_key,
                'query': str(query),
                'language': 'en-US',
                'page': 1
            }

            if year:
                params['year'] = year
                
            logger.debug(f"MovieSearchTool._run: searching movies with params: {params}")
            
            # Perform search (use pooled session)
            start = time()
            response = _session.get(search_url, params=params, timeout=10)
            duration = time() - start
            logger.debug(f"MovieSearchTool._run: TMDB responded status={getattr(response,'status_code',None)} in {duration:.3f}s")
            if response.status_code != 200:
                return self._get_fallback_movies(query, genre, f"API error: {response.status_code}")
            
            data = response.json()
            results = data.get('results', [])
            movies = []
            
            for movie in results[:5]:
                movie_details = self._get_basic_movie_details(movie)
                if movie_details:
                    movies.append(movie_details)
            
            if not movies:
                return f"No movies found for query: '{query}'"
            
            formatted_results = []
            for movie in movies:
                formatted_results.append(
                    f"Title: {movie['title']} ({movie['year']})\n"
                    f"Rating: {movie['rating']}/10\n"
                    f"Genre: {movie['genre']}\n"
                    f"Description: {movie['description']}\n"
                    f"ID: {movie['id']}"
                )
            
            return "\n---\n".join(formatted_results)
            
        except Exception as e:
            return f"Error searching movies: {str(e)}"

    def _get_basic_movie_details(self, movie) -> Optional[Dict]:
        try:
            # Get genre names from genre IDs
            genre_names = []
            if hasattr(movie, 'genre_ids') and movie.genre_ids:
                genre_map = {
                    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
                    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
                    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
                    9648: "Mystery", 10749: "Romance", 878: "Science Fiction",
                    10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western"
                }
                for genre_id in movie.genre_ids[:3]:
                    if genre_id in genre_map:
                        genre_names.append(genre_map[genre_id])
            
            # Safely get release year
            release_year = 'N/A'
            if hasattr(movie, 'release_date') and movie.release_date:
                try:
                    release_year = str(movie.release_date)[:4]  # Convert to string first
                except:
                    release_year = 'N/A'
            
            return {
                'id': getattr(movie, 'id', 'N/A'),
                'title': getattr(movie, 'title', 'Unknown Title'),
                'year': release_year,
                'rating': round(movie.vote_average, 1) if hasattr(movie, 'vote_average') and movie.vote_average else 'N/A',
                'genre': ', '.join(genre_names) if genre_names else 'Unknown',
                'description': getattr(movie, 'overview', 'No description available'),
                'image_url': f"https://image.tmdb.org/t/p/w500{movie.poster_path}" if hasattr(movie, 'poster_path') and movie.poster_path else None
            }
        except Exception as e:
            print(f"Error getting basic movie details: {e}")
            return None

# Movie Details Tool
class MovieDetailsTool(BaseTool):
    name: str = "get_movie_details"
    description: str = "Get detailed information about a specific movie"
    args_schema: type[BaseModel] = MovieDetailsInput
    
    @cache_api_call(ttl=3600)
    def _run(self, movie_id: int) -> str:
        try:
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return "TMDB API key not configured. Please set TMDB_API_KEY in your environment variables."
            
            # Use direct HTTP API call
            base_url = "https://api.themoviedb.org/3"
            movie_url = f"{base_url}/movie/{movie_id}"
            
            params = {
                'api_key': api_key,
                'language': 'en-US',
                'append_to_response': 'credits'
            }
            
            logger.debug(f"MovieDetailsTool._run: getting details for movie_id={movie_id}")
            start = time()
            response = _session.get(movie_url, params=params, timeout=10)
            duration = time() - start
            logger.debug(f"MovieDetailsTool._run: TMDB responded status={getattr(response,'status_code',None)} in {duration:.3f}s")
            
            if response.status_code != 200:
                return f"Error fetching movie details: {response.status_code}"
            
            movie_data = response.json()
            
            # Parse the data safely
            title = movie_data.get('title', 'Unknown Title')
            release_date = movie_data.get('release_date', '')
            release_year = release_date[:4] if release_date else 'N/A'
            rating = round(movie_data.get('vote_average', 0), 1)
            
            # Get genres
            genres = [genre.get('name', '') for genre in movie_data.get('genres', [])[:3]]
            genre_str = ', '.join([g for g in genres if g])
            
            description = movie_data.get('overview', 'No description available')
            runtime = movie_data.get('runtime', 0)
            duration = f"{runtime} min" if runtime else 'N/A'
            
            # Get cast
            cast = movie_data.get('credits', {}).get('cast', [])
            cast_names = [actor.get('name', '') for actor in cast[:3]]
            cast_str = ', '.join([c for c in cast_names if c])
            
            return (
                f"Title: {title} ({release_year})\n"
                f"Rating: {rating}/10\n"
                f"Genre: {genre_str if genre_str else 'Unknown'}\n"
                f"Duration: {duration}\n"
                f"Description: {description}\n"
                f"Cast: {cast_str if cast_str else 'N/A'}"
            )
            
        except Exception as e:
            return f"Error getting movie details: {str(e)}"

# Popular Movies Tool
class PopularMoviesTool(BaseTool):
    name: str = "get_popular_movies"
    description: str = "Get currently popular movies using direct API calls"
    
    @cache_api_call(ttl=3600)
    def _run(self, genre: Optional[str] = None) -> str:
        try:
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return "TMDB API key not configured. Using fallback popular movies."
            
            # Use direct HTTP API call
            base_url = "https://api.themoviedb.org/3"
            popular_url = f"{base_url}/movie/popular"
            
            params = {
                'api_key': api_key,
                'language': 'en-US',
                'page': 1
            }
            
            logger.debug("PopularMoviesTool._run: getting popular movies via direct API")
            start = time()
            response = _session.get(popular_url, params=params, timeout=10)
            duration = time() - start
            logger.debug(f"PopularMoviesTool._run: TMDB responded status={getattr(response,'status_code',None)} in {duration:.3f}s")
            
            if response.status_code != 200:
                return "Error fetching popular movies. Using fallback data."
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                return "No popular movies found. Using fallback data."
            
            movies = []
            for movie_data in results[:5]:
                movie_details = self._parse_movie_data(movie_data)
                if movie_details:
                    # Filter by genre if specified
                    if not genre or genre.lower() in movie_details['genre'].lower():
                        movies.append(movie_details)
            
            if not movies:
                return "No popular movies match the specified genre."
            
            formatted_results = []
            for movie in movies:
                formatted_results.append(
                    f"Title: {movie['title']} ({movie['year']})\n"
                    f"Rating: {movie['rating']}/10\n"
                    f"Genre: {movie['genre']}\n"
                    f"Description: {movie['description']}\n"
                    f"Image: {movie['image_url']}"
                )
            
            return "Popular Movies:\n" + "\n---\n".join(formatted_results)
            
        except Exception as e:
            return f"Error getting popular movies: {str(e)}. Using fallback data."

    def _parse_movie_data(self, movie_data: Dict) -> Optional[Dict]:
        """Parse movie data from TMDB API response"""
        try:
            genre_map = {
                28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
                80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
                14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
                9648: "Mystery", 10749: "Romance", 878: "Science Fiction",
                10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western"
            }
            
            genre_names = []
            for genre_id in movie_data.get('genre_ids', [])[:3]:
                if genre_id in genre_map:
                    genre_names.append(genre_map[genre_id])
            
            release_date = movie_data.get('release_date', '')
            release_year = release_date[:4] if release_date else 'N/A'
            
            return {
                'title': movie_data.get('title', 'Unknown Title'),
                'year': release_year,
                'rating': round(movie_data.get('vote_average', 0), 1),
                'genre': ', '.join(genre_names) if genre_names else 'Unknown',
                'description': movie_data.get('overview', 'No description available'),
                'image_url': f"https://image.tmdb.org/t/p/w500{movie_data.get('poster_path')}" if movie_data.get('poster_path') else None
            }
        except Exception as e:
            print(f"Error parsing movie data: {e}")
            return None
        

# Book Search Tool
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
                
            # Use simple string query without URL encoding - let requests handle it
            params = {
                'q': query,  # requests will handle encoding
                'maxResults': 8,
                'printType': 'books',
                'key': api_key
            }
            
            logger.debug(f"BookSearchTool._run: searching books q={query}")
            start = time()
            response = _session.get('https://www.googleapis.com/books/v1/volumes', params=params, timeout=10)
            duration = time() - start
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
                    f"Title: {book['title']}\n"
                    f"Author(s): {', '.join(book['authors'])}\n"
                    f"Published: {book['published_year']}\n"
                    f"Genre: {book['genre']}\n"
                    f"Rating: {book['rating']}/5\n"
                    f"Description: {book['description'][:200]}..."
                )
            
            return "\n---\n".join(formatted_results)
            
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
                'rating': volume_info.get('averageRating', 'N/A'),
                'image_url': volume_info.get('imageLinks', {}).get('thumbnail'),
            }
        except Exception as e:
            print(f"Error parsing book data: {e}")
            return None

# Book Details Tool
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
            start = time()
            response = _session.get(f'https://www.googleapis.com/books/v1/volumes/{book_id}', timeout=10)
            duration = time() - start
            logger.debug(f"BookDetailsTool._run: Google Books responded status={getattr(response,'status_code',None)} in {duration:.3f}s")
            response.raise_for_status()
            data = response.json()
            book_info = self._parse_book_data(data)
            
            if not book_info:
                return "Book details not found."
            
            return (
                f"Title: {book_info['title']}\n"
                f"Author(s): {', '.join(book_info['authors'])}\n"
                f"Published: {book_info['published_year']}\n"
                f"Genre: {book_info['genre']}\n"
                f"Rating: {book_info['rating']}/5\n"
                f"Pages: {book_info.get('page_count', 'N/A')}\n"
                f"Publisher: {book_info.get('publisher', 'Unknown')}\n"
                f"Description: {book_info['description']}"
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
                'rating': volume_info.get('averageRating', 'N/A'),
                'page_count': volume_info.get('pageCount'),
                'publisher': volume_info.get('publisher', 'Unknown'),
                'image_url': volume_info.get('imageLinks', {}).get('thumbnail'),
            }
        except Exception as e:
            print(f"Error parsing book data: {e}")
            return None

# Similar Titles Tool
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
            
            return f"Similar {media_type}s to '{title}':\n" + "\n".join([f"• {title}" for title in similar_titles])
            
        except Exception as e:
            return f"Error finding similar titles: {str(e)}"

# News Search Tool
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
                    f"Title: {result.get('title', 'N/A')}\n"
                    f"Source: {source_name}\n"
                    f"Date: {result.get('date', 'N/A')}\n"
                    f"Snippet: {result.get('snippet', 'N/A')[:100]}..."
                )
            
            return "Recent News:\n" + "\n---\n".join(news_items)
            
        except Exception as e:
            return f"Error searching news: {str(e)}"

# Trending Media Tool
class TrendingMediaTool(BaseTool):
    name: str = "search_trending_media"
    description: str = "Search for trending movies or books"
    args_schema: type[BaseModel] = TrendingMediaInput
    
    def _run(self, media_type: str = "movie") -> str:
        try:
            api_key = os.getenv('SERPAPI_KEY')
            if not api_key:
                return "SerpAPI key not configured. Please set SERPAPI_KEY in your environment variables."
                
            query = f"trending {media_type}s {datetime.datetime.year}" if media_type == "movie" else f"best selling books {datetime.datetime.year}"
            
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
                    trending_items.append(f"• {title}\n  {snippet[:100]}...")
            
            if not trending_items:
                return f"No trending {media_type}s found."
            
            return f"Currently Trending {media_type.title()}s:\n" + "\n".join(trending_items)
            
        except Exception as e:
            return f"Error searching trending media: {str(e)}"

# Create tool instances
movie_search_tool = MovieSearchTool()
movie_details_tool = MovieDetailsTool()
popular_movies_tool = PopularMoviesTool()
book_search_tool = BookSearchTool()
book_details_tool = BookDetailsTool()
similar_titles_tool = SimilarTitlesTool()
news_search_tool = NewsSearchTool()
trending_media_tool = TrendingMediaTool()

# Export tools
movie_tools = [movie_search_tool, movie_details_tool, popular_movies_tool]
book_tools = [book_search_tool, book_details_tool]
search_tools = [similar_titles_tool, news_search_tool, trending_media_tool]