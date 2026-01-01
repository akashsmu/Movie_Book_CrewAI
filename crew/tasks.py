"""Task definitions for the Media Recommendation Crew."""

from crewai import Task
from crewai import Agent
import logging

logger = logging.getLogger(__name__)


def create_tasks(agents: dict) -> dict:
    """
    Create all tasks for the media recommendation crew.
    
    Args:
        agents: Dictionary of agent instances from create_agents()
        
    Returns:
        Dictionary of task instances
    """
    try:
        #Analysis task
        analysis_task = Task(
            description="""ANALYZE USER REQUEST:
            
            User Request: {user_request}
            Personalization Context: {personalization_context}
            
            YOUR MISSION:
            1. Determine primary media type preference (movie/book/tv series)
            2. Extract specific genres, themes, and moods
            3. Identify timeframe preferences
            4. Note any special requirements or constraints
            5. **DETECT CONTRADICTIONS**: Identify if the request contains impossible or contradictory requirements
            
            CONTRADICTION DETECTION EXAMPLES:
            - "Happy movie about the Titanic" (happy mood + tragic historical event)
            - "Short 3-hour movie" (short duration + long duration)
            - "Lighthearted comedy about the Holocaust" (comedic tone + tragic subject)
            - "Uplifting book about depression" (mood contradiction)
            - "Relaxing horror movie" (genre-mood conflict)
            
            OPTIMIZATION:
            - If the request is simple (e.g. 'action movies', 'best sci-fi books'), skip detailed analysis and return a standard profile immediately.
            - Do not over-analyze simple queries.
            
            OUTPUT FORMAT:
            - Media Type: [movie/book/tv]
            - Key Genres: [comma-separated list]
            - Mood/Tone: [primary mood]
            - Timeframe: [specific preference]
            - Special Requirements: [any specific asks]
            - Contradiction Detected: [yes/no - explain if yes]""",
            agent=agents['analysis_agent'],
            expected_output="Detailed breakdown of user preferences including media type, genres, moods, and constraints.",
            max_iter=3,
        )
        
        # Movie recommendation task
        movie_task = Task(
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
            2. If your FIRST search returns {num_recommendations} or more high-quality movies with images and trailers, STOP and return them immediately.
            3. Do NOT run the exact same search query twice.
            4. Only use 'get_movie_details' if you critically need cast/runtime info not in the search results.
            """,
            agent=agents['movie_agent'],
            expected_output="""List of {num_recommendations} movie recommendations with complete details.
            Each must include: title, year, genre, rating, description, why_recommended, similar_titles, image_url, trailer_url.""",
            async_execution=False,
            max_iter=5,
        )
        
        # TV recommendation task
        tv_series_task = Task(
            description="""FIND TV SERIES RECOMMENDATIONS:
            
            User Preferences:
            - Media Type: {media_type}
            - Genre: {genre}
            - Mood: {mood}
            - Timeframe: {timeframe}
            - Specific Request: {user_request}
            - Number Needed: {num_recommendations}
            
            REQUIREMENTS:
            - Find {num_recommendations} highly-rated TV shows
            - Match user preferences closely
            - Include diverse options when possible
            - Use TMDB API for accurate data
            
            FOR EACH TV SHOW, PROVIDE:
            - Title and first air year
            - Genre classification
            - Rating (out of 10)
            - Number of seasons (Format: "Seasons: X")
            - Number of episodes (Format: "Episodes: Y")
            - Brief description
            - Why it matches user preferences
            - 2-3 similar shows
            - Image/Poster URL (from search results)
            - Trailer URL (from search results)
            
            SMART STOPPING RULES:
            1. If your FIRST search returns {num_recommendations} or more high-quality shows with images, STOP and return them immediately.
            2. Do NOT run the exact same search query twice.
            
            STRATEGY:
            - If 'Specific Request' contains a show name -> Use 'search_tv_shows' with that name.
            - If request is for a genre -> Use 'discover_tv_shows'.
            """,
            agent=agents['tv_agent'],
            expected_output="""List of {num_recommendations} TV show recommendations with complete details.
            Each must include: title, year, genre, rating, description, why_recommended, similar_titles, image_url, trailer_url.""",
            async_execution=False,
            max_iter=5,
        )
        
        # Book recommendation task
        book_task = Task(
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
            1. If your FIRST search returns {num_recommendations} or more high-quality books with images, STOP and return them immediately.
            2. Do NOT run the exact same search query twice.
            3. Do NOT loop unnecessarily. Speed is quality.
            """,
            agent=agents['book_agent'],
            expected_output="""List of {num_recommendations} book recommendations with complete details.
            Each must include: title, author, published_year, genre, rating, description, why_recommended, similar_titles, image_url.""",
            async_execution=False,
            max_iter=5,
        )
        
        # Research task
        research_task = Task(
            description="""RESEARCH ADDITIONAL CONTEXT:
            
            User Request: {user_request}
            Media Type: {media_type}
            
            RESEARCH FOCUS:
            - Recent news about recommended genres/themes
            - Trending movies/books/shows in relevant categories
            - Cultural context and relevance
            - Critical reception and reviews
            
            PROVIDE:
            - Summary of relevant trends
            - Notable news or updates
            - Cultural context insights
            - Any relevant additional information""",
            agent=agents['research_agent'],
            expected_output="""Concise research summary with relevant trends, news, and cultural context.
            Focus on information that enhances recommendation quality.""",
            async_execution=False,
            max_iter=2,
        )
        
        # Editor task
        editor_task = Task(
            description="""FINALIZE RECOMMENDATIONS:
            
            COMPILE AND REFINE:
            - Combine recommendations from all specialists
            - Remove duplicates and ensure diversity
            - Add personalized explanations
            - Rank by relevance and quality
            - Incorporate research insights
            - HANDLE IMPOSSIBLE REQUESTS with special fields and explanations
            
            IMPOSSIBLE/CONTRADICTORY REQUEST HANDLING:
            If the Analysis Agent detected contradictions OR you identify impossible requirements:
            1. Set "is_compromise": true for affected recommendations
            2. Add "compromise_explanation" field with a clear, empathetic explanation
            3. In the explanation, specifically address:
               - What aspect of the request is impossible/contradictory
               - Why the combination doesn't exist or isn't feasible
               - What aspect was prioritized in the compromise
               - Why this recommendation is still the best match
            
            OUTPUT REQUIREMENTS:
            - Valid JSON array only
            - Exactly {num_recommendations} total recommendations
            - Mix of media types if applicable (though user will select one specific type)
            - Clear personalization for each item
            
            CRITICAL: Return ONLY valid JSON, no other text.
            CRITICAL RULES FOR URLs:
            - ONLY use image_url and trailer_url values that were provided by the Movie/Book/TV agents
            - DO NOT generate or invent URLs
            - If a URL is missing from the specialist's output, set it to null
            - NEVER create fake TMDB or YouTube URLs
            
            JSON FORMAT:
            [
              {{
                "title": "Item Title",
                "type": "movie/book/tv",
                "year": "2023",
                "genre": "Genre1, Genre2",
                "rating": 8.5,
                "description": "Brief description",
                "why_recommended": "Personalized explanation",
                "is_compromise": false,
                "compromise_explanation": "Only include if is_compromise is true - detailed explanation of the mismatch",
                "similar_titles": ["Title1", "Title2", "Title3"],
                "image_url": "https://...",
                "trailer_url": "https://www.youtube.com/...",
                "preview_url": "https://books.google.com/...",
                "seasons": "3 (if TV)",
                "episodes": "24 (if TV)"
              }}
            ]""",
            agent=agents['editor_agent'],
            expected_output="""Valid JSON array with exactly {num_recommendations} personalized media recommendations.
            Each item must have: title, type, year, genre, rating, description, why_recommended, similar_titles, image_url.
            Include 'preview_url' for books if available.
            NO additional text outside JSON.""",
            max_iter=3,
            context=[movie_task, book_task, tv_series_task, research_task],
        )
        
        logger.info("All tasks initialized successfully")
        
        return {
            'analysis_task': analysis_task,
            'movie_task': movie_task,
            'book_task': book_task,
            'tv_series_task': tv_series_task,
            'research_task': research_task,
            'editor_task': editor_task
        }
        
    except Exception as e:
        logger.error(f"Failed to setup tasks: {e}")
        raise
