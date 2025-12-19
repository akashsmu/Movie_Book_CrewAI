
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
    },
    {
        "question": "Scariest horror movies from the 80s",
        "media_type": "movie",
        "ground_truths": ["The Shining, The Thing, and A Nightmare on Elm Street are classic 80s horror films."],
        "expected_tools": ["discover_movies"]
    },
    {
        "question": "Books by Agatha Christie",
        "media_type": "book",
        "ground_truths": ["Agatha Christie is known for mystery novels like 'And Then There Were None' and 'Murder on the Orient Express'."],
        "expected_tools": ["search_books", "find_books"]
    },
    {
        "question": "Best comedy series to binge watch",
        "media_type": "tv",
        "ground_truths": ["The Office, Friends, and Parks and Recreation are popular binge-worthy comedies."],
        "expected_tools": ["discover_tv_shows"]
    },
    {
        "question": "Action movies",
        "media_type": "movie",
        "ground_truths": ["Mad Max: Fury Road, John Wick, and Die Hard are top action movies."],
        "expected_tools": ["discover_movies"] # Should trigger fast path internally if optimized, but tool usage remains discover
    }
]
