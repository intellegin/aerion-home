import subprocess
import sys
import os
import time

def main():
    """
    Launches the web UI, which in turn controls the main assistant process.
    This script provides a single command to start the entire system and ensures
    a clean shutdown.
    """
    python_executable = sys.executable
    web_ui_script_path = os.path.join(os.path.dirname(__file__), 'web_ui.py')
    
    web_ui_process = None
    try:
        print(f"🚀 Launching the Aerion Home control UI...")
        print(f"   - Script: {web_ui_script_path}")
        print(f"   - Press Ctrl+C in this terminal to shut down the entire system.")
        
        web_ui_process = subprocess.Popen([python_executable, web_ui_script_path])
        
        # Wait for the process to complete. 
        web_ui_process.wait()

    except KeyboardInterrupt:
        print("\n🛑 Ctrl+C detected. Shutting down the launcher and all services.")
    except Exception as e:
        print(f"An error occurred while launching the UI: {e}")
    finally:
        if web_ui_process and web_ui_process.poll() is None:
            print("Terminating web UI process...")
            web_ui_process.terminate()
            try:
                # Give it a moment to shut down gracefully
                web_ui_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't respond
                web_ui_process.kill()
        print("System has shut down.")


if __name__ == "__main__":
    main() 