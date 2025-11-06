#!/usr/bin/env python3
"""
Run script for Media Recommender System
"""

import os
import subprocess
import sys
from dotenv import load_dotenv

def load_environment():
    """Load environment variables"""
    if not os.path.exists('.env'):
        print("❌ No .env file found. Please run setup.py first.")
        sys.exit(1)
    
    load_dotenv()
    
    # Check for required API keys
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY not found in .env file.")
        sys.exit(1)

def main():
    """Main run function"""
    print("🎬📚 Starting Media Recommender System...")
    
    # Load environment
    load_environment()
    
    # Check if streamlit is available
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "version"], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("❌ Streamlit not found. Please install dependencies first.")
        sys.exit(1)
    
    # Run the application
    print("🚀 Starting Streamlit application...")
    print("📱 Open your browser to http://localhost:8501")
    print("⏹️  Press Ctrl+C to stop the application")
    
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])
    except KeyboardInterrupt:
        print("\n👋 Application stopped.")
    except Exception as e:
        print(f"❌ Error running application: {e}")

if __name__ == "__main__":
    main()