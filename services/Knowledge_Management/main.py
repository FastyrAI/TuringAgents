from fastapi import FastAPI
from Routes import messages, uploads
from config import API_TITLE, API_HOST, API_PORT

# Initialize FastAPI app
app = FastAPI(title=API_TITLE)

# Include routers
app.include_router(messages.router)
app.include_router(uploads.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)

# You can check this on the browser by going to http://localhost:8000/docs#/
