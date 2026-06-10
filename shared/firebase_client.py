"""
SecureNet SOC — Firebase Cloud Messaging Client

Sends push notifications to mobile devices.
Implements a mock fallback if credentials are not provided.
"""

import os
import logging
import asyncio

try:
    from firebase_admin import credentials, messaging, initialize_app
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False

logger = logging.getLogger(__name__)

FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")

_initialized = False

def init_firebase():
    global _initialized
    if not HAS_FIREBASE:
        logger.info("firebase-admin not installed. Running in MOCK fallback mode.")
        return
    if not FIREBASE_CREDENTIALS_PATH or not os.path.exists(FIREBASE_CREDENTIALS_PATH):
        logger.warning(f"Firebase credentials not found at '{FIREBASE_CREDENTIALS_PATH}'. Running in MOCK fallback mode.")
        return
        
    try:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        initialize_app(cred)
        _initialized = True
        logger.info("Firebase Cloud Messaging initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")

# Initialize at module import
init_firebase()

async def send_push_notification(title: str, body: str, data: dict = None, topic: str = "soc_alerts") -> bool:
    """
    Sends an async push notification via FCM.
    If not initialized, acts as a mock and succeeds.
    """
    if not _initialized:
        logger.debug(f"[MOCK FCM] Sending to topic '{topic}': {title} - {body} | Data: {data}")
        return True
        
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            topic=topic,
        )
        
        # messaging.send is synchronous, so we run it in an executor
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, messaging.send, message)
        logger.info(f"Successfully sent FCM message: {response}")
        return True
    except Exception as e:
        logger.error(f"Error sending FCM message: {e}", exc_info=True)
        return False
