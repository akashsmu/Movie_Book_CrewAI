import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict
import logging



try:
    from mem0 import MemoryClient
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    print("Warning: mem0ai not found. Personalization will be limited.")

logger = logging.getLogger(__name__)

class PersonalizationManager:
    def __init__(self, storage_file: str = "user_preferences.json"):
        self.storage_file = storage_file
        self.user_data = self._load_user_data()
        
        # Initialize Mem0
        if MEM0_AVAILABLE:
            self.memory = MemoryClient(api_key=os.getenv("MEM0_API_KEY"))
        else:
            self.memory = None
    
    def _load_user_data(self) -> Dict:
        """Load user data from storage file (Legacy/Watchlist)"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading user data: {e}")
        return {}
    
    def _save_user_data(self):
        """Save user data to storage file"""
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(self.user_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving user data: {e}")

    # --- Mem0 Integration Methods ---

    def add_memory(self, user_id: str, text: str, metadata: Optional[Dict] = None):
        """Add a raw memory/fact about the user (e.g. from query)"""
        if self.memory:
            try:
                # Mem0 Platform Client expects 'messages' as a list of dicts
                messages = [{"role": "user", "content": text}]
                self.memory.add(messages=messages, user_id=user_id, metadata=metadata)
                logger.info(f"Added memory for {user_id}: {text}")
            except Exception as e:
                logger.error(f"Failed to add memory to Mem0: {e}")

    def get_relevant_memories(self, user_id: str, query: str, limit: int = 5) -> str:
        """Retrieve relevant context strings for a given query"""
        if not self.memory:
            return self.get_user_context(user_id) # Fallback to legacy
            
        try:
            results = self.memory.search(query, user_id=user_id, limit=limit)
            # Results are typically a list of dicts with 'text', 'score'.
            
            if not results:
                return "No specific past memories found."
                
            memory_texts = [f"- {res['memory']}" for res in results if 'memory' in res]
            
            context = "User Personalization Context (from Memory):\n" + "\n".join(memory_texts)
            return context
            
        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return self.get_user_context(user_id) # Fallback

    def record_feedback(self, user_id: str, recommendation: Dict, liked: bool):
        """Record explicit feedback (Like/Dislike) into Mem0"""
        timestamp = datetime.now().isoformat()
        
        # 1. Update Legacy History (for UI/Watchlist tracking if needed)
        self._record_feedback_legacy(user_id, recommendation, liked)
        
        # 2. Add to Mem0
        if self.memory:
            action = "liked" if liked else "disliked"
            title = recommendation.get('title', 'Unknown')
            rec_type = recommendation.get('type', 'Unknown')
            genre = recommendation.get('genre', 'Unknown')
            description = recommendation.get('description', '')
            
            # Construct a rich memory text
            memory_text = (
                f"User {action} the {rec_type} '{title}' (Genre: {genre}). "
                f"Item description: {description}"
            )
            
            # Metadata helps filters if we use them later
            metadata = {
                "type": "feedback",
                "action": action,
                "media_type": rec_type,
                "genre": genre,
                "timestamp": timestamp
            }
            
            self.add_memory(user_id, memory_text, metadata=metadata)

    # --- Legacy / Watchlist Methods ---
    
    def save_user_preferences(self, user_id: str, media_type: str, genre: str, 
                            mood: str, timeframe: str):
        """Save explicit sidebar preferences (Legacy + Mem0)"""
        
        # 1. Legacy Save
        if user_id not in self.user_data:
            self._init_user(user_id)
        
        self.user_data[user_id]['preferences'] = {
            'media_type': media_type,
            'genre': genre,
            'mood': mood,
            'timeframe': timeframe,
            'last_updated': datetime.now().isoformat()
        }
        self._save_user_data()
        
        # 2. Mem0 Save (Explicit preference statement)
        if self.memory:
            pref_text = (
                f"User explicitly set preferences: "
                f"Media Type: {media_type}, Genre: {genre}, "
                f"Mood: {mood}, Timeframe: {timeframe}"
            )
            self.add_memory(user_id, pref_text, metadata={"type": "explicit_preference"})

    def update_user_history(self, user_id: str, user_request: str, recommendations: List[Dict]):
        """Update history - Stores the QUERY into Mem0"""
        
        # 1. Legacy History
        if user_id not in self.user_data:
            self._init_user(user_id)
            
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'request': user_request,
            'recommendations': [
                {
                    'title': rec.get('title'),
                    'type': rec.get('type')
                } for rec in recommendations
            ]
        }
        self.user_data[user_id]['history'].append(history_entry)
        if len(self.user_data[user_id]['history']) > 50:
            self.user_data[user_id]['history'] = self.user_data[user_id]['history'][-50:]
        self._save_user_data()
        
        # 2. Mem0: Store the query as a memory
        if self.memory:
            self.add_memory(user_id, f"User searched for: {user_request}", metadata={"type": "search_query"})

    def get_watchlist(self, user_id: str) -> List[Dict]:
        if user_id not in self.user_data: return []
        return self.user_data[user_id].get('watchlist', [])

    def add_to_watchlist(self, user_id: str, item: Dict):
        if user_id not in self.user_data: self._init_user(user_id)
        watchlist = self.user_data[user_id].setdefault('watchlist', [])
        
        # Deduplicate
        if not any(w['title'] == item['title'] and w['type'] == item['type'] for w in watchlist):
            # Save clean item
            saved_item = {k: item.get(k) for k in ['title', 'type', 'genre', 'description', 'year', 'rating', 'image_url', 'trailer_url', 'preview_url']}
            saved_item['saved_at'] = datetime.now().isoformat()
            watchlist.append(saved_item)
            self._save_user_data()
            
            # Mem0 Signal
            if self.memory:
                action = "added to watchlist"
                title = item.get('title', 'Unknown')
                rec_type = item.get('type', 'Unknown')
                genre = item.get('genre', 'Unknown')
                
                # Metadata helps filters if we use them later
                metadata = {
                    "type": "watchlist",
                    "action": action,
                    "media_type": rec_type,
                    "genre": genre,
                    "timestamp": datetime.now().isoformat()
                }
                self.add_memory(user_id, text=f"User {action} the {rec_type} '{title}'. ", metadata=metadata)
                
            return True
        return False

    def remove_from_watchlist(self, user_id: str, item: Dict):
        """Remove item from watchlist"""
        if user_id not in self.user_data:
            return False
            
        watchlist = self.user_data[user_id].get('watchlist', [])
        initial_len = len(watchlist)
        
        # Filter out the item
        self.user_data[user_id]['watchlist'] = [
            w for w in watchlist 
            if not (w['title'] == item['title'] and w['type'] == item['type'])
        ]
        
        if len(self.user_data[user_id]['watchlist']) < initial_len:
            self._save_user_data()
            
            # Mem0: Delete the specific memory
            if self.memory:
                try:
                    # Search using title to find relevant memories
                    query = f"User added to watchlist {item.get('type')} '{item.get('title')}'."
                    results = self.memory.search(query, user_id=user_id, limit=5)
                    
                    for res in results:
                        # Check metadata or text content
                        meta = res.get('metadata', {})
                        if meta.get('type') == 'watchlist' and item.get('title') in res.get('memory', ''):
                            self.memory.delete(res['id'])
                            logger.info(f"Deleted watchlist memory for {item.get('title')}")
                            break
                            
                except Exception as e:
                    logger.error(f"Failed to delete watchlist memory: {e}")
            
            return True
        return False
        
    def _init_user(self, user_id):
        self.user_data[user_id] = {
            'preferences': {}, 'history': [], 'watchlist': [],
            'liked_recommendations': [], 'disliked_recommendations': []
        }

    def _record_feedback_legacy(self, user_id: str, recommendation: Dict, liked: bool):
        if user_id not in self.user_data: self._init_user(user_id)
        key = 'liked_recommendations' if liked else 'disliked_recommendations'
        self.user_data[user_id][key].append({
            'title': recommendation.get('title'),
            'type': recommendation.get('type'),
            'genre': recommendation.get('genre'),
            'timestamp': datetime.now().isoformat()
        })
        if len(self.user_data[user_id][key]) > 100:
            self.user_data[user_id][key] = self.user_data[user_id][key][-100:]
        self._save_user_data()

    def get_user_context(self, user_id: str) -> str:
        """Legacy context retriever (Fallback)"""
        if user_id not in self.user_data: return "New user."
        u = self.user_data[user_id]
        parts = ["Legacy Preferences:"]
        if u.get('preferences'): parts.append(str(u['preferences']))
        if u.get('liked_recommendations'): 
            parts.append("Liked: " + ", ".join([i['title'] for i in u['liked_recommendations'][-3:]]))
        return "\n".join(parts)
        
    def record_feedback(self, user_id: str, recommendation: Dict, liked: bool):
        """Record user feedback on recommendations"""
        # 1. Update Legacy History
        self._record_feedback_legacy(user_id, recommendation, liked)
        
        # 2. Add/Update Mem0
        if self.memory:
            try:
                action = "liked" if liked else "disliked"
                title = recommendation.get('title', 'Unknown')
                rec_type = recommendation.get('type', 'Unknown')
                genre = recommendation.get('genre', 'Unknown')
                description = recommendation.get('description', '')
                timestamp = datetime.now().isoformat()
                
                # Construct rich memory text
                memory_text = (
                    f"User {action} the {rec_type} '{title}' (Genre: {genre}). "
                    f"Item description: {description}"
                )
                
                # Metadata
                metadata = {
                    "type": "feedback",
                    "action": action,
                    "media_type": rec_type,
                    "genre": genre,
                    "timestamp": timestamp,
                    "title_id": title 
                }
                
                # Check for EXISTING feedback
                existing_memory_id = None
                search_query = f"feedback {title}"
                # Mem0 Platform search expects 'query'
                results = self.memory.search(query=search_query, user_id=user_id, limit=5)
                
                for res in results:
                    meta = res.get('metadata', {})
                    if meta.get('type') == 'feedback' and (meta.get('title_id') == title or title in res.get('memory', '')):
                        existing_memory_id = res['id']
                        break
                
                if existing_memory_id:
                    # UPDATE existing memory
                    self.memory.update(existing_memory_id, text=memory_text,metadata=metadata)
                    logger.info(f"Updated feedback memory for {title} to {action}")
                else:
                    # CREATE new memory
                    messages = [{"role": "user", "content": memory_text}]
                    self.memory.add(messages=messages, user_id=user_id, metadata=metadata)
                    logger.info(f"Added new feedback memory for {title}: {action}")
                    
            except Exception as e:
                logger.error(f"Failed to record feedback in Mem0: {e}")