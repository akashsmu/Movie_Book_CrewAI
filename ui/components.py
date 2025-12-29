"""UI components for the Media Recommender application."""

import streamlit as st
import urllib.parse
from typing import List, Dict, Tuple
from ui.social_card import generate_social_card


def render_sidebar(personalization_manager) -> Tuple:
    """
    Render the sidebar with user preferences and watchlist.
    
    Args:
        personalization_manager: Instance of PersonalizationManager
        
    Returns:
        Tuple of (media_type, genre, mood, timeframe, use_personalization, user_id)
    """
    with st.sidebar:
        st.title("🎬📚 Media Recommender")
        
        # Watchlist Section
        st.markdown("---")
        st.subheader("📑 Your Bucketlist")
        
        # Show toast if item was just added
        if 'watchlist_success' in st.session_state:
            st.toast(st.session_state.watchlist_success, icon="✅")
            del st.session_state.watchlist_success
        
        if 'watchlist' in st.session_state and st.session_state.watchlist:
            for item in st.session_state.watchlist:
                if item.get('type') == 'movie':
                    emoji = "🎬"
                elif item.get('type') == 'book':
                    emoji = "📚"
                else: # tv
                    emoji = "📺"
                    
                st.markdown(f"{emoji} **{item['title']}**")
        else:
            st.info("No items in bucketlist yet. Save recommendations to see them here!")
        
        st.markdown("---")
        
        # Media type selection
        media_type = st.radio(
            "What would you like recommendations for?",
            ["Movie", "Book", "TV Series"],
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
            personalization_manager.save_user_preferences(
                user_id, media_type, genre, mood, timeframe
            )
            st.success("Preferences saved!")
        
        if st.button("Clear My History"):
            personalization_manager.clear_user_history(user_id)
            st.success("History cleared!")
        
        return media_type, genre, mood, timeframe, use_personalization, user_id


def get_external_link(title: str, media_type: str) -> str:
    """
    Generate external search link based on media type.
    
    Args:
        title: Media title
        media_type: 'movie', 'book' or 'tv'
        
    Returns:
        URL string
    """
    encoded_title = urllib.parse.quote(title)
    if media_type == 'movie':
        return f"https://www.justwatch.com/us/search?q={encoded_title}"
    elif media_type == 'tv':
        return f"https://www.justwatch.com/us/search?q={encoded_title}"
    else:  # book
        return f"https://www.goodreads.com/search?q={encoded_title}"


def display_recommendations(recommendations: List[Dict], personalization_manager, user_id: str):
    """
    Display recommendations in a beautiful card format.
    
    Args:
        recommendations: List of recommendation dictionaries
        personalization_manager: Instance of PersonalizationManager
        user_id: Current user ID
    """
    st.markdown("---")
    st.markdown(f"### 🎉 Recommendations for: *{st.session_state.user_input}*")
    
    # Check if any recommendations are compromises and display alert
    compromise_recs = [rec for rec in recommendations if rec.get('is_compromise', False)]
    if compromise_recs:
        st.markdown("""
        <div class="compromise-alert">
            <div class="compromise-alert-title">⚠️ About Your Request</div>
            <div class="compromise-alert-text">
                Your request contained contradictory or impossible requirements. 
                We've provided the best possible recommendations and explained the compromises below.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Social Share
    with st.expander("📤 Share Recommendations"):
        col_s1, col_s2 = st.columns([1, 2])
        with col_s1:
            if st.button("📸 Generate Shareable Card"):
                try:
                    # Determine a title context if possible
                    title_ctx = "My AI Recommendations"
                    # If we have the user input in session (we usually do via app.py), we could use it, 
                    # but here we only have the list. We'll stick to a generic title or user ID context if needed.
                    
                    # Get user input for the prompt description
                    user_prompt = st.session_state.get('user_input', '')
                    
                    # Pass user_prompt as prompt_desc
                    img_buf = generate_social_card(recommendations, title_ctx, prompt_desc=user_prompt)
                    st.session_state.share_image = img_buf
                except Exception as e:
                    st.error(f"Failed to generate image: {e}")
        
        if 'share_image' in st.session_state:
            with col_s2:
                st.image(st.session_state.share_image, caption="Ready to share!", use_container_width=True)
                st.download_button(
                    label="⬇️ Download Image",
                    data=st.session_state.share_image,
                    file_name="ai_recommendations.png",
                    mime="image/png"
                )

    for i, rec in enumerate(recommendations, 1):
        with st.container():
            col1, col2 = st.columns([1, 3])
            
            with col1:
                # Determine emoji fallback
                if rec.get('type') == 'movie':
                    emoji = "🎬"
                elif rec.get('type') == 'book':
                    emoji = "📚" 
                else: # tv
                    emoji = "📺"
                
                # Display proper image or fallback emoji
                if rec.get('image_url'):
                    try:
                        st.image(rec['image_url'], use_container_width=True, width="stretch")
                    except Exception:
                        st.markdown(f"<h3>{emoji} #{i}</h3>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<h3>{emoji} #{i}</h3>", unsafe_allow_html=True)
                
                # Render rating
                rating = rec.get('rating', None)
                if rating is not None:
                    try:
                        r = float(rating)
                        if rec.get('type') == 'book':
                            st.metric("Rating", f"{r}/5")
                        else:
                            st.metric("Rating", f"{r}/10")
                    except Exception:
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
                    # Display duration or seasons
                    if rec.get('type') == 'tv':
                        metadata = []
                        if rec.get('seasons'):
                            metadata.append(f"{rec['seasons']} Seasons")
                        if rec.get('episodes'):
                            metadata.append(f"{rec['episodes']} Episodes")
                        
                        if metadata:
                            st.markdown(f"**Length:** {' | '.join(metadata)}")
                    elif rec.get('duration'):
                        st.markdown(f"**Duration:** {rec['duration']}")
                
                # Description
                st.markdown(f"**Description:** {rec.get('description', 'No description available.')}")
                
                # Compromise explanation
                if rec.get('is_compromise', False) and rec.get('compromise_explanation'):
                    st.warning(f"**⚠️ Why this specific choice:** {rec['compromise_explanation']}")
                
                # Why it matches
                if rec.get('why_recommended'):
                    with st.expander("Why this was recommended"):
                        st.write(rec['why_recommended'])
                
                # Similar titles
                if rec.get('similar_titles'):
                    with st.expander("Similar titles you might like"):
                        for similar in rec['similar_titles'][:3]:
                            st.write(f"• {similar}")
                
                # Watch Trailer / External Actions
                if rec.get('type') in ['movie', 'tv']:
                    if rec.get('trailer_url'):
                        with st.expander("🎬 Watch Trailer"):
                            st.video(rec['trailer_url'])
                    
                    external_link = get_external_link(rec['title'], rec['type'])
                    st.link_button("📺 Watch on JustWatch", external_link)
                    
                elif rec.get('type') == 'book':
                    col_links = st.columns(2)
                    with col_links[0]:
                        if rec.get('preview_url'):
                            st.link_button("📖 Read Sample", rec['preview_url'], use_container_width=True)
                    with col_links[1]:
                        external_link = get_external_link(rec['title'], 'book')
                        st.link_button("📖 Buy on Goodreads", external_link, use_container_width=True)
                
                # Action buttons
                col_actions = st.columns(3)
                with col_actions[0]:
                    if st.button("👍 Like", key=f"like_{i}"):
                        personalization_manager.record_feedback(user_id, rec, True)
                        st.success("Thanks for your feedback!")
                with col_actions[1]:
                    if st.button("👎 Dislike", key=f"dislike_{i}"):
                        personalization_manager.record_feedback(user_id, rec, False)
                        st.success("Thanks for your feedback!")
                with col_actions[2]:
                    # Check by title and type instead of object identity
                    is_in_watchlist = any(
                        w.get('title') == rec.get('title') and w.get('type') == rec.get('type') 
                        for w in st.session_state.watchlist
                    )
                    
                    if is_in_watchlist:
                        if st.button("🗑️ Unsave", key=f"unsave_{i}"):
                            personalization_manager.remove_from_watchlist(user_id, rec)
                            st.session_state.watchlist = personalization_manager.get_watchlist(user_id)
                            st.session_state.watchlist_success = f"Removed '{rec['title']}' from Watchlist."
                            st.rerun()
                    else:
                        if st.button("💾 Save", key=f"save_{i}"):
                            personalization_manager.add_to_watchlist(user_id, rec)
                            st.session_state.watchlist = personalization_manager.get_watchlist(user_id)
                            st.session_state.watchlist_success = f"Added '{rec['title']}' to Watchlist!"
                            st.rerun()
                
                # More Like This Pivot
                if st.button("✨ More Like This", key=f"pivot_{i}", help="Find other recommendations like this one"):
                    base_query = f"Find {rec.get('type', 'movie')}s similar to '{rec['title']}'"
                    
                    similar_context = ""
                    if rec.get('similar_titles'):
                        seeds = ", ".join(rec['similar_titles'][:3])
                        similar_context = f". Specific examples of similar content include: {seeds}. Please behave like a recommender system that pivots off these specific examples."
                    
                    st.session_state.pivot_request = base_query + similar_context
                    st.rerun()
            
            st.markdown("---")
