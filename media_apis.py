import os
import requests
from typing import Dict, List, Optional
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

# Movie Search Tool
class MovieSearchTool(BaseTool):
    name: str = "search_movies"
    description: str = "Search for movies using TMDB API"
    args_schema: type[BaseModel] = MovieSearchInput
    
    def _run(self, query: str, year: Optional[int] = None, genre: Optional[str] = None) -> str:
        try:
            # Initialize TMDB inside _run method
            tmdb = TMDb()
            tmdb.api_key = os.getenv('TMDB_API_KEY', 'your_tmdb_api_key_here')
            if not tmdb.api_key or tmdb.api_key == 'your_tmdb_api_key_here':
                return "TMDB API key not configured. Please set TMDB_API_KEY in your environment variables."
                
            tmdb.language = 'en'
            search = Search()
            
            search_params = {"query": query}
            if year:
                search_params["year"] = year
                
            results = search.movies(search_params)
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
            if hasattr(movie, 'genre_ids'):
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
            
            return {
                'id': movie.id,
                'title': movie.title,
                'year': movie.release_date[:4] if movie.release_date else 'N/A',
                'rating': round(movie.vote_average, 1) if movie.vote_average else 'N/A',
                'genre': ', '.join(genre_names) if genre_names else 'Unknown',
                'description': movie.overview or 'No description available'
            }
        except Exception as e:
            print(f"Error getting basic movie details: {e}")
            return None

# Movie Details Tool
class MovieDetailsTool(BaseTool):
    name: str = "get_movie_details"
    description: str = "Get detailed information about a specific movie"
    args_schema: type[BaseModel] = MovieDetailsInput
    
    def _run(self, movie_id: int) -> str:
        try:
            # Initialize TMDB inside _run method
            tmdb = TMDb()
            tmdb.api_key = os.getenv('TMDB_API_KEY', 'your_tmdb_api_key_here')
            if not tmdb.api_key or tmdb.api_key == 'your_tmdb_api_key_here':
                return "TMDB API key not configured. Please set TMDB_API_KEY in your environment variables."
                
            tmdb.language = 'en'
            movie_api = Movie()
            
            movie = movie_api.details(movie_id)
            
            details = {
                'title': movie.title,
                'year': movie.release_date[:4] if movie.release_date else 'N/A',
                'rating': round(movie.vote_average, 1) if movie.vote_average else 'N/A',
                'genre': ', '.join([genre.name for genre in movie.genres][:3]),
                'description': movie.overview or 'No description available',
                'duration': f"{movie.runtime} min" if movie.runtime else 'N/A',
                'cast': ', '.join([cast_member.name for cast_member in getattr(movie, 'casts', {}).get('cast', [])[:3]]) if hasattr(movie, 'casts') and movie.casts else 'N/A'
            }
            
            return (
                f"Title: {details['title']} ({details['year']})\n"
                f"Rating: {details['rating']}/10\n"
                f"Genre: {details['genre']}\n"
                f"Duration: {details['duration']}\n"
                f"Description: {details['description']}\n"
                f"Cast: {details['cast']}"
            )
        except Exception as e:
            return f"Error getting movie details: {str(e)}"

# Popular Movies Tool
class PopularMoviesTool(BaseTool):
    name: str = "get_popular_movies"
    description: str = "Get currently popular movies"
    
    def _run(self, genre: Optional[str] = None) -> str:
        try:
            # Initialize TMDB inside _run method
            tmdb = TMDb()
            tmdb.api_key = os.getenv('TMDB_API_KEY', 'your_tmdb_api_key_here')
            if not tmdb.api_key or tmdb.api_key == 'your_tmdb_api_key_here':
                return "TMDB API key not configured. Please set TMDB_API_KEY in your environment variables."
                
            tmdb.language = 'en'
            movie_api = Movie()
            
            popular = movie_api.popular()
            movies = []
            
            for movie in popular[:8]:
                basic_details = self._get_basic_movie_details(movie)
                if basic_details:
                    movies.append(basic_details)
                
                if len(movies) >= 5:
                    break
            
            if not movies:
                return "No popular movies found."
            
            formatted_results = []
            for movie in movies:
                formatted_results.append(
                    f"Title: {movie['title']} ({movie['year']})\n"
                    f"Rating: {movie['rating']}/10\n"
                    f"Genre: {movie['genre']}\n"
                    f"Description: {movie['description']}"
                )
            
            return "Popular Movies:\n" + "\n---\n".join(formatted_results)
            
        except Exception as e:
            return f"Error getting popular movies: {str(e)}"
    
    def _get_basic_movie_details(self, movie) -> Optional[Dict]:
        try:
            genre_names = []
            if hasattr(movie, 'genre_ids'):
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
            
            return {
                'title': movie.title,
                'year': movie.release_date[:4] if movie.release_date else 'N/A',
                'rating': round(movie.vote_average, 1) if movie.vote_average else 'N/A',
                'genre': ', '.join(genre_names) if genre_names else 'Unknown',
                'description': movie.overview or 'No description available'
            }
        except Exception as e:
            print(f"Error getting basic movie details: {e}")
            return None

# Book Search Tool
class BookSearchTool(BaseTool):
    name: str = "search_books"
    description: str = "Search for books using Google Books API"
    args_schema: type[BaseModel] = BookSearchInput
    
    def _run(self, query: str, genre: Optional[str] = None) -> str:
        try:
            api_key = os.getenv('GOOGLE_BOOKS_API_KEY', 'your_google_books_api_key_here')
            if not api_key or api_key == 'your_google_books_api_key_here':
                return "Google Books API key not configured. Please set GOOGLE_BOOKS_API_KEY in your environment variables."
                
            # URL encode the query
            encoded_query = urllib.parse.quote(query)
            
            params = {
                'q': encoded_query,
                'maxResults': 8,
                'printType': 'books',
                'key': api_key
            }
            
            response = requests.get('https://www.googleapis.com/books/v1/volumes', params=params, timeout=10)
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
                'description': volume_info.get('description', 'No description available.')[:300],  # Limit description length
                'rating': volume_info.get('averageRating', 'N/A'),
            }
        except Exception as e:
            print(f"Error parsing book data: {e}")
            return None

# Book Details Tool
class BookDetailsTool(BaseTool):
    name: str = "get_book_details"
    description: str = "Get detailed information about a specific book"
    args_schema: type[BaseModel] = BookDetailsInput
    
    def _run(self, book_id: str) -> str:
        try:
            api_key = os.getenv('GOOGLE_BOOKS_API_KEY', 'your_google_books_api_key_here')
            if not api_key or api_key == 'your_google_books_api_key_here':
                return "Google Books API key not configured. Please set GOOGLE_BOOKS_API_KEY in your environment variables."
                
            response = requests.get(f'https://www.googleapis.com/books/v1/volumes/{book_id}', timeout=10)
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
            api_key = os.getenv('SERPAPI_KEY', 'your_serpapi_key_here')
            if not api_key or api_key == 'your_serpapi_key_here':
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
            
            # Safely access the results
            organic_results = results.get('organic_results', [])
            if not organic_results:
                return f"No similar {media_type}s found for '{title}'."
            
            similar_titles = []
            for result in organic_results[:5]:
                title_text = result.get('title', '')
                # Clean up the title
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
            api_key = os.getenv('SERPAPI_KEY', 'your_serpapi_key_here')
            if not api_key or api_key == 'your_serpapi_key_here':
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
            
            # Safely access news results
            news_results = results.get('news_results', [])
            if not news_results:
                return f"No recent news found for query: '{query}'"
            
            news_items = []
            for result in news_results[:3]:
                # Safely access nested properties
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
            api_key = os.getenv('SERPAPI_KEY', 'your_serpapi_key_here')
            if not api_key or api_key == 'your_serpapi_key_here':
                return "SerpAPI key not configured. Please set SERPAPI_KEY in your environment variables."
                
            query = f"trending {media_type}s 2024" if media_type == "movie" else f"best selling books 2024"
            
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