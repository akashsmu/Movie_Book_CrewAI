import streamlit as st
import os
from datetime import datetime
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv
from media_crew import MediaRecommendationCrew
from personalization_manager import PersonalizationManager

# Load environment variables
load_dotenv()

class MediaRecommenderApp:
    def __init__(self):
        self.setup_page_config()
        self.personalization_manager = PersonalizationManager()
        
    def setup_page_config(self):
        st.set_page_config(
            page_title="AI Media Recommender",
            page_icon="🎬📚",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    
    def setup_css(self):
        st.markdown("""
        <style>
        .main-header {
            font-size: 3rem;
            color: #1f77b4;
            text-align: center;
            margin-bottom: 2rem;
        }
        .recommendation-card {
            padding: 1.5rem;
            border-radius: 10px;
            border: 1px solid #ddd;
            margin: 1rem 0;
            background-color: #f9f9f9;
        }
        .success-message {
            padding: 1rem;
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 5px;
            margin: 1rem 0;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def render_sidebar(self):
        with st.sidebar:
            st.title("🎬📚 Media Recommender")
            st.markdown("---")
            
            # Media type selection
            media_type = st.radio(
                "What would you like recommendations for?",
                ["Movie", "Book", "Both"],
                index=0
            )
            
            # User preferences
            st.subheader("Your Preferences")
            genre = st.selectbox(
                "Preferred Genre",
                ["Any", "Action", "Comedy", "Drama", "Sci-Fi", "Fantasy", "Mystery", 
                 "Romance", "Thriller", "Horror", "Adventure", "Biography", "History"]
            )
            
            mood = st.selectbox(
                "Current Mood",
                ["Any", "Happy", "Excited", "Relaxed", "Thoughtful", "Adventurous", 
                 "Nostalgic", "Inspired", "Curious"]
            )
            
            timeframe = st.selectbox(
                "Time Period Preference",
                ["Any", "Recent", "Classic", "90s", "2000s", "2010s", "2020s"]
            )
            
            # Personalization toggle
            use_personalization = st.checkbox("Use my personalization profile", value=True)
            
            # User profile management
            st.markdown("---")
            st.subheader("Your Profile")
            user_id = st.text_input("User ID (for saving preferences)", "user_123")
            
            if st.button("Save Current Preferences"):
                self.personalization_manager.save_user_preferences(
                    user_id, media_type, genre, mood, timeframe
                )
                st.success("Preferences saved!")
            
            if st.button("Clear My History"):
                self.personalization_manager.clear_user_history(user_id)
                st.success("History cleared!")
            
            return media_type, genre, mood, timeframe, use_personalization, user_id
    
    def render_main_interface(self):
        st.markdown('<div class="main-header">🎬📚 AI Media Recommender</div>', unsafe_allow_html=True)
        
        # Get sidebar inputs
        media_type, genre, mood, timeframe, use_personalization, user_id = self.render_sidebar()
        
        # Main input area
        col1, col2 = st.columns([2, 1])
        
        with col1:
            user_input = st.text_area(
                "What are you in the mood for?",
                placeholder="E.g., 'I want an exciting sci-fi movie with great visuals' or 'Recommend me a thought-provoking book about AI'",
                height=100
            )
            
            # Advanced options
            with st.expander("Advanced Options"):
                col3, col4 = st.columns(2)
                with col3:
                    num_recommendations = st.slider("Number of recommendations", 1, 10, 3)
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
                
                with st.spinner("🤔 Analyzing your request and searching for the best recommendations..."):
                    try:
                        # Get personalized context if enabled
                        personalization_context = ""
                        if use_personalization:
                            personalization_context = self.personalization_manager.get_user_context(user_id)
                        
                        # Initialize crew and get recommendations
                        crew = MediaRecommendationCrew()
                        recommendations = crew.run(
                            user_request=actual_input,
                            media_type=media_type.lower(),
                            genre=genre if genre != "Any" else None,
                            mood=mood if mood != "Any" else None,
                            timeframe=timeframe if timeframe != "Any" else None,
                            num_recommendations=num_recommendations,
                            personalization_context=personalization_context
                        )
                        
                        # Store recommendations in session
                        st.session_state.recommendations = recommendations
                        st.session_state.user_input = actual_input
                        
                        # Update user history
                        if use_personalization:
                            self.personalization_manager.update_user_history(
                                user_id, actual_input, recommendations
                            )
                        
                    except Exception as e:
                        st.error(f"Error getting recommendations: {str(e)}")
            
            else:
                st.warning("Please describe what you're looking for or select a quick example.")
        
        # Display recommendations if available
        if 'recommendations' in st.session_state:
            self.display_recommendations(st.session_state.recommendations,user_id=user_id)
    
    def display_recommendations(self, recommendations, user_id:str):
        st.markdown("---")
        st.markdown(f"### 🎉 Recommendations for: *{st.session_state.user_input}*")
        
        for i, rec in enumerate(recommendations, 1):
            with st.container():
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    # Display proper image or fallback emoji
                    if rec.get('image_url'):
                        try:
                            st.image(rec['image_url'], use_container_width=True, width="stretch")
                        except Exception:
                            # Fallback if image fails to load
                            emoji = "🎬" if rec.get('type') == 'movie' else "📚"
                            st.markdown(f"<h3>{emoji} #{i}</h3>", unsafe_allow_html=True)
                    else:
                        emoji = "🎬" if rec.get('type') == 'movie' else "📚"
                        st.markdown(f"<h3>{emoji} #{i}</h3>", unsafe_allow_html=True)
                    
                    # Render rating for movies (out of 10) and books (out of 5).
                    rating = rec.get('rating', None)
                    if rating is not None:
                        try:
                            # numeric ratings normalized earlier (float) - detect scale
                            r = float(rating)
                            if rec.get('type') == 'book':
                                st.metric("Rating", f"{r}/5")
                            else:
                                # default to /10 for movies
                                st.metric("Rating", f"{r}/10")
                        except Exception:
                            # If rating is a string like 'N/A' or already formatted
                            st.metric("Rating", str(rating))
                
                with col2:
                    st.markdown(f"#### {rec['title']} ({rec.get('year', 'N/A')})")
                    
                    # Genre and type badges
                    col_badges = st.columns(4)
                    with col_badges[0]:
                        st.markdown(f"**Type:** {rec.get('type', '').title()}")
                    with col_badges[1]:
                        st.markdown(f"**Genre:** {rec.get('genre', 'N/A')}")
                    with col_badges[2]:
                        if rec.get('duration'):
                            st.markdown(f"**Duration:** {rec['duration']}")
                    
                    # Description
                    st.markdown(f"**Description:** {rec.get('description', 'No description available.')}")
                    
                    # Why it matches
                    if rec.get('why_recommended'):
                        with st.expander("Why this was recommended"):
                            st.write(rec['why_recommended'])
                    
                    # Similar titles
                    if rec.get('similar_titles'):
                        with st.expander("Similar titles you might like"):
                            for similar in rec['similar_titles'][:3]:
                                st.write(f"• {similar}")
                                
                    # Watch Trailer
                    if rec.get('trailer_url'):
                        with st.expander("🎬 Watch Trailer"):
                            st.video(rec['trailer_url'])
                    
                    # Action buttons
                    col_actions = st.columns(3)
                    with col_actions[0]:
                        if st.button("👍 Like", key=f"like_{i}"):
                            self.personalization_manager.record_feedback(user_id, rec, True)
                            st.success("Thanks for your feedback!")
                    with col_actions[1]:
                        if st.button("👎 Dislike", key=f"dislike_{i}"):
                            self.personalization_manager.record_feedback(user_id, rec, False)
                            st.success("Thanks for your feedback!")
                    with col_actions[2]:
                        if st.button("💾 Save", key=f"save_{i}"):
                            st.success("Recommendation saved!")
                
                st.markdown("---")
    
    def run(self):
        self.setup_css()
        self.render_main_interface()

if __name__ == "__main__":
    app = MediaRecommenderApp()
    app.run()