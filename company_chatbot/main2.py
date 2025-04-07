import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from websocket import websocket_endpoint
import os
from fastapi.responses import JSONResponse

app = FastAPI(title="LogBinary AI Chatbot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
app.mount("/static", StaticFiles(directory="company_chatbot/static"), name="static")

@app.get("/")
async def get_homepage():
    return FileResponse("company_chatbot/static/index.html")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    try:
        # Validate file type
        if not file.filename.lower().endswith(('.pdf', '.docx')):
            return JSONResponse(
                status_code=400,
                content={"error": "File must be PDF or DOCX format"}
            )
        
        # Create a unique filename to prevent overwrites
        import uuid
        original_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{str(uuid.uuid4())}{original_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write file to disk
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Return the path that can be referenced in the application
        return {"filename": file_path}
    
    except Exception as e:
        import traceback
        print(f"Error uploading file: {e}")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": f"File upload failed: {str(e)}"}
        )

# WebSocket endpoint
app.websocket("/ws")(websocket_endpoint)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=6440)