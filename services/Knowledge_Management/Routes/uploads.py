import os
import uuid
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from Model.models import FileUploadResponse, FileInfo
from FalkorDB.database import DatabaseManager
from Extraction.extractors import GeminiProcessor
from Extraction.code_processor import CodeProcessor
from config import UPLOAD_DIR, MAX_TOKENS_PER_FILE

# Initialize router
router = APIRouter(prefix="/uploads", tags=["Uploads"])

# Initialize services
db_manager = DatabaseManager()
gemini_processor = GeminiProcessor()
code_processor = CodeProcessor()

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

#   http://localhost:8000/uploads/upload

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    description: str = Form("")
):
    """Upload any file and extract knowledge from it"""
    
    # Validate file size (10MB limit for all files)
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size too large. Maximum 10MB allowed.")
    
    # Validate file type - only allow text and code files
    allowed_extensions = [
        '.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm',  # Text files
        '.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt',  # Code files
        '.sql', '.sh', '.bat', '.ps1', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',  # Config/script files
        '.css', '.scss', '.sass', '.less', '.vue', '.jsx', '.tsx', '.r', '.m', '.pl', '.lua'  # More code files
    ]
    
    if file.filename:
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"File type '{file_extension}' is not supported. Please upload text files (.txt, .md, .csv, .json, .xml, .html) or code files (.py, .js, .java, .cpp, etc.)."
            )
    
    try:
        # Generate unique filename with original extension
        file_id = str(uuid.uuid4())
        original_extension = os.path.splitext(file.filename)[1] if file.filename else ""
        filename = f"{file_id}{original_extension}"
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
        
        # Check if content was extracted successfully
        if not extracted_content or extracted_content.strip() == "":
            # Clean up file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=400, 
                detail="File appears to be empty or could not be read. Please check the file content and try again."
            )
        
        # Check token limit before extraction
        # Simple token estimation (words * 1.33 for rough token count)
        estimated_tokens = len(extracted_content.split()) * 1.33
        
        if estimated_tokens > MAX_TOKENS_PER_FILE:
            # Clean up file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(
                status_code=400, 
                detail=f"File too large for processing. Estimated {int(estimated_tokens):,} tokens exceeds the limit of {MAX_TOKENS_PER_FILE:,} tokens. Please upload a smaller file or split it into multiple files."
            )
        
        if extracted_content:
            # Store extracted content as a message
            stored_message = db_manager.store_message(
                content=extracted_content,
                role="file_upload",
                user_id=user_id,
                file_id=file_id
            )
                        # Check if this is a code file
            file_extension = os.path.splitext(file_path)[1].lower()
            code_extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp', '.cs', '.php']
            
            if file_extension in code_extensions:
                # Process as code file
                print(f"Processing {file_extension} file as code")
                code_queries = code_processor.process_code_with_calls(file_path, stored_message["message_id"])
                all_queries = code_queries
            else:
                # Process as text file using Gemini
                print(f"Processing {file_extension} file as text")
                gemini_queries = gemini_processor.extract_entities_and_relations(
                    content=extracted_content,
                    message_id=stored_message["message_id"]
                )
                all_queries = gemini_queries
            
            db_manager.execute_queries(all_queries)
        
        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_size=len(content),
            content_type=file.content_type,
            user_id=user_id,
            message="File uploaded and processed successfully"
        )
        
    except Exception as e:
        # Clean up file if it was created
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


#   http://localhost:8000/uploads/files/{user_id}

@router.get("/files/{user_id}", response_model=List[FileInfo])
def get_user_files(user_id: str):
    """Get all files uploaded by a user"""
    files = db_manager.get_user_files(user_id)
    return files

#   http://localhost:8000/uploads/files/{file_id},{user_id}
@router.delete("/files/{file_id}")
def delete_file(file_id: str, user_id: str):
    """Delete a file and its associated data"""
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
    """Extract text content from text and code files"""
    try:
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # All supported files are text-based, so read directly
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                return f"Error reading file with different encoding: {str(e)}"
        except Exception as e:
            return f"Error reading file: {str(e)}"
                
    except Exception as e:
        return f"Error extracting content: {str(e)}"
