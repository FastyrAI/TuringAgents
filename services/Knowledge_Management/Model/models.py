from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Message(BaseModel):
    content: str
    role: str  # "user" or "agent"
    user_id: str

class MessageResponse(BaseModel):
    message_id: str
    content: str
    role: str
    user_id: str
    timestamp: str

class MessagesResponse(BaseModel):
    user_id: str
    messages: List[MessageResponse]

# File upload models
class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    file_size: int
    content_type: str
    user_id: str
    message: str

class FileInfo(BaseModel):
    file_id: str
    original_filename: str
    stored_filename: str
    file_path: str
    file_size: int
    content_type: str
    user_id: str
    description: Optional[str] = None
    upload_timestamp: Optional[str] = None
