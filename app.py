import streamlit as st
import os
from datetime import datetime
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv
from crew import MediaRecommendationCrew
from personalization_manager import PersonalizationManager
from threading import Thread
from api.movie_tools import DiscoverMoviesTool
from api.tv_tools import DiscoverTVTool
from ui import get_app_css, render_sidebar, display_recommendations

# Load environment variables
load_dotenv()

class MediaRecommenderApp:
    def __init__(self):
        self.setup_page_config()
        self.personalization_manager = PersonalizationManager()
        
        # Initialize session state for user_id if not present
        if 'user_id' not in st.session_state:
            st.session_state.user_id = "user_1"
            
        # Initialize session state for watchlist from persistent storage
        if 'watchlist' not in st.session_state:
            st.session_state.watchlist = self.personalization_manager.get_watchlist(st.session_state.user_id)
    
    def setup_page_config(self):
        st.set_page_config(
            page_title="AI Media Recommender",
            page_icon="🎬📚",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    
    def handle_recommendation_request(self, user_input, media_type, genre, mood, timeframe, num_recommendations, use_personalization, user_id):
        """Handle the core logic of fetching and displaying recommendations"""
        
        # Mapping of tools to agent roles for fallback identification
        TOOL_TO_AGENT = {
            # Movie Agent Tools
            'search_movies': 'Movie Recommendation Specialist',
            'get_movie_details': 'Movie Recommendation Specialist', 
            'get_popular_movies': 'Movie Recommendation Specialist',
            'discover_movies': 'Movie Recommendation Specialist',
            
            # Book Agent Tools
            'search_books': 'Book Recommendation Specialist',
            'get_book_details': 'Book Recommendation Specialist',
            
            # Research Agent Tools
            'search_news': 'Media Research Specialist',
            'search_trending_media': 'Media Research Specialist',
            'find_similar_titles': 'Media Research Specialist', # Shared tool but often used by Research/Specialists
            
            # Default
            'Calculator': 'Analyst',
        }

        # Callback to stream thoughts
        def stream_thought(step_output):
            try:
                # Extract agent name
                agent_name = None
                
                # 1. Try direct attribute
                if hasattr(step_output, 'agent') and hasattr(step_output.agent, 'role'):
                    agent_name = step_output.agent.role
                
                # 2. Try string representation if needed
                if not agent_name and hasattr(step_output, 'agent'):
                     agent_name = str(step_output.agent)
                
                # Extract tool
                tool_name = ""
                if hasattr(step_output, 'tool') and step_output.tool:
                    tool_name = step_output.tool
                
                # 3. Fallback: Infer agent from tool
                if (not agent_name or "Unknown" in agent_name) and tool_name:
                    agent_name = TOOL_TO_AGENT.get(tool_name, "AI Specialist")
                
                # 4. Final Fallback
                if not agent_name or "Unknown" in agent_name:
                    agent_name = "Media Recommender AI"

                # Extract thought
                thought = ""
                if hasattr(step_output, 'thought') and step_output.thought:
                    thought = step_output.thought.strip()
                
                # If we have a thought, display it
                if thought:
                     # Clean up "Thought:" prefix if present
                    if thought.startswith("Thought:"):
                        thought = thought[len("Thought:"):].strip()
                    st.write(f"**🧠 {agent_name}:** {thought}")
                
                # If tool usage
                if tool_name:
                    st.caption(f"🔧 Using tool: `{tool_name}`")
                    
            except Exception as e:
                # print(f"DEBUG: Error in callback: {e}") # Debug only
                pass # safely ignore callback errors to not break main flow

        # Use st.status to show progress
        with st.status("🤖 AI Agents are working...", expanded=True) as status:
            try:
                # Show active configuration to user so they understand the context
                config_details = [
                    f"**Media Type:** {media_type}",
                    f"**Genre:** {genre}",
                    f"**Mood:** {mood}",
                    f"**Timeframe:** {timeframe}"
                ]
                st.markdown(f"📋 **Configuration**: {' | '.join(config_details)}")
                
                st.write("Initializing crew...")
                
                # Get personalized context if enabled
                personalization_context = ""
                if use_personalization:
                    personalization_context = self.personalization_manager.get_user_context(user_id)
                
                # Initialize crew and get recommendations
                crew = MediaRecommendationCrew()
                
                # Map UI media type to internal type
                internal_media_type = media_type.lower()
                if media_type == "TV Series":
                    internal_media_type = "tv"
                
                recommendations = crew.run(
                    user_request=user_input,
                    media_type=internal_media_type,
                    genre=genre if genre != "Any" else None,
                    mood=mood if mood != "Any" else None,
                    timeframe=timeframe if timeframe != "Any" else None,
                    num_recommendations=num_recommendations,
                    personalization_context=personalization_context,
                    step_callback=stream_thought
                )
                
                # Store recommendations in session
                st.session_state.recommendations = recommendations
                st.session_state.user_input = user_input
                
                # Update user history
                if use_personalization:
                   self.personalization_manager.update_user_history(
                        user_id, user_input, recommendations
                    )
                
                status.update(label="✅ Recommendations found!", state="complete", expanded=False)
                return True
                
            except Exception as e:
                status.update(label="❌ Error occurred", state="error")
                st.error(f"Error getting recommendations: {str(e)}")
                return False

    def render_main_interface(self):
        # Apply CSS from UI module
        st.markdown(get_app_css(), unsafe_allow_html=True)
        st.markdown('<div class="main-header">🎬📚 AI Media Recommender</div>', unsafe_allow_html=True)
        
        # Get sidebar inputs from UI module
        media_type, genre, mood, timeframe, use_personalization, user_id = render_sidebar(self.personalization_manager)

        # --- Cache Warming Logic ---
        if 'last_genre' not in st.session_state:
            st.session_state.last_genre = genre
        
        # If genre changed to something specific, warm the cache
        if genre != "Any" and genre != st.session_state.last_genre:
            st.session_state.last_genre = genre
            
            def warm_cache(selected_genre, m_type):
                try:
                    # Determine which tool to warm based on media type
                    if m_type == "TV Series":
                        tool = DiscoverTVTool()
                        # call internal _run to trigger cache decorator
                        tool._run(genre=selected_genre)
                    elif m_type == "Movie":
                        tool = DiscoverMoviesTool()
                        tool._run(genre=selected_genre)
                    # (Book API doesn't have a broad discovery tool same way, skipping)
                    print(f"🔥 Cache warmed for {m_type} - {selected_genre}")
                except Exception as e:
                    print(f"Cache warming failed: {e}")

            # Start background thread
            thread = Thread(target=warm_cache, args=(genre, media_type))
            thread.daemon = True
            thread.start()
        # ---------------------------
        
        # Handle Pivot Request (More Like This)
        if 'pivot_request' in st.session_state:
            pivot_query = st.session_state.pivot_request
            del st.session_state.pivot_request # Clear immediately
            
            # Update session state for the text area to pick up
            st.session_state.temp_input_value = pivot_query
            
            # Clean up old recommendations before generating new ones to avoid confusion
            if 'recommendations' in st.session_state:
                del st.session_state.recommendations
            
            # Auto-trigger search
            self.handle_recommendation_request(
                pivot_query, media_type, genre, mood, timeframe, 
                st.session_state.get('last_num_recs', 3), # Use last count or default
                use_personalization, user_id
            )
            st.rerun()

        # Main input area
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Check for temp input value from pivot
            default_input = st.session_state.get('temp_input_value', "")
            if 'temp_input_value' in st.session_state:
                del st.session_state.temp_input_value
                
            user_input = st.text_area(
                "What are you in the mood for?",
                value=default_input,
                placeholder="E.g., 'I want an exciting sci-fi movie with great visuals' or 'Recommend me a thought-provoking book about AI'",
                height=100
            )
            
            # Advanced options
            with st.expander("Advanced Options"):
                col3, col4 = st.columns(2)
                with col3:
                    num_recommendations = st.slider("Number of recommendations", 1, 10, 3)
                    # Store for pivot usage
                    st.session_state.last_num_recs = num_recommendations
                    
                    diversity = st.slider("Diversity of recommendations", 1, 10, 7)
                with col4:
                    include_reviews = st.checkbox("Include reviews", value=True)
                    include_similar = st.checkbox("Include similar titles", value=True)
        
        with col2:
            st.subheader("Quick Examples")
            examples = [
                "Mind-bending thriller like Inception",
                "Feel-good romance book for weekend",
                "Historical fiction about ancient Rome",
                "Award-winning movies from 2020s"
            ]
            for example in examples:
                if st.button(example, key=example):
                    st.session_state.example_input = example
        
        # Recommendation button
        if st.button("🎯 Get Recommendations", type="primary", use_container_width=True):
            if user_input or 'example_input' in st.session_state:
                actual_input = user_input if user_input else st.session_state.get('example_input', '')
                
                self.handle_recommendation_request(
                    actual_input, media_type, genre, mood, timeframe, 
                    num_recommendations, use_personalization, user_id
                )
            
            else:
                st.warning("Please describe what you're looking for or select a quick example.")
        
        # Display recommendations if available
        if 'recommendations' in st.session_state:
            display_recommendations(st.session_state.recommendations, self.personalization_manager, user_id)
            
    def run(self):
        self.render_main_interface()

if __name__ == "__main__":
    app = MediaRecommenderApp()
    app.run()
