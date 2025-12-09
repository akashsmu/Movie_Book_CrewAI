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
from media_apis import movie_tools, book_tools, search_tools
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

        # Simple in-memory rating cache (title -> (timestamp, rating))
        self._rating_cache: Dict[str, Any] = {}
        self.RATING_CACHE_TTL = int(os.getenv('RATING_CACHE_TTL', '86400'))  # seconds, default 24h
        self.setup_agents()
        self.setup_tasks()
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
    
    def setup_agents(self):
        """Initialize all agents with enhanced configuration"""
        try:
            # Analysis Agent - Determines user intent and media type
            self.analysis_agent = Agent(
                role="Media Request Analyst",
                goal="""Analyze user requests to determine media type preference (movie/book/both) 
                and extract specific preferences like genre, mood, timeframe, and themes.""",
                backstory="""You are an expert at understanding user preferences and intent in media requests. 
                You excel at discerning whether someone wants movies, books, or both, and can extract key elements 
                like genre, mood, themes, and specific requirements from their description with high accuracy.""",
                verbose=False,
                allow_delegation=False,
                llm=self.llm,
                max_iter=5,  # Increased from 1
                max_rpm=20    # Increased from 5
            )
            
            # Movie Specialist Agent
            self.movie_agent = Agent(
                role="Movie Recommendation Specialist",
                goal="Find highly-rated, relevant movie recommendations using TMDB API and search tools",
                backstory="""You are a film expert with comprehensive knowledge of cinema across all genres and eras. 
                You use TMDB API and search tools to find current, highly-rated movies that perfectly match user preferences. 
                You consider factors like ratings, reviews, cultural relevance, and thematic alignment.""",
                verbose=False,
                allow_delegation=False,
                llm=self.llm,
                tools=movie_tools + [search_tools[0]],  # movie tools + similar_titles_tool
                max_iter=10,
                max_rpm=20
            )
            
            # Book Specialist Agent
            self.book_agent = Agent(
                role="Book Recommendation Specialist",
                goal="Find compelling book recommendations using Google Books API and search tools",
                backstory="""You are a literary expert with extensive knowledge of books across all genres and time periods. 
                You use Google Books API and search tools to find perfect book matches based on user preferences. 
                You consider writing style, author reputation, thematic elements, and reader reviews.""",
                verbose=False,
                allow_delegation=False,
                llm=self.llm,
                tools=book_tools + [search_tools[0]],  # book tools + similar_titles_tool
                max_iter=10,
                max_rpm=20
            )
            
            # Research Agent
            self.research_agent = Agent(
                role="Media Research Specialist",
                goal="Gather additional context, reviews, and trending information to enhance recommendation quality",
                backstory="""You are a research expert who finds additional context, recent reviews, 
                trending information, and cultural insights about recommended media to provide comprehensive recommendations.""",
                verbose=False,
                allow_delegation=False,
                llm=self.llm,
                tools=search_tools,
                max_iter=10,
                max_rpm=20
            )
            
            # Editor Agent
            self.editor_agent = Agent(
                role="Recommendation Editor",
                goal="Review, refine and personalize recommendations to ensure they perfectly match user needs",
                backstory="""You are a senior editor who ensures all recommendations are high-quality, relevant, 
                and personalized. You check for consistency, remove duplicates, add personalization touches, 
                and ensure the final list is perfectly tailored to the user's stated preferences and context.""",
                verbose=False,
                allow_delegation=False,
                llm=self.llm,
                max_iter=5,
                max_rpm=20
            )
            
            logger.info("All agents initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup agents: {e}")
            raise
    
    def setup_tasks(self):
        """Initialize all tasks with clear completion criteria and constraints"""
        try:
            # Analysis task
            self.analysis_task = Task(
                description="""ANALYZE USER REQUEST:
                
                User Request: {user_request}
                Personalization Context: {personalization_context}
                
                YOUR MISSION:
                1. Determine primary media type preference (movie/book/both)
                2. Extract specific genres, themes, and moods
                3. Identify timeframe preferences
                4. Note any special requirements or constraints
                4. Note any special requirements
                
                OPTIMIZATION:
                - If the request is simple (e.g. 'action movies', 'best sci-fi books'), skip detailed analysis and return a standard profile immediately.
                - Do not over-analyze simple queries.
                
                OUTPUT FORMAT:
                - Media Type: [movie/book/both]
                - Key Genres: [comma-separated list]
                - Mood/Tone: [primary mood]
                - Timeframe: [specific preference]
                - Special Requirements: [any specific asks]""",
                agent=self.analysis_agent,
                expected_output="Detailed breakdown of user preferences including media type, genres, moods, and constraints.",
                max_iter=3,
            )
            
            # Movie recommendation task
            self.movie_task = Task(
                description="""FIND MOVIE RECOMMENDATIONS:
                
                User Preferences:
                - Media Type: {media_type}
                - Genre: {genre}
                - Mood: {mood}
                - Timeframe: {timeframe}
                - Specific Request: {user_request}
                - Number Needed: {num_recommendations}
                
                REQUIREMENTS:
                - Find {num_recommendations} highly-rated movies
                - Match user preferences closely
                - Include diverse options when possible
                - Use TMDB API for accurate data
                
                FOR EACH MOVIE, PROVIDE:
                - Title and release year
                - Genre classification
                - Rating (out of 10)
                - Brief description
                - Why it matches user preferences
                - 2-3 similar movies
                - Image/Poster URL (from search results)
                - Trailer URL (from search results)
                
                SMART STOPPING RULES:
                1. If the user asks for a specific genre (e.g. 'sci-fi', 'action'), use 'discover_movies' tool first. It gives diverse, high-quality results.
                2. If your FIRST search returns 3+ high-quality movies with images and trailers, STOP and return them immediately.
                3. Do NOT run the exact same search query twice.
                4. Only use 'get_movie_details' if you critically need cast/runtime info not in the search results.
                """,
                agent=self.movie_agent,
                expected_output="""List of {num_recommendations} movie recommendations with complete details.
                Each must include: title, year, genre, rating, description, why_recommended, similar_titles, image_url, trailer_url.""",
                async_execution=True,
                max_iter=5,
            )
            
            # Book recommendation task
            self.book_task = Task(
                description="""FIND BOOK RECOMMENDATIONS:
                
                User Preferences:
                - Media Type: {media_type}
                - Genre: {genre}
                - Mood: {mood}
                - Timeframe: {timeframe}
                - Specific Request: {user_request}
                - Number Needed: {num_recommendations}
                
                REQUIREMENTS:
                - Find {num_recommendations} highly-rated books
                - Match user preferences closely
                - Include diverse authors and styles
                - Use Google Books API for accurate data
                
                FOR EACH BOOK, PROVIDE:
                - Title and author
                - Publication year
                - Genre classification
                - Rating (out of 5)
                - Brief description
                - Why it matches user preferences
                - 2-3 similar books
                - Image/Cover URL (from search results)
                
                SMART STOPPING RULES:
                1. If your FIRST search returns 3+ high-quality books with images, STOP and return them immediately.
                2. Do NOT run the exact same search query twice.
                3. Do NOT loop unnecessarily. Speed is quality.
                """,
                agent=self.book_agent,
                expected_output="""List of {num_recommendations} book recommendations with complete details.
                Each must include: title, author, published_year, genre, rating, description, why_recommended, similar_titles, image_url.""",
                async_execution=True,
                max_iter=5,
            )
            
            # Research task
            self.research_task = Task(
                description="""RESEARCH ADDITIONAL CONTEXT:
                
                User Request: {user_request}
                Media Type: {media_type}
                
                RESEARCH FOCUS:
                - Recent news about recommended genres/themes
                - Trending movies/books in relevant categories
                - Cultural context and relevance
                - Critical reception and reviews
                
                PROVIDE:
                - Summary of relevant trends
                - Notable news or updates
                - Cultural context insights
                - Any relevant additional information""",
                agent=self.research_agent,
                expected_output="""Concise research summary with relevant trends, news, and cultural context.
                Focus on information that enhances recommendation quality.""",
                async_execution=True,
                max_iter=2,
            )
            
            # Editor task
            self.editor_task = Task(
                description="""FINALIZE RECOMMENDATIONS:
                
                COMPILE AND REFINE:
                - Combine recommendations from all specialists
                - Remove duplicates and ensure diversity
                - Add personalized explanations
                - Rank by relevance and quality
                - Incorporate research insights
                
                OUTPUT REQUIREMENTS:
                - Valid JSON array only
                - 3-5 total recommendations
                - Mix of media types if applicable
                - Clear personalization for each item
                
                CRITICAL: Return ONLY valid JSON, no other text.
                
                JSON FORMAT:
                [
                  {{
                    "title": "Item Title",
                    "type": "movie/book",
                    "year": "2023",
                    "genre": "Genre1, Genre2",
                    "rating": 8.5,
                    "description": "Brief description",
                    "why_recommended": "Personalized explanation",
                    "similar_titles": ["Title1", "Title2", "Title3"],
                    "image_url": "https://...",
                    "trailer_url": "https://www.youtube.com/..."
                  }}
                ]""",
                agent=self.editor_agent,
                expected_output="""Valid JSON array with 3-5 personalized media recommendations.
                Each item must have: title, type, year, genre, rating, description, why_recommended, similar_titles, image_url.
                NO additional text outside JSON.""",
                max_iter=3,
            )
            
            logger.info("All tasks initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup tasks: {e}")
            raise
    
    def run(self, user_request: str, media_type: str = "both", genre: Optional[str] = None,
            mood: Optional[str] = None, timeframe: Optional[str] = None,
            num_recommendations: int = 3, personalization_context: str = "") -> List[Dict]:
        """
        Execute the media recommendation crew with enhanced error handling and monitoring
        
        Args:
            user_request: The user's media request
            media_type: Type of media ('movie', 'book', 'both')
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
            
            # Update tasks with current inputs
            self._update_task_descriptions(task_inputs)
            
            # FAST PATH CHECK
            fast_path_match = self._check_fast_path(user_request)
            if fast_path_match:
                logger.info(f"Fast Path triggered: {fast_path_match}")
                # Bypass Analysis Agent
                # We need to manually inject the "analysis" result or just configure the crew to skip the analysis task
                # Simplest way: Create a custom crew list excluding analysis_task
                crew = self._create_fast_path_crew(fast_path_match)
            else:
                # Normal flow
                crew = self._create_crew()
            
            # Execute with timeout protection
            result = self._execute_crew_with_timeout(crew, task_inputs, timeout=600)  # 10 minute timeout
            
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
        
        if media_type not in ['movie', 'book', 'both']:
            raise ValueError("Media type must be 'movie', 'book', or 'both'")
        
        if not 1 <= num_recommendations <= 10:
            raise ValueError("Number of recommendations must be between 1 and 10")
    
    def _update_task_descriptions(self, task_inputs: Dict[str, Any]):
        """Update task descriptions with current inputs"""
        try:
            self.analysis_task.description = self.analysis_task.description.format(**task_inputs)
            self.movie_task.description = self.movie_task.description.format(**task_inputs)
            self.book_task.description = self.book_task.description.format(**task_inputs)
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
            
            # Optionally log thought/tool if available and needed
            # if hasattr(step_output, 'thought'):
            #    logger.debug(f"Thought: {step_output.thought}")
                
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
        # e.g. "sci fi movies", "action books", "comedy movie"
        
        request = user_request.lower().strip()
        
        # Movie patterns
        movie_match = re.search(r'^(action|adventure|animation|comedy|crime|documentary|drama|family|fantasy|history|horror|music|mystery|romance|sci-fi|sci fi|science fiction|thriller|war|western)\s+movies?$', request)
        if movie_match:
            # Normalize genre for API
            genre = movie_match.group(1)
            if genre == 'sci fi': genre = 'sci-fi'
            return {"type": "movie", "genre": genre}
            
        return None

    def _create_fast_path_crew(self, context: Dict) -> Crew:
        """Create a simplified crew for fast execution"""
        tasks = []
        
        # Add specific task based on detected type
        if context['type'] == 'movie':
            # Pre-inject genre into task description if possible, or reliance on agent to pick it up from user_request (which is preserved)
            # Actually, _update_task_descriptions already updated description with {user_request}
            tasks.append(self.movie_task)
            
        tasks.append(self.editor_task)
        
        return Crew(
            agents=[self.movie_agent, self.editor_agent], # Only relevant agents
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
        
        media_type = getattr(self, '_current_media_type', 'both')
    
        if media_type in ["movie", "both"]:
            tasks.append(self.movie_task)
        if media_type in ["book", "both"]:
            tasks.append(self.book_task)

        user_request = getattr(self, '_current_user_request', '')
        if any(word in user_request.lower() for word in ['trending', 'new', 'recent', 'latest', 'upcoming', 'update', 'news', 'current']):
            tasks.append(self.research_task)
        
        #tasks.append(self.research_task)
        tasks.append(self.editor_task)

        return Crew(
            agents=[self.analysis_agent, self.movie_agent, self.book_agent,
                    self.research_agent, self.editor_agent],
            tasks=tasks,
            process=Process.sequential,
            verbose=True,  # Set to True for extensive logging
            memory=False,
            max_rpm=20,
            step_callback=self._log_step,
            task_callback=self._log_task
        )
    
    def _execute_crew_with_timeout(self, crew: Crew, inputs: Dict[str, Any], timeout: int = 120):
        """Execute crew with timeout protection.

        Runs crew.kickoff in a background thread and enforces a hard timeout on waiting.
        If the timeout is reached, we return None (caller should handle fallback).
        Note: underlying background thread may still be running; this prevents the API
        from blocking the caller and limits user-facing latency.
        """
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
                # Attempt to cancel the future; if it is already running, cancel() returns False
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
            logger.debug(f"Raw result type: {type(result)}, length: {len(str(result)) if hasattr(result, '__len__') else 'N/A'}")
            
            # Handle different result types
            if isinstance(result, list):
                logger.info("Result is already a list")
                return result
            
            result_str = str(result)
            logger.debug(f"Result string preview: {result_str[:200]}...")
            
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
            'title:', 'movie:', 'book:', 'recommendation', '###', '---',
            str(current_count + 1) + '.',  # "1.", "2.", etc.
        ]
        return any(indicator in line.lower() for indicator in new_rec_indicators)
    
    def _extract_field(self, line: str, current_rec: Dict):
        """Extract field from line and add to current recommendation"""
        field_patterns = {
            'title': ['title:', 'movie:', 'book:'],
            'year': ['year:', 'released:', 'published:'],
            'genre': ['genre:', 'category:'],
            'rating': ['rating:', 'score:'],
            'description': ['description:', 'summary:', 'plot:'],
            'why_recommended': ['why:', 'recommended because:', 'matches because:'],
            'type': ['type:'],
            'image_url': ['image:', 'cover:', 'poster:'],
            'trailer_url': ['trailer:', 'video:', 'preview:']
        }
        
        for field, patterns in field_patterns.items():
            for pattern in patterns:
                if pattern in line.lower():
                    value = line.split(':', 1)[1].strip() if ':' in line else line
                    current_rec[field] = value
                    return
    
    def _is_valid_recommendation(self, rec: Dict) -> bool:
        """Check if recommendation has minimum required fields"""
        return bool(rec.get('title') and rec.get('type'))
    
    def _post_process_recommendations(self, recommendations: List[Dict]) -> List[Dict]:
        """Add missing fields and validate recommendations"""
        for rec in recommendations:
            # Ensure required fields
            rec.setdefault('rating', 'N/A')
            rec.setdefault('similar_titles', [])
            rec.setdefault('rating', 'N/A')
            rec.setdefault('similar_titles', [])
            rec.setdefault('description', 'No description available')
            rec.setdefault('why_recommended', 'Matches your preferences')
            rec.setdefault('image_url', None)
            rec.setdefault('trailer_url', None)
            
            # Clean up fields
            if 'year' in rec:
                rec['year'] = str(rec['year']).split('-')[0]  # Extract year from date
            
            # Ensure rating is properly formatted
            self._normalize_rating(rec)
        
        return recommendations
    
    def _normalize_rating(self, rec: Dict):
        """Normalize rating to numeric format"""
        rating = rec.get('rating')
        if isinstance(rating, (int, float)):
            rec['rating'] = round(float(rating), 1)
        elif isinstance(rating, str):
            try:
                # Handle "8.5/10", "4.5/5", etc.
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
            if not rec.get('type') in ['movie', 'book']:
                logger.warning(f"Invalid type in recommendation: {rec.get('type')}")
    
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
        except Exception as e:
            logger.debug(f"Rating fetch failed for {title}: {e}")
            return None
        
        return None
    
    def _fetch_movie_rating(self, title: str) -> Optional[float]:
        """Fetch movie rating from TMDB"""
        api_key = os.getenv('TMDB_API_KEY')
        if not api_key:
            return None
        # Check cache first
        key = f"movie:{title.lower()}"
        now = time.time()
        cached = self._rating_cache.get(key)
        if cached and now - cached[0] < self.RATING_CACHE_TTL:
            logger.debug(f"_fetch_movie_rating: cache HIT for {key}")
            return cached[1]

        try:
            params = {
                'api_key': api_key,
                'query': title,
                'language': 'en-US',
                'page': 1
            }

            start = time.time()
            response = self._http.get('https://api.themoviedb.org/3/search/movie', params=params, timeout=10)
            duration = time.time() - start
            logger.debug(f"_fetch_movie_rating: TMDB responded status={getattr(response,'status_code',None)} in {duration:.3f}s for title={title}")
            response.raise_for_status()

            data = response.json()
            results = data.get('results', [])

            if results and results[0].get('vote_average'):
                rating = round(float(results[0]['vote_average']), 1)
                # Cache result
                self._rating_cache[key] = (now, rating)
                logger.debug(f"_fetch_movie_rating: cached rating {rating} for {key}")
                return rating

        except Exception as e:
            logger.debug(f"TMDB API error for {title}: {e}")

        return None
    
    def _fetch_book_rating(self, title: str) -> Optional[float]:
        """Fetch book rating from Google Books"""
        api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
        # Check cache first
        key = f"book:{title.lower()}"
        now = time.time()
        cached = self._rating_cache.get(key)
        if cached and now - cached[0] < self.RATING_CACHE_TTL:
            logger.debug(f"_fetch_book_rating: cache HIT for {key}")
            return cached[1]

        try:
            params = {'q': title, 'maxResults': 1}
            if api_key:
                params['key'] = api_key

            start = time.time()
            response = self._http.get('https://www.googleapis.com/books/v1/volumes', params=params, timeout=10)
            duration = time.time() - start
            logger.debug(f"_fetch_book_rating: Google Books responded status={getattr(response,'status_code',None)} in {duration:.3f}s for title={title}")
            response.raise_for_status()

            data = response.json()
            items = data.get('items', [])

            if items:
                volume_info = items[0].get('volumeInfo', {})
                avg_rating = volume_info.get('averageRating')
                if avg_rating is not None:
                    rating = float(avg_rating)
                    self._rating_cache[key] = (now, rating)
                    logger.debug(f"_fetch_book_rating: cached rating {rating} for {key}")
                    return rating

        except Exception as e:
            logger.debug(f"Google Books API error for {title}: {e}")

        return None
    
    def _get_fallback_recommendations(self, user_request: str, media_type: str) -> List[Dict]:
        """Provide high-quality fallback recommendations"""
        logger.info(f"Using fallback recommendations for: {user_request}")
        
        # Enhanced fallback data with more variety
        fallback_data = {
            'movie': [
                {
                    "title": "Inception",
                    "type": "movie",
                    "year": "2010",
                    "genre": "Sci-Fi, Thriller",
                    "rating": 8.8,
                    "description": "A thief who steals corporate secrets through dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.",
                    "why_recommended": "Mind-bending plot with stunning visuals perfect for fans of complex sci-fi narratives.",
                    "similar_titles": ["The Matrix", "Interstellar", "Tenet"]
                },
                {
                    "title": "The Shawshank Redemption",
                    "type": "movie", 
                    "year": "1994",
                    "genre": "Drama",
                    "rating": 9.3,
                    "description": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.",
                    "why_recommended": "Powerful storytelling and character development that resonates emotionally with viewers.",
                    "similar_titles": ["The Green Mile", "Forrest Gump", "The Godfather"]
                },
                {
                    "title": "Parasite",
                    "type": "movie",
                    "year": "2019",
                    "genre": "Thriller, Drama",
                    "rating": 8.6,
                    "description": "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.",
                    "why_recommended": "Award-winning social thriller that masterfully blends multiple genres.",
                    "similar_titles": ["Snowpiercer", "Memories of Murder", "Shoplifters"]
                }
            ],
            'book': [
                {
                    "title": "Project Hail Mary",
                    "type": "book",
                    "year": "2021", 
                    "genre": "Science Fiction",
                    "rating": 4.8,
                    "description": "A lone astronaut must save the earth from disaster in this high-stakes sci-fi adventure filled with humor and science.",
                    "why_recommended": "Engaging hard sci-fi with compelling characters and creative problem-solving.",
                    "similar_titles": ["The Martian", "Artemis", "Three Body Problem"]
                },
                {
                    "title": "The Midnight Library",
                    "type": "book",
                    "year": "2020",
                    "genre": "Fiction, Fantasy", 
                    "rating": 4.6,
                    "description": "Between life and death there is a library, and within that library, the shelves go on forever. Every book provides a chance to try another life you could have lived.",
                    "why_recommended": "Thought-provoking exploration of life choices, regrets, and possibilities.",
                    "similar_titles": ["The Invisible Life of Addie LaRue", "Life After Life", "The Alchemist"]
                },
                {
                    "title": "Where the Crawdads Sing",
                    "type": "book",
                    "year": "2018",
                    "genre": "Mystery, Fiction",
                    "rating": 4.8,
                    "description": "The story of Kya Clark, the 'Marsh Girl' of Barkley Cove, North Carolina, and a mysterious murder that rocks the small town.",
                    "why_recommended": "Beautifully written mystery with rich atmosphere and character development.",
                    "similar_titles": ["The Great Alone", "The Secret Life of Bees", "Educated"]
                }
            ]
        }
        
        if media_type == "movie":
            return fallback_data['movie'][:3]
        elif media_type == "book":
            return fallback_data['book'][:3]
        else:
            # Mix for "both" - ensure we have both types
            movies = fallback_data['movie'][:2]
            books = fallback_data['book'][:1]
            return movies + books

    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get execution metrics for monitoring"""
        return {
            "timestamp": datetime.now().isoformat(),
            "agents_initialized": len([self.analysis_agent, self.movie_agent, self.book_agent, 
                                     self.research_agent, self.editor_agent]),
            "tasks_configured": len([self.analysis_task, self.movie_task, self.book_task,
                                   self.research_task, self.editor_task]),
            "llm_model": self.llm.model_name,
            "llm_temperature": self.llm.temperature
        }