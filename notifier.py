import requests
import logging
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Notifier")

def _send_telegram_photo_sync(token: str, chat_id: str, message: str, image_bytes: bytes):
    """Synchronous worker function to send Telegram photo and caption."""
    try:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        files = {"photo": ("alert.jpg", image_bytes, "image/jpeg")}
        data = {
            "chat_id": chat_id,
            "caption": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data, files=files, timeout=15)
        if response.status_code == 200:
            logger.info("Telegram photo notification sent successfully.")
        else:
            logger.error(f"Failed to send Telegram photo: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error sending Telegram notification: {e}")

def _send_telegram_message_sync(token: str, chat_id: str, message: str):
    """Synchronous worker function to send standard text message."""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            logger.info("Telegram message notification sent successfully.")
        else:
            logger.error(f"Failed to send Telegram message: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")

def send_notification(token: str, chat_id: str, message: str, image_bytes: bytes = None):
    """
    Sends a Telegram push notification asynchronously to avoid blocking the caller's main thread.
    Can send just a text message, or a photo with a caption.
    """
    if not token or not chat_id:
        logger.warning("Telegram notification skipped: Bot token or chat ID is not configured.")
        return

    if image_bytes is not None:
        thread = threading.Thread(
            target=_send_telegram_photo_sync,
            args=(token, chat_id, message, image_bytes),
            daemon=True
        )
    else:
        thread = threading.Thread(
            target=_send_telegram_message_sync,
            args=(token, chat_id, message),
            daemon=True
        )
    thread.start()
