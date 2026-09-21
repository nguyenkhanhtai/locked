import uvicorn
import os
import sys

# Ensure backend directory is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

def main():
    port = int(os.environ.get("LOCKED_PORT", 8765))
    host = os.environ.get("LOCKED_HOST", "127.0.0.1")
    print("==================================================")
    print("🚀 Starting Locked - Study Toolkit Server")
    print(f"🌐 Open http://{host}:{port} in your browser")
    print("🛑 Press Ctrl+C to stop the server")
    print("==================================================")
    uvicorn.run("app:app", host=host, port=port, reload=True, app_dir=backend_dir)

if __name__ == '__main__':
    main()
