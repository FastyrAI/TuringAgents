import os
import uuid
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from Model.models import FileUploadResponse, FileInfo
from FalkorDB.database import DatabaseManager
from Extraction.extractors import NLPProcessor
from config import SPACY_MODEL, UPLOAD_DIR

# Initialize router
router = APIRouter(prefix="/uploads", tags=["Uploads"])

# Initialize services
db_manager = DatabaseManager()
nlp_processor = NLPProcessor(SPACY_MODEL)

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

#   http://localhost:8000/uploads/upload

@router.post("/upload", response_model=FileUploadResponse)
async def upload_text_file(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    description: str = Form("")
):
    """Upload a text file and extract knowledge from it"""
    
    # Only allow text files
    if file.content_type != 'text/plain':
        raise HTTPException(
            status_code=400, 
            detail="Only text files (.txt) are supported"
        )
    
    # Validate file size (1MB limit for text files)
    if file.size and file.size > 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size too large. Maximum 1MB allowed.")
    
    try:
        # Generate unique filename
        file_id = str(uuid.uuid4())
        filename = f"{file_id}.txt"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Store file metadata in database
        file_metadata = db_manager.store_file(
            file_id=file_id,
            original_filename=file.filename,
            stored_filename=filename,
            file_path=file_path,
            file_size=len(content),
            content_type=file.content_type,
            user_id=user_id,
            description=description
        )
        
        # Extract text content from file
        extracted_content = await extract_text_content(file_path)
        
        if extracted_content:
            # Store extracted content as a message
            stored_message = db_manager.store_message(
                content=extracted_content,
                role="file_upload",
                user_id=user_id,
                file_id=file_id
            )
            
            # Extract entities and relations from file content
            extraction_queries = nlp_processor.extract_entities_and_relations(
                content=extracted_content,
                message_id=stored_message["message_id"]
            )
            
            # Execute extraction queries
            db_manager.execute_queries(extraction_queries)
        
        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_size=len(content),
            content_type=file.content_type,
            user_id=user_id,
            message="Text file uploaded and processed successfully"
        )
        
    except Exception as e:
        # Clean up file if it was created
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


#   http://localhost:8000/uploads/files/{user_id}

@router.get("/files/{user_id}", response_model=List[FileInfo])
def get_user_files(user_id: str):
    """Get all text files uploaded by a user"""
    files = db_manager.get_user_files(user_id)
    return files

#   http://localhost:8000/uploads/files/{file_id},{user_id}
@router.delete("/files/{file_id}")
def delete_file(file_id: str, user_id: str):
    """Delete a text file and its associated data"""
    try:
        # Get file info
        file_info = db_manager.get_file(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")
        
        if file_info["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this file")
        
        # Delete file from filesystem
        file_path = file_info["file_path"]
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete from database
        db_manager.delete_file(file_id)
        
        return JSONResponse(content={"message": "File deleted successfully"})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


async def extract_text_content(file_path: str) -> str:
    """Extract text content from text file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error extracting content: {str(e)}"
