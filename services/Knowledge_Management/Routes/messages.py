from fastapi import APIRouter
from Model.models import Message, MessageResponse, MessagesResponse
from FalkorDB.database import DatabaseManager
from Extraction.extractors import GeminiProcessor


# Initialize router
router = APIRouter(prefix="/messages", tags=["Messages"])

# Initialize services
db_manager = DatabaseManager()
gemini_processor = GeminiProcessor()


#   http://localhost:8000/messages/store

@router.post("/store", response_model=MessageResponse)
def store_message(message: Message):
    """Store a message and extract entities/relations"""
    # Store message in database
    stored_message = db_manager.store_message(
        content=message.content,
        role=message.role,
        user_id=message.user_id
    )
    
    
    # Extract entities and relations using Gemini
    gemini_queries = gemini_processor.extract_entities_and_relations(
        content=message.content,
        message_id=stored_message["message_id"]
    )
    
    all_queries = gemini_queries
    db_manager.execute_queries(all_queries)
    
    return MessageResponse(**stored_message)

@router.get("/{user_id}", response_model=MessagesResponse)
def get_messages(user_id: str):
    """Retrieve messages for a specific user"""
    messages = db_manager.get_messages(user_id)
    return MessagesResponse(user_id=user_id, messages=messages)

#   http://localhost:8000/messages/{user_id}
