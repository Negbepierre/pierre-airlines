# main.py — The FastAPI Server
# ─────────────────────────────────────────────────────────────
# Think of this like a waiter in a restaurant:
# - The frontend (customer) places an order
# - The waiter (FastAPI) takes it to the kitchen
# - The kitchen (LangGraph agent) prepares the response
# - The waiter brings it back to the customer
#
# FastAPI creates a web server with endpoints — URLs that
# the frontend can send messages to and get responses from
# ─────────────────────────────────────────────────────────────

import sys
import os
from pathlib import Path

# Add the agent folder to Python's search path
# So we can import agent.py from a different folder
sys.path.append(str(Path(__file__).parent / "agent"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

# Import our agent
from agent import run_agent

# ── CREATE THE APP ──
# FastAPI is like setting up a shop
# Every @app.get or @app.post is like opening a window
# where customers (the frontend) can talk to you

app = FastAPI(
    title="Pierre Airlines — Agent API",
    description="LangGraph-powered airline support agent",
    version="1.0.0"
)

# ── CORS MIDDLEWARE ──
# CORS = Cross Origin Resource Sharing
# Without this, browsers BLOCK requests between different ports
# Our frontend runs on port 5500, our server on port 8000
# This tells the browser: "yes, they're allowed to talk"
# Think of it like giving someone a visitor pass to your building

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # In production: replace with your domain
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DATA MODELS ──
# Pydantic models define exactly what shape the data must be
# If the frontend sends the wrong shape, FastAPI rejects it
# Think of it like a form — every field must be filled correctly

class Message(BaseModel):
    role: str       # "user" or "assistant"
    content: str    # the actual text

class ChatRequest(BaseModel):
    message: str              # the new message from the customer
    history: List[Message] = []  # previous messages in conversation

class ChatResponse(BaseModel):
    reply: str          # the agent's response
    escalated: bool     # was this sent to a human?
    session_id: Optional[str] = None


# ── ENDPOINTS ──

@app.get("/")
def root():
    """
    Health check endpoint
    Visit http://localhost:8000 to confirm server is running
    """
    return {
        "status": "Pierre Airlines Agent API is running",
        "version": "1.0.0",
        "agent": "Pierre Assist — LangGraph + Claude"
    }


@app.get("/health")
def health():
    """
    Detailed health check
    Used by monitoring systems to verify the server is alive
    """
    return {
        "status": "healthy",
        "model": "claude-sonnet-4-5",
        "tools_available": [
            "check_booking",
            "check_flight_status",
            "check_upgrade",
            "calculate_compensation",
            "rebook_flight",
            "create_ticket"
        ]
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    THE MAIN ENDPOINT — this is where all the magic happens

    The frontend sends:
    {
        "message": "My flight was delayed",
        "history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }

    We pass it to the LangGraph agent and return:
    {
        "reply": "Based on EU261...",
        "escalated": false
    }
    """
    try:
        # Convert Pydantic models to plain dicts for the agent
        history_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in request.history
        ]

        # Run the LangGraph agent
        result = run_agent(
            user_message=request.message,
            history=history_dicts
        )

        return ChatResponse(
            reply=result["reply"],
            escalated=result["escalated"]
        )

    except Exception as e:
        # If anything goes wrong, return a proper error
        # Never expose internal errors to the frontend
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(e)}"
        )


@app.get("/flights/{flight_number}")
def get_flight(flight_number: str):
    """
    Direct flight lookup endpoint
    Example: GET /flights/PA2847
    Useful for the frontend to show live flight status
    """
    sys.path.append(str(Path(__file__).parent / "agent"))
    from tools import check_flight_status
    result = check_flight_status(flight_number.upper())
    return {"flight": flight_number.upper(), "status": result}


@app.get("/bookings/{booking_ref}")
def get_booking(booking_ref: str):
    """
    Direct booking lookup endpoint
    Example: GET /bookings/PR-48291
    """
    from tools import check_booking
    result = check_booking(booking_ref.upper())
    return {"booking_ref": booking_ref.upper(), "details": result}


# ── RUN THE SERVER ──
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",   # accept connections from any IP
        port=8000,         # run on port 8000
        reload=True        # auto-restart when you save changes
    )
