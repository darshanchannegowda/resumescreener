# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import jobs, resumes, evaluations, auth

# Initialize FastAPI app
app = FastAPI(
    title="Resume Relevance Check System",
    description="AI-powered resume evaluation system (local demo)",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(jobs.router, prefix="/api", tags=["Jobs"])
app.include_router(resumes.router, prefix="/api", tags=["Resumes"])
app.include_router(evaluations.router, prefix="/api", tags=["Evaluations"])


@app.get("/")
async def root():
    return {"status": "active", "message": "Resume Relevance Check System is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)