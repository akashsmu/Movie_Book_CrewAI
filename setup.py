#!/usr/bin/env python3
"""
Setup script for Media Recommender System
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

def check_environment():
    """Check if required environment variables are set"""
    required_vars = ['OPENAI_API_KEY']
    optional_vars = ['TMDB_API_KEY', 'GOOGLE_BOOKS_API_KEY', 'SERPAPI_KEY']
    
    print("🔍 Checking environment variables...")
    
    missing_required = []
    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)
    
    if missing_required:
        print("❌ Missing required environment variables:")
        for var in missing_required:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file")
        return False
    
    print("✅ All required environment variables are set!")
    
    missing_optional = [var for var in optional_vars if not os.getenv(var)]
    if missing_optional:
        print("⚠️  Missing optional environment variables (some features may be limited):")
        for var in missing_optional:
            print(f"   - {var}")
    
    return True

def create_env_file():
    """Create .env file from template if it doesn't exist"""
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if not env_file.exists() and env_example.exists():
        print("📝 Creating .env file from template...")
        env_file.write_text(env_example.read_text())
        print("✅ Created .env file. Please edit it with your API keys.")
    elif not env_file.exists():
        print("❌ No .env file found and no template available.")
        return False
    
    return True

def install_dependencies():
    """Install required dependencies"""
    print("📦 Installing dependencies...")
    
    try:
        # Install using pip from requirements.txt
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def main():
    """Main setup function"""
    print("🎬📚 Media Recommender System Setup")
    print("=" * 40)
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Create .env file if needed
    if not create_env_file():
        return
    
    # Install dependencies
    if not install_dependencies():
        return
    
    # Check environment
    if not check_environment():
        print("\n⚠️  Please set the missing environment variables and run again.")
        return
    
    print("\n🎉 Setup completed successfully!")
    print("\nTo run the application:")
    print("  streamlit run app.py")
    print("\nMake sure you have set all your API keys in the .env file.")

if __name__ == "__main__":
    main()