"""Centralized environment and channel settings."""
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_DIR = os.path.join(DATA_DIR, "db")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
_SESSION_RAW = (os.getenv("SESSION_NAME") or "forward_bot_session_local").strip()
if os.path.isabs(_SESSION_RAW) or ("/" in _SESSION_RAW) or ("\\" in _SESSION_RAW):
    SESSION_NAME = _SESSION_RAW
else:
    SESSION_NAME = os.path.join(SESSIONS_DIR, _SESSION_RAW)

# Optional: paste a Telethon StringSession (generate on your PC where SMS works).
# On cloud VPSs Telegram often does not deliver login SMS; use this instead of interactive login.
TELEGRAM_STRING_SESSION = (os.getenv("TELEGRAM_STRING_SESSION") or "").strip() or None

NEWS_DB_PATH = os.getenv("NEWS_DB_PATH", os.path.join(DB_DIR, "news.db"))

# IANA timezone for interpreting /ask phrases like "yesterday" and "between 2 and 4".
ASK_TIMEZONE = os.getenv("ASK_TIMEZONE", "Asia/Jerusalem")

TARGET_CHANNEL_MAIN = -1002584913687
TARGET_CHANNEL_STREETS = -1002692513965

# Every chat id here is subscribed via Telethon `NewMessage(chats=...)`: any new post
# from these channels/groups triggers forward + duplicate + archive (not other dialogs).
SOURCE_CHANNELS = [
    -1001307326930,
    -1001253130437,
    -1001807128752,
    -1001200257707,
    -1001672018523,
    -1001398906121,
    -1001125629973,
    -1001966059354,
    -1001634384757,
    -1001700954166,
    -1001291766291,
    -1001619836256,
    -1001014183242,
    -1001750166587,
    -1001721523102,
    -1002606693516,
    -1001989491822,
    -1001429269676,
    -1001267214144,
    -1001325889089,
    -591526182,
    -1001756020315,
]
