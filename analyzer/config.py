# config.py
from dotenv import load_dotenv
import os

# Load .env from the project root (one level up from analyzer/)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, '.env'))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL_NAME = "claude-sonnet-5"

# Form analysis: image/PDF -> full JSON structure
ANALYSIS_MAX_TOKENS = 64000
ANALYSIS_THINKING = False

# Form name/category detection
DETECTION_MAX_TOKENS = 512
DETECTION_THINKING = False
