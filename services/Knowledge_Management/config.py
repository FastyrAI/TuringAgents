# Load environment variables
import os

env_loaded = False
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ .env file loaded successfully")
    env_loaded = True
except ImportError:
    print("python-dotenv not found. Trying manual .env file loading...")
except Exception as e:
    print(f"⚠ Error loading .env file with python-dotenv: {e}. Trying manual loading...")

# Manual .env file loading as fallback
if not env_loaded:
    try:
        env_file_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            print("env file loaded manually")
        else:
            print("env file not found in project directory")
    except Exception as e:
        print(f"Error loading .env file manually: {e}")

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please check your .env file.")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
ENABLE_GEMINI_EXTRACTION = os.getenv("ENABLE_GEMINI_EXTRACTION", "true").lower() == "true"


# Database Configuration
FALKORDB_HOST = os.getenv("FALKORDB_HOST")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT"))
FALKORDB_USERNAME = os.getenv("FALKORDB_USERNAME")
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD")
FALKORDB_GRAPH_NAME = os.getenv("FALKORDB_GRAPH_NAME")

# API Configuration
API_HOST = "0.0.0.0"
API_PORT = 8000
API_TITLE = "Knowledge Management API"

# NLP Configuration
SPACY_MODEL = "en_core_web_sm"

# File Upload Configuration
UPLOAD_DIR = "uploads"

# Knowledge Extraction Configuration
# Only extract these entity types (empty list = extract all)
ALLOWED_ENTITY_TYPES = ["PERSON", "ORG", "GPE", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE"]

# Entity type priority (higher priority types override lower ones for same text)
ENTITY_TYPE_PRIORITY = {
    "PERSON": 1,
    "ORG": 2, 
    "GPE": 3,
    "PRODUCT": 4,
    "EVENT": 5,
    "WORK_OF_ART": 6,
    "LAW": 7,
    "LANGUAGE": 8
}

# Minimum entity length to store (shorter entities are ignored)
MIN_ENTITY_LENGTH = 3

# Only extract noun chunks longer than this
MIN_CONCEPT_LENGTH = 3

# Maximum entities to extract per document
MAX_ENTITIES_PER_DOC = 15

# Maximum concepts to extract per document  
MAX_CONCEPTS_PER_DOC = 20

# Relationship extraction settings
ENABLE_SVO_RELATIONS = True  # Subject-verb-object relationships
ENABLE_COOCCURRENCE_RELATIONS = True  # Co-occurrence relationships
MAX_RELATIONS_PER_DOC = 30  # Maximum relationships to create

# Maximum tokens allowed in uploaded files for smooth extraction
MAX_TOKENS_PER_FILE = 50000  # Approximately 37,500 words or 125 pages

# Words to ignore (common words that don't add value)
IGNORE_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "this", "that", "these", "those",
    "it", "its", "they", "them", "their", "we", "us", "our", "you", "your", "he", "she", "his", "her",
    "i", "me", "my", "mine", "what", "when", "where", "why", "how", "who", "which", "whose"
}

