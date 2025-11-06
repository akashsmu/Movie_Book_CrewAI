import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

class PersonalizationManager:
    def __init__(self, storage_file: str = "user_preferences.json"):
        self.storage_file = storage_file
        self.user_data = self._load_user_data()
    
    def _load_user_data(self) -> Dict:
        """Load user data from storage file"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading user data: {e}")
        return {}
    
    def _save_user_data(self):
        """Save user data to storage file"""
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(self.user_data, f, indent=2)
        except Exception as e:
            print(f"Error saving user data: {e}")
    
    def save_user_preferences(self, user_id: str, media_type: str, genre: str, 
                            mood: str, timeframe: str):
        """Save user preferences"""
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                'preferences': {},
                'history': [],
                'liked_recommendations': [],
                'disliked_recommendations': []
            }
        
        self.user_data[user_id]['preferences'] = {
            'media_type': media_type,
            'genre': genre,
            'mood': mood,
            'timeframe': timeframe,
            'last_updated': datetime.now().isoformat()
        }
        
        self._save_user_data()
    
    def update_user_history(self, user_id: str, user_request: str, recommendations: List[Dict]):
        """Update user interaction history"""
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                'preferences': {},
                'history': [],
                'liked_recommendations': [],
                'disliked_recommendations': []
            }
        
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'request': user_request,
            'recommendations': [
                {
                    'title': rec.get('title'),
                    'type': rec.get('type'),
                    'genre': rec.get('genre')
                } for rec in recommendations
            ]
        }
        
        self.user_data[user_id]['history'].append(history_entry)
        
        # Keep only last 50 history entries
        if len(self.user_data[user_id]['history']) > 50:
            self.user_data[user_id]['history'] = self.user_data[user_id]['history'][-50:]
        
        self._save_user_data()
    
    def get_user_context(self, user_id: str) -> str:
        """Get personalized context for recommendation generation"""
        if user_id not in self.user_data:
            return "New user - no previous preferences available."
        
        user_info = self.user_data[user_id]
        context_parts = []
        
        # Add preferences
        prefs = user_info.get('preferences', {})
        if prefs:
            context_parts.append("User preferences:")
            context_parts.append(f"- Preferred media type: {prefs.get('media_type', 'Not specified')}")
            context_parts.append(f"- Preferred genre: {prefs.get('genre', 'Not specified')}")
            context_parts.append(f"- Typical mood: {prefs.get('mood', 'Not specified')}")
            context_parts.append(f"- Timeframe preference: {prefs.get('timeframe', 'Not specified')}")
        
        # Add history insights
        history = user_info.get('history', [])
        if history:
            context_parts.append("\nRecent interaction history:")
            recent_requests = [entry['request'] for entry in history[-5:]]  # Last 5 requests
            for i, req in enumerate(recent_requests[-3:], 1):  # Show last 3
                context_parts.append(f"{i}. {req}")
        
        # Add liked/disliked items
        liked = user_info.get('liked_recommendations', [])
        disliked = user_info.get('disliked_recommendations', [])
        
        if liked:
            context_parts.append("\nPreviously liked items:")
            for item in liked[-5:]:
                context_parts.append(f"- {item.get('title')} ({item.get('type')})")
        
        if disliked:
            context_parts.append("\nPreviously disliked items:")
            for item in disliked[-3:]:
                context_parts.append(f"- {item.get('title')} ({item.get('type')})")
        
        return "\n".join(context_parts)
    
    def record_feedback(self, user_id: str, recommendation: Dict, liked: bool):
        """Record user feedback on recommendations"""
        if user_id not in self.user_data:
            return
        
        key = 'liked_recommendations' if liked else 'disliked_recommendations'
        
        feedback_entry = {
            'title': recommendation.get('title'),
            'type': recommendation.get('type'),
            'genre': recommendation.get('genre'),
            'timestamp': datetime.now().isoformat()
        }
        
        self.user_data[user_id][key].append(feedback_entry)
        
        # Keep reasonable limits
        if len(self.user_data[user_id][key]) > 100:
            self.user_data[user_id][key] = self.user_data[user_id][key][-100:]
        
        self._save_user_data()
    
    def clear_user_history(self, user_id: str):
        """Clear user history and preferences"""
        if user_id in self.user_data:
            self.user_data[user_id] = {
                'preferences': {},
                'history': [],
                'liked_recommendations': [],
                'disliked_recommendations': []
            }
            self._save_user_data()
    
    def get_user_insights(self, user_id: str) -> Dict:
        """Get insights about user preferences based on history"""
        if user_id not in self.user_data:
            return {}
        
        user_info = self.user_data[user_id]
        insights = {
            'favorite_genres': defaultdict(int),
            'preferred_media_types': defaultdict(int),
            'common_themes': [],
            'recommendation_success_rate': 0
        }
        
        # Analyze history for patterns
        for entry in user_info.get('history', []):
            for rec in entry.get('recommendations', []):
                insights['favorite_genres'][rec.get('genre')] += 1
                insights['preferred_media_types'][rec.get('type')] += 1
        
        # Calculate success rate based on likes vs dislikes
        total_feedback = len(user_info.get('liked_recommendations', [])) + len(user_info.get('disliked_recommendations', []))
        if total_feedback > 0:
            likes = len(user_info.get('liked_recommendations', []))
            insights['recommendation_success_rate'] = (likes / total_feedback) * 100
        
        return insights