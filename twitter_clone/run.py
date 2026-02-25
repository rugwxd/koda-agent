#!/usr/bin/env python3
"""
Simple script to run the Twitter Clone application.
"""

import os
import sys
from app import app, init_db

def main():
    """Main function to run the application."""
    print("🐦 Starting Twitter Clone...")
    print("=" * 50)
    
    # Initialize database
    print("📊 Initializing database...")
    init_db()
    print("✅ Database initialized successfully!")
    
    # Check if running in development mode
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"🚀 Starting Flask server (debug={'ON' if debug_mode else 'OFF'})...")
    print("🌐 Open your browser and go to: http://localhost:5000")
    print("=" * 50)
    print("Press Ctrl+C to stop the server")
    print()
    
    try:
        app.run(debug=debug_mode, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 Shutting down Twitter Clone. Goodbye!")
        sys.exit(0)

if __name__ == '__main__':
    main()