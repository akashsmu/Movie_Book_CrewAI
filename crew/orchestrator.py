from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
import os
from typing import Dict, List, Optional, Any
import concurrent.futures
import requests
import json
import re
import time
import logging
from datetime import datetime

# Import from new modular API structure
from api import movie_tools, book_tools, tv_tools, search_tools
from crew.agents import create_agents
from crew.tasks import create_tasks
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from cache_manager import PersistentCacheManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('media_recommender.log')
    ]
)
logger = logging.getLogger(__name__)

class MediaRecommendationCrew:
    def __init__(self):
        self.llm = self._setup_llm()
        # Shared HTTP session for external API calls (connection pooling + retries)
        try:
            self._http = requests.Session()
            _retry = Retry(total=3, backoff_factor=0.3, status_forcelist=[500,502,503,504])
            _adapter = HTTPAdapter(max_retries=_retry, pool_connections=10, pool_maxsize=10)
            self._http.mount('https://', _adapter)
            self._http.mount('http://', _adapter)
        except Exception:
            self._http = requests.Session()

        # Persistent rating cache (for movies, books, and TV)
        self._rating_cache = PersistentCacheManager('rating_cache.json')
        self.RATING_CACHE_TTL = int(os.getenv('RATING_CACHE_TTL', '86400'))  # seconds, default 24h
        self.external_step_callback = None
        
        # Create agents and tasks using modular functions
        agents = create_agents(self.llm)
        self.analysis_agent = agents['analysis_agent']
        self.movie_agent = agents['movie_agent']
        self.book_agent = agents['book_agent']
        self.tv_agent = agents['tv_agent']
        self.research_agent = agents['research_agent']
        self.editor_agent = agents['editor_agent']
        
        tasks = create_tasks(agents)
        self.analysis_task = tasks['analysis_task']
        self.movie_task = tasks['movie_task']
        self.book_task = tasks['book_task']
        self.tv_series_task = tasks['tv_series_task']
        self.research_task = tasks['research_task']
        self.editor_task = tasks['editor_task']
        
        logger.info("MediaRecommendationCrew initialized successfully")
    
    def _setup_llm(self) -> ChatOpenAI:
        """Configure and return the LLM with proper error handling"""
        try:
            model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
            api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=api_key,
                max_retries=2,
                request_timeout=30
            )
        except Exception as e:
            logger.error(f"Failed to setup LLM: {e}")
            raise
    
    def run(self, user_request: str, media_type: str = "movie", genre: Optional[str] = None,
            mood: Optional[str] = None, timeframe: Optional[str] = None,
            num_recommendations: int = 3, personalization_context: str = "",
            step_callback=None) -> List[Dict]:
        """
        Execute the media recommendation crew with enhanced error handling and monitoring
        
        Args:
            user_request: The user's media request
            media_type: Type of media ('movie', 'book', 'tv')
            genre: Preferred genre
            mood: Desired mood/tone
            timeframe: Time period preference
            num_recommendations: Number of recommendations to return
            personalization_context: User personalization context
            
        Returns:
            List of recommendation dictionaries
        """
        start_time = time.time()
        logger.info(f"Starting crew execution for request: {user_request[:100]}...")
        
        # Clear previous trace
        self.latest_trace = []

        try:
            # Validate inputs
            self._validate_inputs(user_request, media_type, num_recommendations)
            self._current_media_type = media_type  # Store for task configuration
            self._current_user_request = user_request  # Store for task configuration

            # Set up task inputs
            task_inputs = {
                "user_request": user_request,
                "media_type": media_type,
                "genre": genre or "Not specified",
                "mood": mood or "Not specified", 
                "timeframe": timeframe or "Not specified",
                "num_recommendations": num_recommendations,
                "personalization_context": personalization_context or "No personalization context"
            }
            
            # Store external callback
            self.external_step_callback = step_callback
            
            # Update tasks with current inputs
            self._update_task_descriptions(task_inputs)
            
            # FAST PATH CHECK
            fast_path_match = self._check_fast_path(user_request)
            if fast_path_match:
                logger.info(f"Fast Path triggered: {fast_path_match}")
                # Bypass Analysis Agent
                crew = self._create_fast_path_crew(fast_path_match)
            else:
                # Normal flow
                crew = self._create_crew()
            
            # Execute crew
            # We run directly in the main thread to ensure Streamlit callbacks work correctly
            # (Streamlit contexts are thread-local)
            result = crew.kickoff(inputs=task_inputs)
            
            # Parse and validate results
            recommendations = self._process_crew_result(result, user_request, media_type)
            
            execution_time = time.time() - start_time
            logger.info(f"Crew execution completed in {execution_time:.2f}s. "
                       f"Returning {len(recommendations)} recommendations.")
            
            return recommendations
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Crew execution failed after {execution_time:.2f}s: {e}")
            return self._get_fallback_recommendations(user_request, media_type)

        finally:
            if hasattr(self, '_current_media_type'):
                del self._current_media_type  # Clean up any stored state

    def _validate_inputs(self, user_request: str, media_type: str, num_recommendations: int):
        """Validate input parameters"""
        if not user_request or not user_request.strip():
            raise ValueError("User request cannot be empty")
        
        valid_types = ['movie', 'book', 'tv']
        if media_type not in valid_types:
            raise ValueError(f"Media type must be one of {valid_types}")
        
        if not 1 <= num_recommendations <= 10:
            raise ValueError("Number of recommendations must be between 1 and 10")
    
    def _update_task_descriptions(self, task_inputs: Dict[str, Any]):
        """Update task descriptions with current inputs"""
        try:
            self.analysis_task.description = self.analysis_task.description.format(**task_inputs)
            self.movie_task.description = self.movie_task.description.format(**task_inputs)
            self.book_task.description = self.book_task.description.format(**task_inputs)
            self.tv_series_task.description = self.tv_series_task.description.format(**task_inputs)
            self.research_task.description = self.research_task.description.format(**task_inputs)
            self.editor_task.description = self.editor_task.description.format(**task_inputs)
        except KeyError as e:
            logger.warning(f"Missing key in task inputs: {e}")

    def _log_step(self, step_output):
        """Safe step callback logger"""
        try:
            # Attempt to extract agent role if available
            agent_role = "Unknown Agent"
            if hasattr(step_output, 'agent') and hasattr(step_output.agent, 'role'):
                agent_role = step_output.agent.role
            
            # Log the step occurrence
            logger.info(f"Agent Step: {agent_role} is executing a step...")
                
            # Execute external callback if registered
            if self.external_step_callback:
                self.external_step_callback(step_output)
            
            # Capture trace for Ragas
            if hasattr(step_output, 'result'):
                self.latest_trace.append(str(step_output.result))
            elif isinstance(step_output, (str, dict, list)):
                self.latest_trace.append(str(step_output))
                
        except Exception as e:
            logger.warning(f"Error in step callback: {e}")

    def _log_task(self, task_output):
        """Safe task callback logger"""
        try:
            agent_role = "Unknown Agent"
            if hasattr(task_output, 'agent') and hasattr(task_output.agent, 'role'):
                agent_role = task_output.agent.role
            
            logger.info(f"Task Completion: {agent_role} has finished their task.")
        except Exception as e:
            logger.warning(f"Error in task callback: {e}")
    
    def _check_fast_path(self, user_request: str) -> Optional[Dict]:
        """Check if request allows for fast path execution"""
        # Simple regex for "genre media_type" patterns
        
        request = user_request.lower().strip()
        
        # Patterns
        type_patterns = {
            'movie': r'\s+movies?$',
            'book': r'\s+books?$',
            'tv': r'\s+(tv|shows?|series)$'
        }
        
        genres = r'(action|adventure|animation|comedy|crime|documentary|drama|family|fantasy|history|horror|music|mystery|romance|sci-fi|sci fi|science fiction|thriller|war|western)'
        
        for m_type, pattern_suffix in type_patterns.items():
            pattern = f"^{genres}{pattern_suffix}"
            match = re.search(pattern, request)
            if match:
                genre = match.group(1)
                if genre == 'sci fi': genre = 'sci-fi'
                return {"type": m_type, "genre": genre}
            
        return None

    def _create_fast_path_crew(self, context: Dict) -> Crew:
        """Create a simplified crew for fast execution"""
        tasks = []
        agents = []
        
        # Add specific task based on detected type
        if context['type'] == 'movie':
            tasks.append(self.movie_task)
            agents.append(self.movie_agent)
        elif context['type'] == 'book':
            tasks.append(self.book_task)
            agents.append(self.book_agent)
        elif context['type'] == 'tv':
            tasks.append(self.tv_series_task)
            agents.append(self.tv_agent)
            
        tasks.append(self.editor_task)
        agents.append(self.editor_agent)
        
        return Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True,
            memory=False,
            max_rpm=20,
            step_callback=self._log_step,
            task_callback=self._log_task
        )

    def _create_crew(self) -> Crew:
        """Create crew with production configuration"""
        tasks = [self.analysis_task]
        agents = [self.analysis_agent]
        
        media_type = getattr(self, '_current_media_type', 'movie')
    
        if media_type == "movie":
            tasks.append(self.movie_task)
            agents.append(self.movie_agent)
        elif media_type == "book":
            tasks.append(self.book_task)
            agents.append(self.book_agent)
        elif media_type == "tv":
            tasks.append(self.tv_series_task)
            agents.append(self.tv_agent)

        user_request = getattr(self, '_current_user_request', '')
        if any(word in user_request.lower() for word in ['trending', 'new', 'recent', 'latest', 'upcoming', 'update', 'news', 'current']):
            tasks.append(self.research_task)
            if self.research_agent not in agents:
                agents.append(self.research_agent)
        
        tasks.append(self.editor_task)
        agents.append(self.editor_agent)

        return Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True,  # Set to True for extensive logging
            memory=False,
            max_rpm=20,
            step_callback=self._log_step,
            task_callback=self._log_task
        )
    
    def _execute_crew_with_timeout(self, crew: Crew, inputs: Dict[str, Any], timeout: int = 120):
        """Execute crew with timeout protection."""
        start_time = time.time()
        logger.info("Starting crew kickoff (with timeout protection)...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._run_crew_kickoff, crew, inputs)
            try:
                result = future.result(timeout=timeout)
                execution_time = time.time() - start_time
                logger.info(f"Crew kickoff completed in {execution_time:.2f}s")
                return result
            except concurrent.futures.TimeoutError:
                logger.error(f"Crew kickoff exceeded timeout of {timeout}s; returning early and using fallback")
                try:
                    future.cancel()
                except Exception:
                    pass
                return None
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"Crew kickoff failed after {execution_time:.2f}s: {e}")
                return None

    def _run_crew_kickoff(self, crew: Crew, inputs: Dict[str, Any]):
        """Small wrapper to call crew.kickoff() so it can be run in a thread."""
        try:
            return crew.kickoff()
        except Exception as e:
            logger.error(f"Error during crew.kickoff(): {e}")
            raise
    
    def _process_crew_result(self, result: Any, user_request: str, media_type: str) -> List[Dict]:
        """Process and validate crew result"""
        logger.info("Processing crew result...")
        
        # Parse the result
        recommendations = self._parse_result(result) or []
        
        # Validate we have recommendations
        if not recommendations:
            logger.warning("No recommendations parsed from crew result, using fallback")
            return self._get_fallback_recommendations(user_request, media_type)
        
        # Enrich and validate recommendations
        try:
            self._enrich_ratings(recommendations)
            self._validate_recommendations(recommendations)
        except Exception as e:
            logger.warning(f"Recommendation enrichment/validation failed: {e}")
        
        logger.info(f"Successfully processed {len(recommendations)} recommendations")
        return recommendations
    
    def _parse_result(self, result) -> List[Dict]:
        """Parse crew result with enhanced error handling"""
        try:
            logger.debug(f"Raw result type: {type(result)}")
            
            # Handle different result types
            if isinstance(result, list):
                logger.info("Result is already a list")
                return result
            
            result_str = str(result)
            
            # Try JSON extraction first
            json_match = self._extract_json_from_text(result_str)
            if json_match:
                logger.info("Successfully extracted JSON from result")
                return self._parse_json_safely(json_match)
            
            # Fall back to structured text parsing
            logger.info("Attempting structured text parsing")
            structured_result = self._parse_structured_text(result_str)
            if structured_result:
                logger.info("Successfully parsed structured text")
                return structured_result
            
            logger.warning("Could not parse result using any method")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing result: {e}")
            return None
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """Extract JSON from text with improved pattern matching"""
        try:
            # Multiple JSON pattern attempts
            patterns = [
                r'\[\s*\{[^{}]*\}\s*\]',  # Simple array
                r'\[\s*\{.*?\}\s*\]',     # Array with any content
                r'\{\s*"recommendations".*?\}',  # Object with recommendations key
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    logger.debug(f"Found JSON with pattern: {pattern}")
                    return match.group()
            
            return None
        except Exception as e:
            logger.error(f"Error extracting JSON: {e}")
            return None
    
    def _parse_json_safely(self, json_str: str) -> Optional[List[Dict]]:
        """Safely parse JSON with validation"""
        try:
            parsed_data = json.loads(json_str)
            
            if isinstance(parsed_data, list):
                # Validate each item in the list
                valid_items = []
                for item in parsed_data:
                    if isinstance(item, dict) and item.get('title'):
                        valid_items.append(item)
                
                if valid_items:
                    logger.info(f"Validated {len(valid_items)} JSON recommendations")
                    return valid_items
            
            logger.warning("JSON parsing resulted in invalid format")
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
            return None
    
    def _parse_structured_text(self, text: str) -> Optional[List[Dict]]:
        """Parse structured text with improved field detection"""
        try:
            recommendations = []
            current_rec = {}
            lines = text.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # New recommendation detection
                if self._is_new_recommendation(line, len(recommendations)):
                    if current_rec and self._is_valid_recommendation(current_rec):
                        recommendations.append(current_rec)
                        current_rec = {}
                
                # Field extraction
                self._extract_field(line, current_rec)
            
            # Add final recommendation
            if current_rec and self._is_valid_recommendation(current_rec):
                recommendations.append(current_rec)
            
            # Post-process recommendations
            return self._post_process_recommendations(recommendations)
            
        except Exception as e:
            logger.error(f"Error in structured text parsing: {e}")
            return None
    
    def _is_new_recommendation(self, line: str, current_count: int = 0) -> bool:
        """Check if line indicates a new recommendation"""
        new_rec_indicators = [
            'title:', 'movie:', 'book:', 'tv:', 'recommendation', '###', '---',
            str(current_count + 1) + '.',  # "1.", "2.", etc.
        ]
        return any(indicator in line.lower() for indicator in new_rec_indicators)
    
    def _extract_field(self, line: str, current_rec: Dict):
        """Extract field from line and add to current recommendation"""
        field_patterns = {
            'title': ['title:', 'movie:', 'book:', 'tv:', 'show:'],
            'year': ['year:', 'released:', 'published:', 'aired:'],
            'genre': ['genre:', 'category:'],
            'rating': ['rating:', 'score:'],
            'description': ['description:', 'summary:', 'plot:'],
            'why_recommended': ['why:', 'recommended because:', 'matches because:'],
            'type': ['type:'],
            'image_url': ['image:', 'cover:', 'poster:'],
            'trailer_url': ['trailer:', 'video:'],
            'preview_url': ['preview:', 'sample:', 'google books:']
        }
        
        for field, patterns in field_patterns.items():
            for pattern in patterns:
                if pattern in line.lower():
                    value = line.split(':', 1)[1].strip() if ':' in line else line
                    current_rec[field] = value
                    return
    
    def _is_valid_recommendation(self, rec: Dict) -> bool:
        """Check if recommendation has minimum required fields"""
        return bool(rec.get('title')) # Relaxed check, type inferred if missing
    
    def _post_process_recommendations(self, recommendations: List[Dict]) -> List[Dict]:
        """Add missing fields and validate recommendations"""
        for rec in recommendations:
            rec.setdefault('rating', 'N/A')
            rec.setdefault('similar_titles', [])
            rec.setdefault('description', 'No description available')
            rec.setdefault('why_recommended', 'Matches your preferences')
            rec.setdefault('image_url', None)
            rec.setdefault('trailer_url', None)
            rec.setdefault('type', 'unknown') # Placeholder
            
            if 'year' in rec:
                rec['year'] = str(rec['year']).split('-')[0]
            
            self._normalize_rating(rec)
        
        return recommendations
    
    def _normalize_rating(self, rec: Dict):
        """Normalize rating to numeric format"""
        rating = rec.get('rating')
        if isinstance(rating, (int, float)):
            rec['rating'] = round(float(rating), 1)
        elif isinstance(rating, str):
            try:
                if '/' in rating:
                    rec['rating'] = round(float(rating.split('/')[0].strip()), 1)
                else:
                    rec['rating'] = round(float(rating), 1)
            except (ValueError, AttributeError):
                rec['rating'] = 'N/A'
    
    def _validate_recommendations(self, recommendations: List[Dict]):
        """Validate recommendation structure and content"""
        for rec in recommendations:
            if not rec.get('title'):
                logger.warning(f"Recommendation missing title: {rec}")
    
    def _enrich_ratings(self, recommendations: List[Dict]):
        """Enhanced rating enrichment with better error handling"""
        for rec in recommendations:
            try:
                current_rating = rec.get('rating')
                
                # Skip if we already have a valid rating
                if current_rating not in (None, '', 'N/A', 'Unknown'):
                    continue
                
                # Attempt to fetch rating
                fetched_rating = self._fetch_rating_for_rec(rec)
                if fetched_rating is not None:
                    rec['rating'] = fetched_rating
                    logger.debug(f"Enriched rating for {rec.get('title')}: {fetched_rating}")
                else:
                    rec['rating'] = 'N/A'
                    
            except Exception as e:
                logger.warning(f"Failed to enrich rating for {rec.get('title')}: {e}")
                rec['rating'] = 'N/A'
    
    def _fetch_rating_for_rec(self, rec: Dict) -> Optional[float]:
        """Fetch rating with improved error handling and caching"""
        title = rec.get('title')
        if not title:
            return None
        
        media_type = rec.get('type')
        
        try:
            if media_type == 'movie':
                return self._fetch_movie_rating(title)
            elif media_type == 'book':
                return self._fetch_book_rating(title)
            elif media_type == 'tv':
                return self._fetch_tv_rating(title)
        except Exception as e:
            logger.debug(f"Rating fetch failed for {title}: {e}")
            return None
        
        return None
    
    def _fetch_movie_rating(self, title: str) -> Optional[float]:
        """Fetch movie rating from TMDB"""
        api_key = os.getenv('TMDB_API_KEY')
        if not api_key: return None
        
        key = f"movie:{title.lower()}"
        cached = self._rating_cache.get(key, ttl=self.RATING_CACHE_TTL)
        if cached is not None: return cached

        try:
            params = {'api_key': api_key, 'query': title, 'language': 'en-US', 'page': 1}
            response = self._http.get('https://api.themoviedb.org/3/search/movie', params=params, timeout=10)
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results and results[0].get('vote_average'):
                    rating = round(float(results[0]['vote_average']), 1)
                    self._rating_cache.set(key, rating)
                    return rating
        except Exception:
            pass
        return None
    
    def _fetch_book_rating(self, title: str) -> Optional[float]:
        """Fetch book rating from Google Books"""
        api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
        key = f"book:{title.lower()}"
        cached = self._rating_cache.get(key, ttl=self.RATING_CACHE_TTL)
        if cached is not None: return cached

        try:
            params = {'q': title, 'maxResults': 1}
            if api_key: params['key'] = api_key
            response = self._http.get('https://www.googleapis.com/books/v1/volumes', params=params, timeout=10)
            if response.status_code == 200:
                items = response.json().get('items', [])
                if items:
                    avg_rating = items[0].get('volumeInfo', {}).get('averageRating')
                    if avg_rating is not None:
                        rating = float(avg_rating)
                        self._rating_cache.set(key, rating)
                        return rating
        except Exception:
            pass
        return None

    def _fetch_tv_rating(self, title: str) -> Optional[float]:
        """Fetch TV rating from TMDB"""
        api_key = os.getenv('TMDB_API_KEY')
        if not api_key: return None
        
        key = f"tv:{title.lower()}"
        cached = self._rating_cache.get(key, ttl=self.RATING_CACHE_TTL)
        if cached is not None: return cached

        try:
            params = {'api_key': api_key, 'query': title, 'language': 'en-US', 'page': 1}
            response = self._http.get('https://api.themoviedb.org/3/search/tv', params=params, timeout=10)
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results and results[0].get('vote_average'):
                    rating = round(float(results[0]['vote_average']), 1)
                    self._rating_cache.set(key, rating)
                    return rating
        except Exception:
            pass
        return None
    
    def _get_fallback_recommendations(self, user_request: str, media_type: str) -> List[Dict]:
        """Provide high-quality fallback recommendations"""
        logger.info(f"Using fallback recommendations for: {user_request}")
        
        fallback_data = {
            'movie': [
                {"title": "Inception", "type": "movie", "year": "2010", "genre": "Sci-Fi, Thriller", "rating": 8.8, "description": "A thief who steals corporate secrets through dream-sharing technology.", "why_recommended": "Masterpiece of sci-fi cinema.", "similar_titles": ["The Matrix"]},
                {"title": "The Dark Knight", "type": "movie", "year": "2008", "genre": "Action, Crime", "rating": 9.0, "description": "Batman sets out to dismantle the remaining criminal organizations.", "why_recommended": "Defining superhero movie.", "similar_titles": ["Batman Begins"]}
            ],
            'book': [
                {"title": "Project Hail Mary", "type": "book", "year": "2021", "genre": "Sci-Fi", "rating": 4.8, "description": "A lone astronaut must save the earth.", "why_recommended": "Engaging hard sci-fi.", "similar_titles": ["The Martian"]},
                {"title": "Dune", "type": "book", "year": "1965", "genre": "Sci-Fi", "rating": 4.7, "description": "The story of Paul Atreides.", "why_recommended": "Epic masterpiece.", "similar_titles": ["Foundation"]}
            ],
            'tv': [
                {"title": "Breaking Bad", "type": "tv", "year": "2008", "genre": "Crime, Drama", "rating": 9.5, "description": "A high school chemistry teacher turned manufacturing drug dealer.", "why_recommended": "Widely considered one of the best shows ever made.", "similar_titles": ["Better Call Saul", "Ozark"]},
                {"title": "Stranger Things", "type": "tv", "year": "2016", "genre": "Sci-Fi, Horror", "rating": 8.7, "description": "When a young boy vanishes, a small town uncovers a mystery.", "why_recommended": "Nostalgic and thrilling.", "similar_titles": ["Dark", "The OA"]}
            ]
        }
        
        if media_type in fallback_data:
            return fallback_data[media_type][:3]
        
        return fallback_data['movie'][:3] # Default