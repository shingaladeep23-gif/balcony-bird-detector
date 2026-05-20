import sys
import json
import os

# Add parent directory to path just in case
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from detector import BirdDetector
    print("[OK] Successfully imported BirdDetector class.")
except Exception as e:
    print(f"[ERROR] Failed to import BirdDetector: {e}")
    sys.exit(1)

def test_connection():
    config_path = "config.json"
    if not os.path.exists(config_path):
        print(f"[ERROR] Configuration file '{config_path}' not found in the current directory.")
        return

    print("Loading config...")
    detector = BirdDetector(config_path=config_path)
    
    token = detector.config.get("telegram_bot_token", "")
    chat_id = detector.config.get("telegram_chat_id", "")
    
    print(f"Telegram Bot Token: {token[:6]}...{token[-6:] if len(token) > 12 else ''}")
    print(f"Telegram Chat ID: {chat_id}")
    
    if not token or not chat_id:
        print("[ERROR] Bot Token or Chat ID is not defined in config.json.")
        print("Please edit config.json or configure it via the dashboard web interface.")
        return
        
    print("Dispatching test alert notification...")
    success, message = detector.send_test_telegram()
    if success:
        print(f"[OK] SUCCESS: {message}")
        print("Please check your phone's Telegram client now!")
    else:
        print(f"[ERROR] Failed: {message}")

if __name__ == "__main__":
    test_connection()

