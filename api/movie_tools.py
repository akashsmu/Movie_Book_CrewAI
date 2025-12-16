"""Movie-related API tools for TMDB."""

import os
import time
import logging
import random
from typing import Dict, List, Optional, Union
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from utils.cache_decorator import cache_api_call
from utils.http_session import _session

# Module logger
logger = logging.getLogger(__name__)


# Input schemas
class MovieSearchInput(BaseModel):
    query: str = Field(description="Search query for movies")
    year: Optional[Union[int, str]] = Field(None, description="Release year filter")
    genre: Optional[str] = Field(None, description="Genre filter")


class MovieDetailsInput(BaseModel):
    movie_id: int = Field(description="TMDB movie ID")


class DiscoverMoviesInput(BaseModel):
    genre: str = Field(description="The genre to filter by (e.g., 'Action', 'Science Fiction')")
    min_rating: Optional[float] = Field(default=None, description="Minimum rating (0-10) to filter by")
    sort_by: Optional[str] = Field(default="popularity.desc", description="Sort order (default: popularity.desc)")


class MovieSearchTool(BaseTool):
    name: str = "search_movies"
    description: str = "Search for movies using TMDB API"
    args_schema: type[BaseModel] = MovieSearchInput
    
    @cache_api_call(ttl=300)
    def _run(self, query: str, year: Optional[Union[int, str]] = None, genre: Optional[str] = None) -> str:
        try:
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
                # Handle string 'None' or invalid strings safely
                if isinstance(year, str):
                    if year.lower() == 'none' or not year.strip():
                        year = None
                    elif year.isdigit():
                        year = int(year)
                    else:
                        try:
                            year = int(''.join(filter(str.isdigit, year)))
                        except:
                            year = None
                            
                if year:
                    params['year'] = year
                
            logger.debug(f"MovieSearchTool._run: searching movies with params: {params}")
            
            # Perform search
            start = time.time()
            response = _session.get(search_url, params=params, timeout=10)
            duration = time.time() - start
            logger.debug(f"MovieSearchTool._run: TMDB responded status={getattr(response,'status_code',None)} in {duration:.3f}s")
            
            if response.status_code != 200:
                return f"API error: {response.status_code}"
            
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
                    f"Title: {movie['title']} ({movie['year']})\\n"
                    f"Rating: {movie['rating']}/10\\n"
                    f"Genre: {movie['genre']}\\n"
                    f"Description: {movie['description']}\\n"
                    f"ID: {movie['id']}\\n"
                    f"Image: {movie['image_url']}\\n"
                    f"Trailer: {movie.get('trailer_url', 'N/A')}"
                )
            
            return "\\n---\\n".join(formatted_results)
            
        except Exception as e:
            return f"Error searching movies: {str(e)}"

    def _get_basic_movie_details(self, movie) -> Optional[Dict]:
        try:
            # Handle both dictionary and object
            def get_val(obj, key, default=None):
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            # Get genre names from genre IDs
            genre_names = []
            genre_ids = get_val(movie, 'genre_ids', [])
            if genre_ids:
                genre_map = {
                    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
                    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
                    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
                    9648: "Mystery", 10749: "Romance", 878: "Science Fiction",
                    10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western"
                }
                for genre_id in genre_ids[:3]:
                    if genre_id in genre_map:
                        genre_names.append(genre_map[genre_id])
            
            # Safely get release year
            release_date = get_val(movie, 'release_date')
            release_year = 'N/A'
            if release_date:
                try:
                    release_year = str(release_date)[:4]
                except:
                    release_year = 'N/A'
            
            poster_path = get_val(movie, 'poster_path')
            vote_average = get_val(movie, 'vote_average')
            
            return {
                'id': get_val(movie, 'id', 'N/A'),
                'title': get_val(movie, 'title', 'Unknown Title'),
                'year': release_year,
                'rating': round(vote_average, 1) if vote_average is not None else 'N/A',
                'genre': ', '.join(genre_names) if genre_names else 'Unknown',
                'description': get_val(movie, 'overview', 'No description available'),
                'image_url': f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None,
                'trailer_url': self._get_trailer_url(get_val(movie, 'id'))
            }
        except Exception as e:
            print(f"Error getting basic movie details: {e}")
            return None

    @cache_api_call(ttl=3600)
    def _get_trailer_url(self, movie_id: int) -> Optional[str]:
        """Fetch YouTube trailer URL for a movie"""
        try:
            if not movie_id or movie_id == 'N/A':
                return None
                
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return None
                
            url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos"
            params = {'api_key': api_key, 'language': 'en-US'}
            
            response = _session.get(url, params=params, timeout=5)
            if response.status_code == 200:
                results = response.json().get('results', [])
                for video in results:
                    if video.get('site') == 'YouTube' and video.get('type') == 'Trailer':
                        return f"https://www.youtube.com/watch?v={video.get('key')}"
            return None
        except Exception:
            return None


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
            
            base_url = "https://api.themoviedb.org/3"
            movie_url = f"{base_url}/movie/{movie_id}"
            
            params = {
                'api_key': api_key,
                'language': 'en-US',
                'append_to_response': 'credits,videos'
            }
            
            logger.debug(f"MovieDetailsTool._run: getting details for movie_id={movie_id}")
            start = time.time()
            response = _session.get(movie_url, params=params, timeout=10)
            duration = time.time() - start
            logger.debug(f"MovieDetailsTool._run: TMDB responded status={getattr(response,'status_code',None)} in {duration:.3f}s")
            
            if response.status_code != 200:
                return f"Error fetching movie details: {response.status_code}"
            
            movie_data = response.json()
            
            # Parse the data safely
            title = movie_data.get('title', 'Unknown Title')
            release_date = movie_data.get('release_date', '')
            release_year = release_date[:4] if release_date else 'N/A'
            vote_average = movie_data.get('vote_average')
            rating = round(vote_average, 1) if vote_average is not None else 'N/A'
            
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
            
            poster_path = movie_data.get('poster_path')
            image_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
            
            # Fetch trailer
            trailer_url = None
            videos = movie_data.get('videos', {}).get('results', [])
            for video in videos:
                if video.get('site') == 'YouTube' and video.get('type') == 'Trailer':
                    trailer_url = f"https://www.youtube.com/watch?v={video.get('key')}"
                    break

            return (
                f"Title: {title} ({release_year})\\n"
                f"Rating: {rating}/10\\n"
                f"Genre: {genre_str if genre_str else 'Unknown'}\\n"
                f"Duration: {duration}\\n"
                f"Description: {description}\\n"
                f"Cast: {cast_str if cast_str else 'N/A'}\\n"
                f"Image: {image_url}\\n"
                f"Trailer: {trailer_url if trailer_url else 'N/A'}"
            )
            
        except Exception as e:
            return f"Error getting movie details: {str(e)}"


class PopularMoviesTool(BaseTool):
    name: str = "get_popular_movies"
    description: str = "Get currently popular movies using direct API calls"
    
    @cache_api_call(ttl=3600)
    def _run(self, genre: Optional[str] = None) -> str:
        try:
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return "TMDB API key not configured. Using fallback popular movies."
            
            base_url = "https://api.themoviedb.org/3"
            popular_url = f"{base_url}/movie/popular"
            
            params = {
                'api_key': api_key,
                'language': 'en-US',
                'page': 1
            }
            
            logger.debug("PopularMoviesTool._run: getting popular movies via direct API")
            start = time.time()
            response = _session.get(popular_url, params=params, timeout=10)
            duration = time.time() - start
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
                    if not genre or genre.lower() in movie_details['genre'].lower():
                        movies.append(movie_details)
            
            if not movies:
                return "No popular movies match the specified genre."
            
            formatted_results = []
            for movie in movies:
                formatted_results.append(
                    f"Title: {movie['title']} ({movie['year']})\\n"
                    f"Rating: {movie['rating']}/10\\n"
                    f"Genre: {movie['genre']}\\n"
                    f"Description: {movie['description']}\\n"
                    f"Image: {movie['image_url']}\\n"
                    f"Trailer: {movie.get('trailer_url', 'N/A')}"
                )
            
            return "Popular Movies:\\n" + "\\n---\\n".join(formatted_results)
            
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
            
            vote_average = movie_data.get('vote_average')
            return {
                'title': movie_data.get('title', 'Unknown Title'),
                'year': release_year,
                'rating': round(vote_average, 1) if vote_average is not None else 'N/A',
                'genre': ', '.join(genre_names) if genre_names else 'Unknown',
                'description': movie_data.get('overview', 'No description available'),
                'image_url': f"https://image.tmdb.org/t/p/w500{movie_data.get('poster_path')}" if movie_data.get('poster_path') else None,
                'trailer_url': self._get_trailer_url(movie_data.get('id', 'N/A'))
            }
        except Exception as e:
            print(f"Error parsing movie data: {e}")
            return None
            
    def _get_trailer_url(self, movie_id: int) -> Optional[str]:
        """Fetch YouTube trailer URL for a movie"""
        try:
            if not movie_id or movie_id == 'N/A':
                return None
                
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return None
            
            url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos"
            params = {'api_key': api_key, 'language': 'en-US'}
            
            response = _session.get(url, params=params, timeout=5)
            if response.status_code == 200:
                results = response.json().get('results', [])
                for video in results:
                    if video.get('site') == 'YouTube' and video.get('type') == 'Trailer':
                        return f"https://www.youtube.com/watch?v={video.get('key')}"
            return None
        except Exception:
            return None


class DiscoverMoviesTool(BaseTool):
    name: str = "discover_movies"
    description: str = "Find movies by genre with diverse results. Use this for broad genre requests like 'sci-fi movies' to get fresh recommendations."
    args_schema: type[BaseModel] = DiscoverMoviesInput

    def _run(self, genre: str, min_rating: Optional[float] = None, sort_by: str = "popularity.desc") -> str:
        try:
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return "Error: TMDB_API_KEY not found."

            # Map genre names to IDs
            genre_map = {
                "action": 28, "adventure": 12, "animation": 16, "comedy": 35,
                "crime": 80, "documentary": 99, "drama": 18, "family": 10751,
                "fantasy": 14, "history": 36, "horror": 27, "music": 10402,
                "mystery": 9648, "romance": 10749, "science fiction": 878, "sci-fi": 878,
                "tv movie": 10770, "thriller": 53, "war": 10752, "western": 37
            }
            
            genre_id = genre_map.get(genre.lower())
            if not genre_id:
                # Try partial match
                for k, v in genre_map.items():
                    if k in genre.lower():
                        genre_id = v
                        break
            
            page = random.randint(1, 5)  # Randomize page for diversity
            
            url = "https://api.themoviedb.org/3/discover/movie"
            params = {
                'api_key': api_key,
                'with_genres': genre_id,
                'sort_by': sort_by,
                'language': 'en-US',
                'page': page,
                'vote_count.gte': 100  # Ensure decent quality
            }
            
            if min_rating:
                params['vote_average.gte'] = min_rating
            
            logger.debug(f"DiscoverMoviesTool: discovering genre={genre} (id={genre_id}) min_rating={min_rating} page={page}")
            response = _session.get(url, params=params, timeout=5)
            
            if response.status_code != 200:
                return f"Error discovering movies: {response.status_code} - {response.text}"
                
            data = response.json()
            results = data.get('results', [])[:5]
            
            if not results:
                return f"No movies found for genre: {genre}"

            formatted_results = []
            for movie in results:
                movie_id = movie.get('id')
                trailer_url = self._get_trailer_url(movie_id)
                
                poster_path = movie.get('poster_path')
                image_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
                
                formatted_results.append(
                    f"Title: {movie.get('title')}\\n"
                    f"Year: {str(movie.get('release_date', 'N/A'))[:4]}\\n"
                    f"Rating: {round(movie.get('vote_average', 0), 1) if movie.get('vote_average') else 'N/A'}/10\\n"
                    f"Description: {movie.get('overview', 'No description available')}\\n"
                    f"Image: {image_url}\\n"
                    f"Trailer: {trailer_url if trailer_url else 'N/A'}"
                )
            
            return "\\n---\\n".join(formatted_results)

        except Exception as e:
            return f"Error executing discover_movies: {str(e)}"

    @cache_api_call(ttl=3600)
    def _get_trailer_url(self, movie_id: int) -> Optional[str]:
        try:
            if not movie_id:
                return None
            api_key = os.getenv('TMDB_API_KEY')
            url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos"
            params = {'api_key': api_key}
            resp = _session.get(url, params=params, timeout=3)
            if resp.status_code == 200:
                for video in resp.json().get('results', []):
                    if video.get('site') == 'YouTube' and video.get('type') == 'Trailer':
                        return f"https://www.youtube.com/watch?v={video.get('key')}"
            return None
        except:
            return None
