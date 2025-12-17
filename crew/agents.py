"""Agent definitions for the Media Recommendation Crew."""

from crewai import Agent
from langchain_openai import ChatOpenAI
import logging

from api import movie_tools, book_tools, tv_tools, search_tools

logger = logging.getLogger(__name__)


def create_agents(llm: ChatOpenAI) -> dict:
    """
    Create all agents for the media recommendation crew.
    
    Args:
        llm: Configured ChatOpenAI instance
        
    Returns:
        Dictionary of agent instances
    """
    try:
        # Analysis Agent - Determines user intent and media type
        analysis_agent = Agent(
            role="Media Request Analyst",
            goal="""Analyze user requests to determine media type preference (movie/book/tv series) 
            and extract specific preferences like genre, mood, timeframe, and themes. 
            CRITICALLY: Detect contradictory or impossible requirements (e.g., 'happy movie about tragic event', 
            'short 3-hour film', 'lighthearted Holocaust story').""",
            backstory="""You are an expert at understanding user preferences and intent in media requests. 
            You excel at discerning whether someone wants movies, books, or TV shows, and can extract key elements 
            like genre, mood, themes, and specific requirements from their description with high accuracy. 
            You have a keen eye for contradictions - when users request combinations that are fundamentally 
            incompatible (like 'happy Titanic movie' or 'uplifting tragedy'), you identify these conflicts 
            so the recommendation team can provide the best possible compromise with clear explanations.""",
            verbose=False,
            allow_delegation=False,
            llm=llm,
            max_iter=5,
            max_rpm=20
        )
        
        # Movie Specialist Agent
        movie_agent = Agent(
            role="Movie Recommendation Specialist",
            goal="Find highly-rated, relevant movie recommendations using TMDB API and search tools",
            backstory="""You are a film expert with comprehensive knowledge of cinema across all genres and eras. 
            You use TMDB API and search tools to find current, highly-rated movies that perfectly match user preferences. 
            You consider factors like ratings, reviews, cultural relevance, and thematic alignment.""",
            verbose=False,
            allow_delegation=False,
            llm=llm,
            tools=movie_tools + [search_tools[0]],  # movie tools + similar_titles_tool
            max_iter=10,
            max_rpm=20
        )
        
        # Book Specialist Agent
        book_agent = Agent(
            role="Book Recommendation Specialist",
            goal="Find compelling book recommendations using Google Books API and search tools",
            backstory="""You are a literary expert with extensive knowledge of books across all genres and time periods. 
            You use Google Books API and search tools to find perfect book matches based on user preferences. 
            You consider writing style, author reputation, thematic elements, and reader reviews.""",
            verbose=False,
            allow_delegation=False,
            llm=llm,
            tools=book_tools + [search_tools[0]],  # book tools + similar_titles_tool
            max_iter=10,
            max_rpm=20
        )
        
        # TV Series Specialist Agent
        tv_agent = Agent(
            role="TV Series Recommendation Specialist",
            goal="Find highly-rated, relevant TV show recommendations using proper tools (Search vs Discover)",
            backstory="""You are a television expert with deep knowledge of TV series.
        CRITICAL TOOL USAGE:
        1. If the user asks for a SPECIFIC show (e.g., "Breaking Bad", "The Office"), you MUST use 'search_tv_shows' first.
        2. If the user asks for a GENRE or general recommendations (e.g., "Sci-Fi shows", "Funny sitcoms"), use 'discover_tv_shows'.
        3. Do NOT use search for genres. Do NOT use discover for specific titles.
        You understand the nuances of different TV formats.""",
            verbose=False,
            allow_delegation=False,
            llm=llm,
            tools=tv_tools + [search_tools[0]], # tv tools + similar_titles_tool
            max_iter=10,
            max_rpm=20
        )
        
        # Research Agent
        research_agent = Agent(
            role="Media Research Specialist",
            goal="Gather additional context, reviews, and trending information to enhance recommendation quality",
            backstory="""You are a research expert who finds additional context, recent reviews, 
            trending information, and cultural insights about recommended media to provide comprehensive recommendations.""",
            verbose=False,
            allow_delegation=False,
            llm=llm,
            tools=search_tools,
            max_iter=10,
            max_rpm=20
        )
        
        # Editor Agent
        editor_agent = Agent(
            role="Recommendation Editor",
            goal="Review, refine and personalize recommendations to ensure they perfectly match user needs, and clearly explain any compromises when requests are impossible",
            backstory="""You are a senior editor who ensures all recommendations are high-quality, relevant, 
            and personalized. You check for consistency, remove duplicates, add personalization touches, 
            and ensure the final list is perfectly tailored to the user's stated preferences and context. 
            When users request impossible combinations (e.g., 'happy Titanic movie'), you're skilled at 
            identifying the best compromise and crafting clear, empathetic explanations of why certain 
            aspects cannot be met, while highlighting what makes the recommendation still valuable.""",
            verbose=False,
            allow_delegation=False,
            llm=llm,
            max_iter=5,
            max_rpm=20
        )
        
        logger.info("All agents initialized successfully")
        
        return {
            'analysis_agent': analysis_agent,
            'movie_agent': movie_agent,
            'book_agent': book_agent,
            'tv_agent': tv_agent,
            'research_agent': research_agent,
            'editor_agent': editor_agent
        }
        
    except Exception as e:
        logger.error(f"Failed to setup agents: {e}")
        raise
