#!/usr/bin/env python3
"""
Main entry point for running the RefMatch application
"""

from app.main import create_app
import os

if __name__ == '__main__':
    # Set environment
    os.environ.setdefault('FLASK_ENV', 'development')
    
    # Create and run app
    app = create_app()
    
    print("Starting RefMatch MVP...")
    print("Access the application at: http://localhost:5001")
    print("API documentation at: http://localhost:5001/api")
    print("\nPress CTRL+C to stop the server")
    
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True
    )