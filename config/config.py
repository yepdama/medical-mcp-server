import os
from dotenv import load_dotenv

# Load .env once during config import
load_dotenv()

# Core configuration variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MCP_SERVER_TOKEN = os.getenv("MCP_SERVER_TOKEN", "super-secret-token")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "logs/server.log")


