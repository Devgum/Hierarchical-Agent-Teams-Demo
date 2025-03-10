#!/usr/bin/env python
# coding: utf-8

import os
import uuid
import tempfile
import shutil
import logging
from typing import Dict, Any, List, Optional
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
import json

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import setup_environment
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from graph import build_research_team_graph, build_writing_team_graph, build_super_team_graph

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Session class, stores session information and super_team instance
class Session:
    def __init__(self, super_team, working_dir: Path):
        self.id = str(uuid.uuid4())
        self.super_team = super_team
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.working_dir = working_dir
        logger.info(f"Created new session: {self.id}, super_team: {self.super_team}")
    
    def update_last_used(self):
        self.last_used = datetime.now()

# Session manager
class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.llm = None
        self.tavily_tool = None
    
    def initialize(self):
        """Initialize environment and shared resources"""
        logger.info("Initializing session manager")
        setup_environment()
        
        self.llm = ChatOpenAI(model="gpt-4o")
        # self.llm = ChatOpenAI(
        #     model="openai/gpt-4o-2024-11-20",
        #     temperature=0,
        #     api_key=os.environ["OPENROUTER_API_KEY"],
        #     base_url="https://openrouter.ai/api/v1",
        # )
        
        self.tavily_tool = TavilySearchResults(max_results=5)
        logger.info(f"LLM and tools initialization completed: {self.llm}, {self.tavily_tool}")
    
    def create_session(self) -> Session:
        """Create new session"""
        logger.info("Starting to create new session")
        if self.llm is None:
            logger.info("LLM not initialized, initializing now")
            self.initialize()
        
        # Create temporary directory as working directory
        temp_dir = Path(tempfile.mkdtemp(prefix="agent_session_"))
        logger.info(f"Created temporary working directory: {temp_dir}")
            
        logger.info("Starting to build super_team")
        super_team = self.build_super_team(temp_dir)
        logger.info(f"super_team build completed: {super_team}")
        
        session = Session(super_team, temp_dir)
        self.sessions[session.id] = session
        logger.info(f"Session creation completed: {session.id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session"""
        logger.info(f"Attempting to get session: {session_id}")
        session = self.sessions.get(session_id)
        if session:
            session.update_last_used()
            logger.info(f"Found session: {session_id}")
        else:
            logger.warning(f"Session not found: {session_id} sessions:{self.sessions}")
        return session
    
    def build_super_team(self, working_dir: Path):
        """Build super_team instance"""
        logger.info("Starting to build research_team")
        research_team = build_research_team_graph(self.llm, self.tavily_tool)
        logger.info(f"research_team build completed: {research_team}")
        
        logger.info("Starting to build writing_team")
        writing_team = build_writing_team_graph(self.llm, working_dir)
        logger.info(f"writing_team build completed: {writing_team}")
        
        logger.info("Starting to build super_team")
        super_team = build_super_team_graph(self.llm, research_team, writing_team)
        logger.info(f"super_team build completed: {super_team}")
        
        return super_team
    
    def cleanup_old_sessions(self, max_age_hours=24):
        """Clean up old sessions"""
        now = datetime.now()
        expired_time = now - timedelta(hours=max_age_hours)
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if session.last_used < expired_time
        ]
        for session_id in expired_sessions:
            self._cleanup_session(session_id)
        return len(expired_sessions)
    
    def _cleanup_session(self, session_id):
        """Clean up resources for a single session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            # Delete temporary working directory
            if session.working_dir.exists():
                try:
                    shutil.rmtree(session.working_dir, ignore_errors=True)
                except Exception as e:
                    logger.error(f"Error cleaning up session directory: {e}")
            # Delete session
            del self.sessions[session_id]
            logger.info(f"Session cleaned up: {session_id}")

# Create session manager instance
session_manager = SessionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Execute on startup
    logger.info("Application starting, initializing session manager")
    session_manager.initialize()
    yield
    # Execute on shutdown - clean up all sessions
    logger.info("Application shutting down, cleaning up all sessions")
    for session_id in list(session_manager.sessions.keys()):
        session_manager._cleanup_session(session_id)

# Initialize FastAPI application
app = FastAPI(
    title="Hierarchical Agent Team API", 
    description="API for interacting with hierarchical agent teams",
    lifespan=lifespan
)

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins, should be restricted in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define request model
class QueryRequest(BaseModel):
    query: str
    recursion_limit: int = 150
    session_id: Optional[str] = None

# Define response model
class QueryResponse(BaseModel):
    results: List[str]
    session_id: str

# Define session response model
class SessionResponse(BaseModel):
    session_id: str

# Define file list response model
class FileListResponse(BaseModel):
    files: List[str]
    session_id: str

# Dependency function to get or create session
async def get_or_create_session(session_id: Optional[str] = None):
    """Get existing session or create new one"""
    logger.info(f"Attempting to get or create session, session_id: {session_id}")
    if session_id:
        session = session_manager.get_session(session_id)
        if session:
            logger.info(f"Using existing session: {session_id}")
            return session
    
    # If no session ID provided or session doesn't exist, create new session
    logger.info("Creating new session")
    return session_manager.create_session()

@app.post("/session", response_model=SessionResponse)
async def create_new_session():
    """Create new session"""
    logger.info("API request: Create new session")
    session = session_manager.create_session()
    return SessionResponse(session_id=session.id)

@app.get("/session", response_model=SessionResponse)
async def get_session_info(session_id: Optional[str] = None):
    """Get session info, verify if session exists if session_id is provided, otherwise create new session"""
    logger.info(f"API request: Get session info, session_id: {session_id}")
    
    if session_id:
        # Verify if session exists
        session = session_manager.get_session(session_id)
        if session:
            logger.info(f"Session exists: {session_id}")
            # Use FastAPI's Response object to set headers
            return JSONResponse(
                content={"session_id": session.id},
                headers={"X-Session-ID": session.id}
            )
        else:
            logger.info(f"Session doesn't exist: {session_id}, creating new session")
            session = session_manager.create_session()
            return JSONResponse(
                content={"session_id": session.id},
                headers={"X-Session-ID": session.id}
            )
    else:
        # No session_id provided, create new session
        logger.info("No session_id provided, creating new session")
        session = session_manager.create_session()
        return JSONResponse(
            content={"session_id": session.id},
            headers={"X-Session-ID": session.id}
        )

async def stream_generator(query: str, session: Session, recursion_limit: int = 150):
    """Async generator for streaming responses"""
    try:
        if session.super_team is None:
            error_msg = "super_team is None, cannot call astream method"
            logger.error(error_msg)
            yield f"data: ERROR: {error_msg}\n\n"
            yield f"event: end\ndata: {error_msg}\n\n"
            return
            
        stream_input = {
            "messages": [
                ("user", query)
            ],
        }
        stream_config = {"recursion_limit": recursion_limit}
        # async for response in session.super_team.astream(stream_input, stream_config, stream_mode="updates"):
        #     # Send each result as a separate event
        #     for key, value in response.items():
        #         response_data = {}
        #         response_data['sender'] = key
        #         for kk, vv in value.items():
        #             if kk == 'next':
        #                 response_data[kk] = vv
        #             elif kk == 'messages':
        #                 response_data[kk] = vv[0].text()
        #     yield f"data: {json.dumps(response_data)}\n\n"

        async for response, metadata in session.super_team.astream(stream_input, stream_config, stream_mode="messages"):
            response_data = {
                "response": response.text(),
                "metadata": metadata
            }
            yield f"data: {json.dumps(response_data)}\n\n"
        
        # After all data is sent, send end event
        yield f"event: end\ndata: Processing completed\n\n"
    except Exception as e:
        error_msg = f"Error generating streaming response: {str(e)}"
        logger.error(error_msg, exc_info=True)
        yield f"data: ERROR: {error_msg}\n\n"
        # Send end event even if error occurs, to notify client to close connection
        yield f"event: end\ndata: Processing error: {str(e)}\n\n"

@app.get("/query")
async def query_agent_get(
    query: str = Query(..., description="User query"),
    recursion_limit: int = Query(150, description="Recursion limit"),
    session_id: Optional[str] = None
):
    """Stream agent responses via GET request"""
    logger.info(f"API request: GET /query, query: {query}, recursion_limit: {recursion_limit}, session_id: {session_id}")
    session = await get_or_create_session(session_id)
    return StreamingResponse(
        stream_generator(query, session, recursion_limit),
        media_type="text/event-stream",
        headers={"X-Session-ID": session.id}
    )

@app.post("/query")
async def query_agent_post(request: QueryRequest):
    """Stream agent responses via POST request"""
    logger.info(f"API request: POST /query, query: {request.query}, recursion_limit: {request.recursion_limit}, session_id: {request.session_id}")
    session = await get_or_create_session(request.session_id)
    return StreamingResponse(
        stream_generator(request.query, session, request.recursion_limit),
        media_type="text/event-stream",
        headers={"X-Session-ID": session.id}
    )

@app.get("/files")
async def list_files(session_id: str):
    """Get list of files in working directory"""
    try:
        logger.info(f"Getting file list for session {session_id}")
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} does not exist")
        
        session.update_last_used()
        
        # Get all files in working directory
        files = []
        for file_path in session.working_dir.glob("**/*"):
            if file_path.is_file():
                # Return path relative to working directory
                rel_path = file_path.relative_to(session.working_dir)
                files.append(str(rel_path))
        
        return FileListResponse(files=files, session_id=session_id)
    except Exception as e:
        logger.error(f"Error getting file list: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting file list: {str(e)}")

@app.get("/download")
async def download_file(session_id: str, file_path: str):
    """Download file from working directory"""
    try:
        logger.info(f"Downloading file from session {session_id}: {file_path}")
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} does not exist")
        
        session.update_last_used()
        
        # Build complete file path
        full_path = session.working_dir / file_path
        
        # Check if file exists and is within working directory
        if not full_path.exists():
            raise HTTPException(status_code=404, detail=f"File {file_path} does not exist")
        
        if not full_path.is_file():
            raise HTTPException(status_code=400, detail=f"{file_path} is not a file")
        
        # Check if file is within working directory (security check)
        try:
            full_path.relative_to(session.working_dir)
        except ValueError:
            raise HTTPException(status_code=403, detail="Cannot access files outside working directory")
        
        # Return file
        return FileResponse(
            path=str(full_path),
            filename=full_path.name,
            media_type="application/octet-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

# If this file is run directly, start API server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)