import subprocess
import sys
import os
import threading
import time
import signal

def run_backend():
    """Run the FastAPI backend"""
    os.chdir('backend')
    print("Starting FastAPI backend...")
    subprocess.run([sys.executable, '-m', 'uvicorn', 'api:app', '--host', '0.0.0.0', '--port', '8000', '--reload'])

def run_user_bot():
    """Run the user bot"""
    os.chdir('../bots')
    print("Starting User Bot...")
    subprocess.run([sys.executable, 'user_bot.py'])

def run_admin_bot():
    """Run the admin bot"""
    os.chdir('../bots')
    print("Starting Admin Bot...")
    subprocess.run([sys.executable, 'admin_bot.py'])

def run_ml_trainer():
    """Run ML model trainer"""
    os.chdir('../ml')
    print("Starting ML Trainer...")
    subprocess.run([sys.executable, 'trainer.py'])

def signal_handler(signum, frame):
    print("\nShutting down all services...")
    sys.exit(0)

def main():
    print("Starting WinGo AI Prediction System...")
    
    # Create required directories
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('ml/models', exist_ok=True)
    
    # Create .gitkeep files in empty directories
    open('ml/models/.gitkeep', 'a').close()
    
    # Start backend first
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    
    time.sleep(3)  # Wait for backend to start
    
    # Start bots in separate threads
    user_bot_thread = threading.Thread(target=run_user_bot, daemon=True)
    admin_bot_thread = threading.Thread(target=run_admin_bot, daemon=True)
    
    user_bot_thread.start()
    admin_bot_thread.start()
    
    # Start ML trainer (will run once initially)
    ml_thread = threading.Thread(target=run_ml_trainer, daemon=True)
    ml_thread.start()
    
    print("\n" + "="*60)
    print("ALL SERVICES STARTED!")
    print("="*60)
    print("Backend running on: http://localhost:8000")
    print("Swagger UI: http://localhost:8000/docs")
    print("WebApp: http://localhost:8000/webapp/index.html")
    print("User Bot: Running (Telegram)")
    print("Admin Bot: Running (Telegram)")
    print("ML Models: Training on startup and daily")
    print("="*60)
    print("Press Ctrl+C to stop all services")
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()