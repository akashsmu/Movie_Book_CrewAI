"""TV Series-related API tools for TMDB."""

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
class TVSearchInput(BaseModel):
    query: str = Field(description="Search query for TV shows")
    year: Optional[Union[int, str]] = Field(None, description="First air date year filter")
    genre: Optional[str] = Field(None, description="Genre filter")


class TVDetailsInput(BaseModel):
    tv_id: int = Field(description="TMDB TV show ID")


class DiscoverTVInput(BaseModel):
    genre: str = Field(description="The genre to filter by (e.g., 'Action & Adventure', 'Drama', 'Comedy')")
    min_rating: Optional[float] = Field(default=None, description="Minimum rating (0-10) to filter by")
    sort_by: Optional[str] = Field(default="popularity.desc", description="Sort order (default: popularity.desc)")


class TVSearchTool(BaseTool):
    name: str = "search_tv_shows"
    description: str = "Search for TV shows using TMDB API"
    args_schema: type[BaseModel] = TVSearchInput
    
    @cache_api_call(ttl=300)
    def _run(self, query: str, year: Optional[Union[int, str]] = None, genre: Optional[str] = None) -> str:
        try:
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return "TMDB API key not configured. Please set TMDB_API_KEY in your environment variables."
            
            base_url = "https://api.themoviedb.org/3"
            search_url = f"{base_url}/search/tv"
            
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
                    params['first_air_date_year'] = year
                
            logger.debug(f"TVSearchTool._run: searching TV with params: {params}")
            
            # Perform search
            start = time.time()
            response = _session.get(search_url, params=params, timeout=10)
            duration = time.time() - start
            logger.debug(f"TVSearchTool._run: TMDB responded status={getattr(response,'status_code',None)} in {duration:.3f}s")
            
            if response.status_code != 200:
                return f"API error: {response.status_code}"
            
            data = response.json()
            results = data.get('results', [])
            shows = []
            
            for show in results[:5]:
                show_details = self._get_basic_show_details(show)
                if show_details:
                    shows.append(show_details)
            
            if not shows:
                return f"No TV shows found for query: '{query}'"
            
            formatted_results = []
            for show in shows:
                # Fetch detailed info for top results to get season counts
                details = self._fetch_season_details(show['id'])
                seasons_str = f"Seasons: {details.get('number_of_seasons', 'N/A')}" if details else "Seasons: N/A"
                episodes_str = f"Episodes: {details.get('number_of_episodes', 'N/A')}" if details else ""
                
                formatted_results.append(
                    f"Title: {show['title']} ({show['year']})\\n"
                    f"Rating: {show['rating']}/10\\n"
                    f"Genre: {show['genre']}\\n"
                    f"{seasons_str} {episodes_str}\\n"
                    f"Description: {show['description']}\\n"
                    f"ID: {show['id']}\\n"
                    f"Image: {show['image_url']}\\n"
                    f"Trailer: {show.get('trailer_url', 'N/A')}"
                )
            
            return "\\n---\\n".join(formatted_results)
            
        except Exception as e:
            return f"Error searching TV shows: {str(e)}"

    @cache_api_call(ttl=3600)
    def _fetch_season_details(self, tv_id: int) -> Optional[Dict]:
        """Fetch details for a specific TV show to get season counts"""
        try:
            if not tv_id or tv_id == 'N/A': return None
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key: return None
            
            url = f"https://api.themoviedb.org/3/tv/{tv_id}"
            params = {'api_key': api_key, 'language': 'en-US'}
            
            # Short timeout as this is a secondary call
            response = _session.get(url, params=params, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'number_of_seasons': data.get('number_of_seasons'),
                    'number_of_episodes': data.get('number_of_episodes')
                }
            return None
        except Exception:
            return None

    def _get_basic_show_details(self, show) -> Optional[Dict]:
        try:
            # Handle both dictionary and object
            def get_val(obj, key, default=None):
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            # Get genre names from genre IDs
            genre_names = []
            genre_ids = get_val(show, 'genre_ids', [])
            if genre_ids:
                genre_map = {
                    10759: "Action & Adventure", 16: "Animation", 35: "Comedy",
                    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
                    10762: "Kids", 9648: "Mystery", 10763: "News", 10764: "Reality",
                    10765: "Sci-Fi & Fantasy", 10766: "Soap", 10767: "Talk",
                    10768: "War & Politics", 37: "Western"
                }
                for genre_id in genre_ids[:3]:
                    if genre_id in genre_map:
                        genre_names.append(genre_map[genre_id])
            
            # Safely get first air date
            first_air_date = get_val(show, 'first_air_date')
            year = 'N/A'
            if first_air_date:
                try:
                    year = str(first_air_date)[:4]
                except:
                    year = 'N/A'
            
            poster_path = get_val(show, 'poster_path')
            vote_average = get_val(show, 'vote_average')
            
            return {
                'id': get_val(show, 'id', 'N/A'),
                'title': get_val(show, 'name', 'Unknown Title'), # 'name' for TV
                'year': year,
                'rating': round(vote_average, 1) if vote_average is not None else 'N/A',
                'genre': ', '.join(genre_names) if genre_names else 'Unknown',
                'description': get_val(show, 'overview', 'No description available'),
                'image_url': f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None,
                'trailer_url': self._get_trailer_url(get_val(show, 'id'))
            }
        except Exception as e:
            print(f"Error getting basic TV details: {e}")
            return None

    @cache_api_call(ttl=3600)
    def _get_trailer_url(self, tv_id: int) -> Optional[str]:
        """Fetch YouTube trailer URL for a TV show"""
        try:
            if not tv_id or tv_id == 'N/A':
                return None
                
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return None
                
            url = f"https://api.themoviedb.org/3/tv/{tv_id}/videos"
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


class TVDetailsTool(BaseTool):
    name: str = "get_tv_details"
    description: str = "Get detailed information about a specific TV show"
    args_schema: type[BaseModel] = TVDetailsInput
    
    @cache_api_call(ttl=3600)
    def _run(self, tv_id: int) -> str:
        try:
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return "TMDB API key not configured. Please set TMDB_API_KEY in your environment variables."
            
            base_url = "https://api.themoviedb.org/3"
            tv_url = f"{base_url}/tv/{tv_id}"
            
            params = {
                'api_key': api_key,
                'language': 'en-US',
                'append_to_response': 'credits,videos'
            }
            
            logger.debug(f"TVDetailsTool._run: getting details for tv_id={tv_id}")
            start = time.time()
            response = _session.get(tv_url, params=params, timeout=10)
            duration = time.time() - start
            logger.debug(f"TVDetailsTool._run: TMDB responded status={getattr(response,'status_code',None)} in {duration:.3f}s")
            
            if response.status_code != 200:
                return f"Error fetching TV details: {response.status_code}"
            
            show_data = response.json()
            
            # Parse the data safely
            title = show_data.get('name', 'Unknown Title')
            first_air_date = show_data.get('first_air_date', '')
            year = first_air_date[:4] if first_air_date else 'N/A'
            vote_average = show_data.get('vote_average')
            rating = round(vote_average, 1) if vote_average is not None else 'N/A'
            
            # Get genres
            genres = [genre.get('name', '') for genre in show_data.get('genres', [])[:3]]
            genre_str = ', '.join([g for g in genres if g])
            
            description = show_data.get('overview', 'No description available')
            
            # TV specific fields
            num_seasons = show_data.get('number_of_seasons', 0)
            num_episodes = show_data.get('number_of_episodes', 0)
            status = show_data.get('status', 'Unknown')
            
            # Get cast
            cast = show_data.get('credits', {}).get('cast', [])
            cast_names = [actor.get('name', '') for actor in cast[:3]]
            cast_str = ', '.join([c for c in cast_names if c])
            
            poster_path = show_data.get('poster_path')
            image_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
            
            # Fetch trailer
            trailer_url = None
            videos = show_data.get('videos', {}).get('results', [])
            for video in videos:
                if video.get('site') == 'YouTube' and video.get('type') == 'Trailer':
                    trailer_url = f"https://www.youtube.com/watch?v={video.get('key')}"
                    break
            
            return (
                f"Title: {title} ({year})\\n"
                f"Rating: {rating}/10\\n"
                f"Genre: {genre_str if genre_str else 'Unknown'}\\n"
                f"Seasons: {num_seasons} ({num_episodes} episodes)\\n"
                f"Status: {status}\\n"
                f"Description: {description}\\n"
                f"Cast: {cast_str if cast_str else 'N/A'}\\n"
                f"Image: {image_url}\\n"
                f"Trailer: {trailer_url if trailer_url else 'N/A'}"
            )
            
        except Exception as e:
            return f"Error getting TV details: {str(e)}"


class PopularTVTool(BaseTool):
    name: str = "get_popular_tv_shows"
    description: str = "Get currently popular TV shows using direct API calls"
    
    @cache_api_call(ttl=3600)
    def _run(self, genre: Optional[str] = None) -> str:
        try:
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return "TMDB API key not configured. Using fallback popular shows."
            
            base_url = "https://api.themoviedb.org/3"
            popular_url = f"{base_url}/tv/popular"
            
            params = {
                'api_key': api_key,
                'language': 'en-US',
                'page': 1
            }
            
            start = time.time()
            response = _session.get(popular_url, params=params, timeout=10)
            duration = time.time() - start
            logger.debug(f"PopularTVTool: fetched in {duration:.3f}s")
            
            if response.status_code != 200:
                return "Error fetching popular TV shows."
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                return "No popular TV shows found."
            
            shows = []
            for show_data in results[:5]:
                show_details = self._parse_show_data(show_data)
                if show_details:
                    # Very simple genre check
                    if not genre or genre.lower() in show_details['genre'].lower():
                        shows.append(show_details)
            
            if not shows:
                return "No popular TV shows match the specified genre."
            
            formatted_results = []
            for show in shows:
                formatted_results.append(
                    f"Title: {show['title']} ({show['year']})\\n"
                    f"Rating: {show['rating']}/10\\n"
                    f"Genre: {show['genre']}\\n"
                    f"Description: {show['description']}\\n"
                    f"Image: {show['image_url']}\\n"
                    f"Trailer: {show.get('trailer_url', 'N/A')}"
                )
            
            return "Popular TV Shows:\\n" + "\\n---\\n".join(formatted_results)
            
        except Exception as e:
            return f"Error: {str(e)}"

    def _parse_show_data(self, show_data: Dict) -> Optional[Dict]:
        try:
            genre_map = {
                10759: "Action & Adventure", 16: "Animation", 35: "Comedy",
                80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
                10762: "Kids", 9648: "Mystery", 10763: "News", 10764: "Reality",
                10765: "Sci-Fi & Fantasy", 10766: "Soap", 10767: "Talk",
                10768: "War & Politics", 37: "Western"
            }
            
            genre_names = []
            for genre_id in show_data.get('genre_ids', [])[:3]:
                if genre_id in genre_map:
                    genre_names.append(genre_map[genre_id])
            
            first_air_date = show_data.get('first_air_date', '')
            year = first_air_date[:4] if first_air_date else 'N/A'
            
            vote_average = show_data.get('vote_average')
            return {
                'title': show_data.get('name', 'Unknown Title'),
                'year': year,
                'rating': round(vote_average, 1) if vote_average is not None else 'N/A',
                'genre': ', '.join(genre_names) if genre_names else 'Unknown',
                'description': show_data.get('overview', 'No description available'),
                'image_url': f"https://image.tmdb.org/t/p/w500{show_data.get('poster_path')}" if show_data.get('poster_path') else None,
                'trailer_url': self._get_trailer_url(show_data.get('id', 'N/A'))
            }
        except Exception:
            return None
            
    def _get_trailer_url(self, tv_id: int) -> Optional[str]:
        try:
            if not tv_id: return None
            api_key = os.getenv('TMDB_API_KEY')
            url = f"https://api.themoviedb.org/3/tv/{tv_id}/videos"
            params = {'api_key': api_key}
            resp = _session.get(url, params=params, timeout=3)
            if resp.status_code == 200:
                for video in resp.json().get('results', []):
                    if video.get('site') == 'YouTube' and video.get('type') == 'Trailer':
                        return f"https://www.youtube.com/watch?v={video.get('key')}"
            return None
        except:
            return None


class DiscoverTVTool(BaseTool):
    name: str = "discover_tv_shows"
    description: str = "Find TV shows by genre with diverse results. Use for broad genre requests."
    args_schema: type[BaseModel] = DiscoverTVInput

    def _run(self, genre: str, min_rating: Optional[float] = None, sort_by: str = "popularity.desc") -> str:
        try:
            api_key = os.getenv('TMDB_API_KEY')
            if not api_key:
                return "Error: TMDB_API_KEY not found."

            # Map genre names to IDs (TV Specific)
            genre_map = {
                "action & adventure": 10759, "action": 10759, "adventure": 10759,
                "animation": 16, "comedy": 35, "crime": 80, "documentary": 99,
                "drama": 18, "family": 10751, "kids": 10762, "mystery": 9648,
                "news": 10763, "reality": 10764, "sci-fi & fantasy": 10765,
                "sci-fi": 10765, "fantasy": 10765, "soap": 10766, "talk": 10767,
                "war & politics": 10768, "war": 10768, "western": 37
            }
            
            genre_id = genre_map.get(genre.lower())
            if not genre_id:
                for k, v in genre_map.items():
                    if k in genre.lower():
                        genre_id = v
                        break
            
            page = random.randint(1, 5)
            
            url = "https://api.themoviedb.org/3/discover/tv"
            params = {
                'api_key': api_key,
                'with_genres': genre_id,
                'sort_by': sort_by,
                'language': 'en-US',
                'page': page,
                'vote_count.gte': 50
            }
            
            if min_rating:
                params['vote_average.gte'] = min_rating
            
            response = _session.get(url, params=params, timeout=5)
            
            if response.status_code != 200:
                return f"Error discovering TV shows: {response.status_code}"
                
            data = response.json()
            results = data.get('results', [])[:5]
            
            if not results:
                return f"No TV shows found for genre: {genre}"

            formatted_results = []
            for show in results:
                show_id = show.get('id')
                trailer_url = self._get_trailer_url(show_id)
                
                poster_path = show.get('poster_path')
                image_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
                
                formatted_results.append(
                    f"Title: {show.get('name')}\\n"
                    f"Year: {str(show.get('first_air_date', 'N/A'))[:4]}\\n"
                    f"Rating: {round(show.get('vote_average', 0), 1)}/10\\n"
                    f"Description: {show.get('overview', 'No description available')}\\n"
                    f"Image: {image_url}\\n"
                    f"Trailer: {trailer_url if trailer_url else 'N/A'}"
                )
            
            return "\\n---\\n".join(formatted_results)

        except Exception as e:
            return f"Error executing discover_tv_shows: {str(e)}"

    @cache_api_call(ttl=3600)
    def _get_trailer_url(self, tv_id: int) -> Optional[str]:
        try:
            if not tv_id: return None
            api_key = os.getenv('TMDB_API_KEY')
            url = f"https://api.themoviedb.org/3/tv/{tv_id}/videos"
            params = {'api_key': api_key}
            resp = _session.get(url, params=params, timeout=3)
            if resp.status_code == 200:
                for video in resp.json().get('results', []):
                    if video.get('site') == 'YouTube' and video.get('type') == 'Trailer':
                        return f"https://www.youtube.com/watch?v={video.get('key')}"
            return None
        except:
            return None
