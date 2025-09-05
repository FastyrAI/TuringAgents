#!/usr/bin/env python3
"""
Simple HTTP server to serve the evaluation dashboard.
Usage: python serve_dashboard.py [port]
"""

import os
import sys
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler


def main():
    # Get port from command line or default to 8080
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    
    # Change to .deepeval directory to serve files (VocalAi structure)
    deepeval_dir = Path(__file__).parent / ".deepeval"
    if not deepeval_dir.exists():
        print(f"❌ Directory not found: {deepeval_dir}")
        print("Run some evaluations first to create the .deepeval directory.")
        return 1
    
    os.chdir(deepeval_dir)
    
    # Check if results.html exists
    if not Path("results.html").exists():
        print("❌ results.html not found in history directory")
        print("Make sure the dashboard has been set up properly.")
        return 1
    
    # Check if history file exists
    if not Path(".deepeval-history.json").exists():
        print("⚠️  No evaluation history found (.deepeval-history.json)")
        print("Run some evaluations first to generate data.")
        # Create empty history file
        with open(".deepeval-history.json", "w") as f:
            f.write("[]")
    
    # Start server
    handler = SimpleHTTPRequestHandler
    httpd = HTTPServer(("localhost", port), handler)
    
    url = f"http://localhost:{port}/results.html"
    print(f"🚀 Starting TuringAgents evaluation dashboard...")
    print(f"📊 Dashboard URL: {url}")
    print(f"📁 Serving from: {deepeval_dir}")
    print("Press Ctrl+C to stop the server")
    
    # Try to open browser automatically
    try:
        webbrowser.open(url)
        print("🌐 Opened dashboard in your default browser")
    except Exception:
        print("💡 Open the URL above in your browser to view the dashboard")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        return 0


if __name__ == "__main__":
    sys.exit(main())
