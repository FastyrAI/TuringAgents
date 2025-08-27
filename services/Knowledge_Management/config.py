# Database Configuration
FALKORDB_HOST = "r-6jissuruar.instance-sqfov9if0.hc-2uaqqpjgg.us-east-2.aws.f2e0a955bb84.cloud"
FALKORDB_PORT = 50224
FALKORDB_USERNAME = "falkordb"
FALKORDB_PASSWORD = "jawadafzal1233"
FALKORDB_GRAPH_NAME = "Tgraph"

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

# Words to ignore (common words that don't add value)
IGNORE_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "this", "that", "these", "those",
    "it", "its", "they", "them", "their", "we", "us", "our", "you", "your", "he", "she", "his", "her",
    "i", "me", "my", "mine", "what", "when", "where", "why", "how", "who", "which", "whose"
}
