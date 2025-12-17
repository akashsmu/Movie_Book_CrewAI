"""API modules for the Movie/Book/TV Recommender application."""

from api.movie_tools import (
    MovieSearchTool,
    MovieDetailsTool,
    PopularMoviesTool,
    DiscoverMoviesTool,
    MovieSearchInput,
    MovieDetailsInput,
    DiscoverMoviesInput
)

from api.book_tools import (
    BookSearchTool,
    BookDetailsTool,
    BookSearchInput,
    BookDetailsInput
)

from api.tv_tools import (
    TVSearchTool,
    TVDetailsTool,
    PopularTVTool,
    DiscoverTVTool,
    TVSearchInput,
    TVDetailsInput,
    DiscoverTVInput
)

from api.shared_tools import (
    SimilarTitlesTool,
    NewsSearchTool,
    TrendingMediaTool,
    SimilarTitlesInput,
    NewsSearchInput,
    TrendingMediaInput
)

# Tool instances
movie_search_tool = MovieSearchTool()
movie_details_tool = MovieDetailsTool()
popular_movies_tool = PopularMoviesTool()
discover_movies_tool = DiscoverMoviesTool()

book_search_tool = BookSearchTool()
book_details_tool = BookDetailsTool()

tv_search_tool = TVSearchTool()
tv_details_tool = TVDetailsTool()
popular_tv_tool = PopularTVTool()
discover_tv_tool = DiscoverTVTool()

similar_titles_tool = SimilarTitlesTool()
news_search_tool = NewsSearchTool()
trending_media_tool = TrendingMediaTool()

# Tool collections
movie_tools = [movie_search_tool, movie_details_tool, popular_movies_tool, discover_movies_tool]
book_tools = [book_search_tool, book_details_tool]
tv_tools = [tv_search_tool, tv_details_tool, popular_tv_tool, discover_tv_tool]
search_tools = [similar_titles_tool, news_search_tool, trending_media_tool]

all_tools = movie_tools + book_tools + tv_tools + search_tools

__all__ = [
    # Movie tools
    'MovieSearchTool', 'MovieDetailsTool', 'PopularMoviesTool', 'DiscoverMoviesTool',
    'MovieSearchInput', 'MovieDetailsInput', 'DiscoverMoviesInput',
    # Book tools
    'BookSearchTool', 'BookDetailsTool',
    'BookSearchInput', 'BookDetailsInput',
    # TV tools
    'TVSearchTool', 'TVDetailsTool', 'PopularTVTool', 'DiscoverTVTool',
    'TVSearchInput', 'TVDetailsInput', 'DiscoverTVInput',
    # Shared tools
    'SimilarTitlesTool', 'NewsSearchTool', 'TrendingMediaTool',
    'SimilarTitlesInput', 'NewsSearchInput', 'TrendingMediaInput',
    # Tool instances
    'movie_search_tool', 'movie_details_tool', 'popular_movies_tool', 'discover_movies_tool',
    'book_search_tool', 'book_details_tool',
    'tv_search_tool', 'tv_details_tool', 'popular_tv_tool', 'discover_tv_tool',
    'similar_titles_tool', 'news_search_tool', 'trending_media_tool',
    # Collections
    'movie_tools', 'book_tools', 'tv_tools', 'search_tools', 'all_tools'
]
