
"""
Test dataset for Ragas evaluation.
Contains a list of test cases with questions, expected tool usage, and ground truths.
"""

TEST_CASES = [
    {
        "question": "Find me a movie like Inception",
        "media_type": "movie",
        "ground_truths": ["Inception is a sci-fi thriller directed by Christopher Nolan. Similar movies include The Matrix, Interstellar, and Shutter Island."],
        "expected_tools": ["search_movie", "discover_movies"] # Either is fine
    },
    {
        "question": "I want to watch Breaking Bad",
        "media_type": "tv",
        "ground_truths": ["Breaking Bad is a crime drama about Walter White. It has 5 seasons."],
        "expected_tools": ["search_tv_shows"] # Must use search
    },
    {
        "question": "Recommend some funny sci-fi books",
        "media_type": "book",
        "ground_truths": ["The Hitchhiker's Guide to the Galaxy by Douglas Adams is a classic funny sci-fi book."],
        "expected_tools": ["find_books"]
    },
    {
        "question": "What are the most popular TV shows right now?",
        "media_type": "tv",
        "ground_truths": ["Popular TV shows currently include recent hits on streaming platforms."],
        "expected_tools": ["get_popular_tv_shows"]
    }
]
