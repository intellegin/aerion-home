import os
from dotenv import load_dotenv

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")

# --- Database Settings ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# --- Audio Settings ---
VAD_RMS_THRESHOLD = float(os.getenv("VAD_RMS_THRESHOLD", 0.02)) # Threshold for voice activity detection 