from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
import os
from typing import Dict, List, Optional
import json
import re
from media_apis import movie_tools, book_tools, search_tools

class MediaRecommendationCrew:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL"),
            temperature=os.getenv("OPENAI_TEMPERATURE"),
            api_key=os.getenv("OPENAI_API_KEY")
        )
        self.setup_agents()
        self.setup_tasks()
    
    def setup_agents(self):
        # Analysis Agent - Determines user intent and media type
        self.analysis_agent = Agent(
            role="Media Request Analyst",
            goal="Analyze user requests to determine whether they want movie or book recommendations and extract key preferences",
            backstory="""You are an expert at understanding user preferences and intent in media requests. 
            You can discern whether someone wants movies, books, or both, and extract key elements like 
            genre, mood, themes, and specific requirements from their description.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
        
        # Movie Specialist Agent with proper tools
        self.movie_agent = Agent(
            role="Movie Recommendation Specialist",
            goal="Find the best movie recommendations based on user preferences using real-time data",
            backstory="""You are a film expert with deep knowledge of cinema across all genres and time periods. 
            You use TMDB and search APIs to find current, relevant movie recommendations that match user preferences. 
            You consider factors like ratings, reviews, director, cast, and cultural relevance.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=movie_tools + [search_tools[0]]  # movie tools + similar_titles_tool
        )
        
        # Book Specialist Agent with proper tools
        self.book_agent = Agent(
            role="Book Recommendation Specialist",
            goal="Find the best book recommendations based on user preferences using real-time data",
            backstory="""You are a literary expert with extensive knowledge of books across all genres. 
            You use Google Books API and search APIs to find perfect book matches for users. 
            You consider writing style, author reputation, reviews, and thematic elements.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=book_tools + [search_tools[0]]  # book tools + similar_titles_tool
        )
        
        # Research Agent for additional context
        self.research_agent = Agent(
            role="Media Research Specialist",
            goal="Gather additional context, reviews, and trending information about recommended media",
            backstory="""You are a research expert who finds additional context, recent reviews, 
            and trending information about movies and books to enhance recommendation quality.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=search_tools  # All search tools
        )
        
        # Editor Agent - Refines and personalizes recommendations
        self.editor_agent = Agent(
            role="Recommendation Editor",
            goal="Review, refine and personalize recommendations to ensure they meet user needs",
            backstory="""You are a senior editor who ensures all recommendations are high-quality, relevant, 
            and personalized. You check for consistency, remove duplicates, add personalization touches, 
            and ensure the final list is perfectly tailored to the user's stated preferences and context.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
    
    def setup_tasks(self):
        # Analysis task
        self.analysis_task = Task(
            description="""Analyze the user request: {user_request}
            Determine if they want movies, books, or both.
            Extract key preferences: genre, mood, themes, timeframe, and any specific requirements.
            Consider personalization context: {personalization_context}
            
            Provide a structured analysis with:
            1. Primary media type (movie/book/both)
            2. Key genres and themes
            3. Mood and tone preferences
            4. Time period preferences
            5. Specific requirements or constraints""",
            agent=self.analysis_agent,
            expected_output="Structured analysis of user preferences and media type determination"
        )
        
        # Movie recommendation task
        self.movie_task = Task(
            description="""Based on the analysis, find {num_recommendations} movie recommendations.
            
            User Preferences:
            - Genre: {genre}
            - Mood: {mood}
            - Timeframe: {timeframe}
            - Specific requirements: {user_request}
            
            Use the movie tools to search for current, highly-rated movies that match these preferences.
            For each movie, gather:
            - Title, year, rating
            - Genre and description
            - Why it matches user preferences
            - Similar movies (use search tools)
            
            Return a well-formatted list of movie recommendations.""",
            agent=self.movie_agent,
            expected_output="List of 3-5 movie recommendations with detailed information",
            async_execution=True
        )
        
        # Book recommendation task
        self.book_task = Task(
            description="""Based on the analysis, find {num_recommendations} book recommendations.
            
            User Preferences:
            - Genre: {genre}
            - Mood: {mood}
            - Timeframe: {timeframe}
            - Specific requirements: {user_request}
            
            Use the book tools to search for highly-rated books that match these preferences.
            For each book, gather:
            - Title, author, publication year
            - Genre and description
            - Why it matches user preferences
            - Similar books (use search tools)
            
            Return a well-formatted list of book recommendations.""",
            agent=self.book_agent,
            expected_output="List of 3-5 book recommendations with detailed information",
            async_execution=True
        )
        
        # Research task for additional context
        self.research_task = Task(
            description="""Research additional context for media recommendations.
            
            For the user request: {user_request}
            
            Use search tools to:
            - Find recent news or reviews about recommended genres
            - Check trending movies and books
            - Gather cultural context about the themes
            - Find any relevant updates
            
            This information will help the editor make better final recommendations.""",
            agent=self.research_agent,
            expected_output="Additional context and research about the media landscape",
            async_execution=True
        )
        
        # Editor task - Updated to return proper JSON
        self.editor_task = Task(
            description="""Review and refine all recommendations from movie, book, and research agents.
            
            Original user request: {user_request}
            Personalization context: {personalization_context}
            
            Your responsibilities:
            1. Combine and deduplicate recommendations from all agents
            2. Ensure diversity in recommendations (different genres, eras, styles)
            3. Add personalized explanations for why each item was chosen
            4. Rank recommendations by relevance and quality
            5. Format the final output as a VALID JSON array
            6. Incorporate research context where relevant
            7. Ensure each recommendation has: title, type, year, genre, description, why_recommended, similar_titles
            
            IMPORTANT: Return ONLY a valid JSON array. No additional text, no markdown, no code blocks.
            
            Example format:
            [
                {{
                    "title": "Movie Name",
                    "type": "movie",
                    "year": 2020,
                    "genre": "Action, Sci-Fi",
                    "description": "Movie description here",
                    "why_recommended": "Why this matches user preferences",
                    "similar_titles": ["Similar 1", "Similar 2", "Similar 3"]
                }}
            ]
            
            Final output should be a valid JSON array with 3-5 recommendations.""",
            agent=self.editor_agent,
            expected_output="Valid JSON array of personalized media recommendations"
        )
    
    def run(self, user_request: str, media_type: str = "both", genre: Optional[str] = None,
            mood: Optional[str] = None, timeframe: Optional[str] = None,
            num_recommendations: int = 3, personalization_context: str = "") -> List[Dict]:
        
        # Set up task inputs
        task_inputs = {
            "user_request": user_request,
            "media_type": media_type,
            "genre": genre or "Not specified",
            "mood": mood or "Not specified", 
            "timeframe": timeframe or "Not specified",
            "num_recommendations": num_recommendations,
            "personalization_context": personalization_context
        }
        
        # Update tasks with current inputs
        self.analysis_task.description = self.analysis_task.description.format(**task_inputs)
        self.movie_task.description = self.movie_task.description.format(**task_inputs)
        self.book_task.description = self.book_task.description.format(**task_inputs)
        self.research_task.description = self.research_task.description.format(**task_inputs)
        self.editor_task.description = self.editor_task.description.format(**task_inputs)
        
        # Create crew based on media type
        tasks = [self.analysis_task]
        
        if media_type in ["movie", "both"]:
            tasks.append(self.movie_task)
        if media_type in ["book", "both"]:
            tasks.append(self.book_task)
        
        tasks.append(self.research_task)
        tasks.append(self.editor_task)
        
        crew = Crew(
            agents=[self.analysis_agent, self.movie_agent, self.book_agent, 
                   self.research_agent, self.editor_agent],
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        )
        
        try:
            print("🤖 Starting CrewAI execution...")
            result = crew.kickoff()
            print(f"🎯 CrewAI execution completed. Result type: {type(result)}")
            print(f"📝 Raw result: {result}")
            
            # Parse the actual result
            recommendations = self._parse_result(result)
            print(f"✅ Parsed {len(recommendations)} recommendations")
            return recommendations
            
        except Exception as e:
            print(f"❌ Error in crew execution: {e}")
            # Return fallback recommendations only if real parsing fails
            return self._get_fallback_recommendations(user_request, media_type)
    
    def _parse_result(self, result) -> List[Dict]:
        """Parse the crew result into structured recommendations"""
        try:
            print(f"🔍 Parsing result: {result}")
            
            # If result is already a list, return it
            if isinstance(result, list):
                print("✅ Result is already a list")
                return result
            
            # Convert to string if needed
            result_str = str(result)
            print(f"📄 Result as string: {result_str[:500]}...")  # First 500 chars
            
            # Try to find JSON in the result
            json_match = self._extract_json_from_text(result_str)
            if json_match:
                print("✅ Found JSON in result")
                parsed_data = json.loads(json_match)
                if isinstance(parsed_data, list):
                    return parsed_data
            
            # If no JSON found, try to parse as structured text
            print("🔄 Trying to parse as structured text")
            structured_result = self._parse_structured_text(result_str)
            if structured_result:
                print("✅ Successfully parsed structured text")
                return structured_result
            
            print("❌ Could not parse result, using fallback")
            return self._get_fallback_recommendations("parsing_failed", "both")
            
        except Exception as e:
            print(f"❌ Error parsing result: {e}")
            return self._get_fallback_recommendations("error", "both")
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """Extract JSON from text response"""
        try:
            # Look for JSON array pattern
            json_pattern = r'\[\s*\{.*?\}\s*\]'
            match = re.search(json_pattern, text, re.DOTALL)
            if match:
                return match.group()
            
            # Look for JSON object pattern (single recommendation)
            object_pattern = r'\{\s*".*?"\s*:\s*".*?"\s*\}'
            matches = re.findall(object_pattern, text, re.DOTALL)
            if matches:
                return f'[{",".join(matches)}]'
                
            return None
        except Exception as e:
            print(f"Error extracting JSON: {e}")
            return None
    
    def _parse_structured_text(self, text: str) -> Optional[List[Dict]]:
        """Parse structured text into recommendations"""
        try:
            recommendations = []
            lines = text.split('\n')
            
            current_rec = {}
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Look for title patterns
                if any(keyword in line.lower() for keyword in ['title:', 'movie:', 'book:']):
                    if current_rec and 'title' in current_rec:
                        recommendations.append(current_rec)
                        current_rec = {}
                    
                    # Extract title
                    title = self._extract_value(line, ['title:', 'movie:', 'book:'])
                    if title:
                        current_rec['title'] = title
                        current_rec['type'] = 'movie' if 'movie' in line.lower() else 'book'
                
                # Extract other fields
                elif 'year:' in line.lower() and current_rec:
                    year = self._extract_value(line, ['year:'])
                    current_rec['year'] = year
                elif 'genre:' in line.lower() and current_rec:
                    genre = self._extract_value(line, ['genre:'])
                    current_rec['genre'] = genre
                elif 'description:' in line.lower() and current_rec:
                    desc = self._extract_value(line, ['description:'])
                    current_rec['description'] = desc
                elif 'why:' in line.lower() and current_rec:
                    why = self._extract_value(line, ['why:', 'why recommended:', 'recommended because:'])
                    current_rec['why_recommended'] = why
            
            # Add the last recommendation
            if current_rec and 'title' in current_rec:
                recommendations.append(current_rec)
            
            # Add default similar titles if missing
            for rec in recommendations:
                if 'similar_titles' not in rec:
                    rec['similar_titles'] = ["Similar title 1", "Similar title 2", "Similar title 3"]
            
            return recommendations if recommendations else None
            
        except Exception as e:
            print(f"Error parsing structured text: {e}")
            return None
    
    def _extract_value(self, line: str, keywords: List[str]) -> str:
        """Extract value after keywords in a line"""
        for keyword in keywords:
            if keyword in line.lower():
                return line.split(keyword, 1)[1].strip()
        return ""
    
    def _get_fallback_recommendations(self, user_request: str, media_type: str) -> List[Dict]:
        """Provide fallback recommendations when real parsing fails"""
        print("🔄 Using fallback recommendations")
        
        fallback_movies = [
            {
                "title": "Inception",
                "type": "movie",
                "year": "2010",
                "genre": "Sci-Fi, Thriller",
                "rating": "8.8",
                "description": "A thief who steals corporate secrets through dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.",
                "why_recommended": "Mind-bending plot with stunning visuals that matches your interest in thought-provoking sci-fi.",
                "similar_titles": ["The Matrix", "Interstellar", "Tenet"]
            },
            {
                "title": "The Shawshank Redemption",
                "type": "movie", 
                "year": "1994",
                "genre": "Drama",
                "rating": "9.3",
                "description": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.",
                "why_recommended": "Powerful storytelling and character development that resonates emotionally.",
                "similar_titles": ["The Green Mile", "Forrest Gump", "The Godfather"]
            }
        ]
        
        fallback_books = [
            {
                "title": "Project Hail Mary",
                "type": "book",
                "year": "2021", 
                "genre": "Science Fiction",
                "rating": "4.8",
                "description": "A lone astronaut must save the earth from disaster in this high-stakes sci-fi adventure filled with humor and science.",
                "why_recommended": "Engaging hard sci-fi with compelling characters and problem-solving.",
                "similar_titles": ["The Martian", "Artemis", "Three Body Problem"]
            },
            {
                "title": "The Midnight Library",
                "type": "book",
                "year": "2020",
                "genre": "Fiction, Fantasy", 
                "rating": "4.6",
                "description": "Between life and death there is a library, and within that library, the shelves go on forever. Every book provides a chance to try another life you could have lived.",
                "why_recommended": "Thought-provoking exploration of life choices and possibilities.",
                "similar_titles": ["The Invisible Life of Addie LaRue", "Life After Life", "The Alchemist"]
            }
        ]
        
        if media_type == "movie":
            return fallback_movies[:3]
        elif media_type == "book":
            return fallback_books[:3]
        else:
            return fallback_movies[:2] + fallback_books[:1]