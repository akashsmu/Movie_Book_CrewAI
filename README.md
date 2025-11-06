# 🎬📚 AI Media Recommender System

A sophisticated multi-agent AI system that provides personalized movie and book recommendations using CrewAI, real-time APIs, and intelligent personalization.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![CrewAI](https://img.shields.io/badge/CrewAI-000000?style=for-the-badge&logo=ai&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

## 🌟 Features

### 🤖 Multi-Agent Architecture
- **Analysis Agent**: Understands user intent and extracts preferences
- **Movie Specialist**: Expert in film recommendations using TMDB API
- **Book Specialist**: Literary expert using Google Books API
- **Research Agent**: Gathers additional context and trending information
- **Editor Agent**: Refines and personalizes final recommendations

### 🔌 Real-Time API Integration
- **TMDB API**: Current movie data, ratings, and details
- **Google Books API**: Comprehensive book information and reviews
- **SerpAPI**: Web search for similar titles and trending content
- **Real-time Data**: Always up-to-date recommendations

### 🎯 Smart Personalization
- **User Profiles**: Save preferences and interaction history
- **Adaptive Learning**: Improves recommendations based on feedback
- **Context Awareness**: Considers mood, genre, and timeframe preferences
- **History Tracking**: Learns from your likes and dislikes

### 💻 User-Friendly Interface
- **Streamlit Web App**: Beautiful, responsive interface
- **Interactive Controls**: Easy preference customization
- **Real-time Results**: Instant recommendation generation
- **Feedback System**: Like/dislike to improve future suggestions

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Conda (recommended) or pip
- API keys for services below

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd Movie_Book_CrewAI
```

2. **Create and activate Conda environment**
```bash
conda env create -f environment.yml
conda activate media-recommender
```

3. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. **Run the setup script**
```bash
python setup.py
```

5. **Launch the application**
```bash
python run.py
# or directly with:
streamlit run app.py
```

The application will open at `http://localhost:8501`

## 🔑 API Keys Required

### Required APIs
- **OpenAI API**: For AI agent reasoning and natural language processing
- **TMDB API**: For movie data and recommendations
- **Google Books API**: For book information and search
- **SerpAPI**: For web searches and trending content

### How to Get API Keys

#### 1. OpenAI API Key
1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create account or sign in
3. Generate new API key
4. Add to `.env` as `OPENAI_API_KEY=your_key_here`

#### 2. TMDB API Key
1. Go to [TMDB Settings](https://www.themoviedb.org/settings/api)
2. Create free account
3. Apply for API key
4. Add to `.env` as `TMDB_API_KEY=your_key_here`

#### 3. Google Books API Key
1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project
3. Enable Books API
4. Create credentials (API key)
5. Add to `.env` as `GOOGLE_BOOKS_API_KEY=your_key_here`

#### 4. SerpAPI Key
1. Sign up at [SerpAPI](https://serpapi.com/users/sign_up)
2. Get API key from dashboard
3. Add to `.env` as `SERPAPI_KEY=your_key_here`

## 🏗️ Project Architecture

### File Structure
```
Movie_Book_CrewAI/
├── app.py                 # Main Streamlit web application
├── media_crew.py          # CrewAI agent orchestration
├── media_apis.py          # API integrations and tools
├── personalization_manager.py # User profile management
├── environment.yml        # Conda environment configuration
├── requirements.txt       # Python dependencies
├── setup.py              # Environment setup script
├── run.py                # Application launcher
└── .env.example          # Environment variables template
```

### System Workflow

1. **User Input** → Streamlit interface captures request and preferences
2. **Analysis** → Analysis agent determines intent and extracts preferences
3. **Data Gathering** → Specialist agents fetch data from respective APIs
4. **Research** → Research agent gathers additional context
5. **Editing** → Editor agent refines and personalizes recommendations
6. **Output** → Final recommendations displayed to user
7. **Learning** → User feedback updates personalization profile

### Agent Responsibilities

| Agent | Role | Tools Used |
|-------|------|------------|
| **Analysis Agent** | Understands user intent | OpenAI LLM |
| **Movie Specialist** | Finds movie recommendations | TMDB API, Search |
| **Book Specialist** | Finds book recommendations | Google Books API, Search |
| **Research Agent** | Gathers additional context | SerpAPI, News Search |
| **Editor Agent** | Refines final output | OpenAI LLM |

## 🎮 How to Use

### Basic Usage

1. **Select Media Type**: Choose Movies, Books, or Both
2. **Set Preferences**: 
   - Preferred genre
   - Current mood
   - Time period preference
3. **Describe Your Request**: 
   - "I want an exciting sci-fi movie with great visuals"
   - "Recommend me a thought-provoking book about AI"
4. **Get Recommendations**: Click "Get Recommendations" button
5. **Provide Feedback**: Use Like/Dislike buttons to improve future suggestions

### Advanced Features

#### Personalization
- Enable "Use my personalization profile" to save preferences
- System learns from your interaction history
- Recommendations improve over time based on feedback

#### Quick Examples
- "Mind-bending thriller like Inception"
- "Feel-good romance book for weekend"
- "Historical fiction about ancient Rome"
- "Award-winning movies from 2020s"

#### Advanced Options
- Number of recommendations (1-10)
- Diversity level of suggestions
- Include reviews and similar titles

## 🔧 Configuration

### Environment Variables

Create a `.env` file with:

```env
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Movie Recommendations
TMDB_API_KEY=your_tmdb_api_key_here

# Book Recommendations  
GOOGLE_BOOKS_API_KEY=your_google_books_api_key_here

# Search and Trends
SERPAPI_KEY=your_serpapi_key_here

# Optional - Additional APIs
OMDB_API_KEY=your_omdb_api_key_here
```

### Model Configuration

In `media_crew.py`, you can modify:

```python
self.llm = ChatOpenAI(
    model="gpt-3.5-turbo",  # or "gpt-4" for better results
    temperature=0.7,        # creativity vs consistency
    api_key=os.getenv("OPENAI_API_KEY")
)
```

## 🛠️ Development

### Adding New APIs

1. **Create new tool in `media_apis.py`**:
```python
class NewAPITool(BaseTool):
    name: str = "new_tool"
    description: str = "Description of what the tool does"
    
    def _run(self, parameter: str) -> str:
        # Implementation here
        return "Formatted results"
```

2. **Add tool to appropriate agent in `media_crew.py`**:
```python
self.movie_agent = Agent(
    # ... other parameters
    tools=[*existing_tools, new_tool_instance]
)
```

### Customizing Agents

Modify agent parameters in `media_crew.py`:

```python
self.movie_agent = Agent(
    role="Custom Movie Specialist",
    goal="Your custom goal",
    backstory="Custom backstory",
    tools=[],
    llm=self.llm
)
```

### Extending Personalization

Add new preference types in `personalization_manager.py`:

```python
def save_user_preferences(self, user_id: str, new_preference: str):
    # Implementation for new preference type
```

## 📊 API Usage and Costs

### Cost Estimation

| Service | Free Tier | Cost Estimate |
|---------|-----------|---------------|
| **OpenAI** | $0.00 initial credit | ~$0.01-0.10 per request |
| **TMDB** | Free unlimited | $0.00 |
| **Google Books** | Free with quotas | $0.00 for moderate use |
| **SerpAPI** | 100 searches/month free | $0.02 per search after |

### Monitoring Usage

- Check OpenAI usage: [OpenAI Usage Dashboard](https://platform.openai.com/usage)
- Monitor SerpAPI: [SerpAPI Dashboard](https://serpapi.com/dashboard)
- Google Books quotas: [Google Cloud Console](https://console.cloud.google.com/)

## 🐛 Troubleshooting

### Common Issues

1. **"API key not configured"**
   - Check `.env` file exists and has correct keys
   - Verify environment variables are loaded
   - Restart application after adding keys

2. **"Error searching movies/books"**
   - Verify API keys are valid
   - Check internet connection
   - Confirm API service is operational

3. **"No recommendations found"**
   - Try broader search terms
   - Check if APIs are returning data
   - Verify API rate limits aren't exceeded

4. **Streamlit connection issues**
   - Ensure port 8501 is available
   - Check firewall settings
   - Try `streamlit run app.py --server.port 8502`

### Debug Mode

Enable verbose logging by setting in `media_crew.py`:
```python
verbose=True  # In Agent and Crew initialization
```

## 🚀 Deployment

### Local Deployment
```bash
python run.py
```

### Production Deployment

#### Using Streamlit Sharing
1. Push code to GitHub
2. Connect at [Streamlit Sharing](https://share.streamlit.io/)
3. Set environment variables in dashboard
4. Deploy automatically

#### Using Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

EXPOSE 8501
CMD ["streamlit", "run", "app.py"]
```

#### Using Traditional Hosting
1. Install dependencies
2. Set environment variables
3. Run with: `streamlit run app.py --server.port=80`

## 📈 Performance Optimization

### Caching Strategies
- Enable Streamlit caching for expensive operations
- Implement result caching for similar queries
- Use session state to avoid recomputation

### Rate Limiting
- Implement request throttling for APIs
- Use exponential backoff for failed requests
- Cache API responses when appropriate

### Memory Management
- Clear session state periodically
- Implement pagination for large result sets
- Use generators for large data processing

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Setup
```bash
git clone <your-fork-url>
cd Movie_Book_CrewAI
conda env create -f environment.yml
conda activate media-recommender
pip install -r requirements.txt
```

### Testing
```bash
# Add tests to test_media_apis.py, test_media_crew.py, etc.
python -m pytest tests/
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **CrewAI**: For the amazing multi-agent framework
- **OpenAI**: For powerful language models
- **TMDB**: For comprehensive movie database
- **Google Books**: For extensive book information
- **Streamlit**: For simple web app framework
- **SerpAPI**: For reliable search results

## 📞 Support

- **Documentation**: Check this README and code comments
- **Issues**: Open a GitHub issue for bugs or feature requests
- **Discussions**: Use GitHub discussions for questions
- **Email**: Contact maintainers for direct support

## 🔄 Version History

- **v1.0.0** (Current): Initial release with multi-agent recommendation system
- **v0.1.0**: Beta release with basic functionality

---

**Happy Exploring!** 🎬📚

Discover your next favorite movie or book with AI-powered recommendations tailored just for you.