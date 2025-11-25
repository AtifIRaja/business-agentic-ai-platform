"""
Al-Buraq FastAPI Server

RESTful API exposing Al-Buraq's internal logic for external integrations,
OpenAI Agent Builder, and MCP (Model Context Protocol) clients.

DEPLOYMENT OPTIONS (Free Tier):
- Railway.app: Push to GitHub, auto-deploy from main branch
- Render.com: Connect repo, select "Web Service", auto-detects FastAPI
- Fly.io: `flyctl launch` from project root
- Vercel: Requires serverless adapter

USAGE:
    Local: alburaq serve (runs on http://localhost:8000)
    Docs: http://localhost:8000/docs (Swagger UI)
    OpenAPI: http://localhost:8000/openapi.json (for Agent Builder)
"""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .agents import HunterAgent, InvestigatorAgent, DispatchAgent
from .db import get_repository
from .config import settings


# =============================================================================
# API Models (Request/Response Schemas)
# =============================================================================

class HuntRequest(BaseModel):
    """Request to trigger the Hunter Agent"""
    limit: int = Field(default=20, ge=1, le=500, description="Max leads to find")
    source: Optional[str] = Field(default=None, description="Specific source (e.g., 'fmcsa')")
    min_score: float = Field(default=0.6, ge=0.0, le=1.0, description="Minimum lead score")
    save: bool = Field(default=True, description="Save results to database")


class HuntResponse(BaseModel):
    """Response from Hunt operation"""
    success: bool
    duration_seconds: float
    total_found: int
    total_qualified: int
    qualification_rate: float
    message: str


class VerifyRequest(BaseModel):
    """Request to trigger the Investigator Agent"""
    limit: int = Field(default=5, ge=1, le=50, description="Max leads to investigate")
    delay_seconds: float = Field(default=2.0, ge=1.0, le=10.0, description="Delay between searches")


class VerifyResponse(BaseModel):
    """Response from Verify operation"""
    success: bool
    total_investigated: int
    social_verified_count: int
    high_intent_count: int
    duration_seconds: float
    message: str


class DispatchRequest(BaseModel):
    """Request to trigger Dispatch matching"""
    load_count: int = Field(default=5, ge=1, le=20, description="Number of loads to match")
    matches_per_load: int = Field(default=3, ge=1, le=10, description="Matches per load")
    mock_mode: bool = Field(default=True, description="Use sample/mock loads instead of real loads")


class DispatchMatch(BaseModel):
    """Single carrier match for a load"""
    carrier_name: str
    carrier_mc: str
    carrier_state: str
    match_score: float
    estimated_commission: float
    charity_contribution: float
    match_reasons: List[str]


class DispatchLoadRecommendation(BaseModel):
    """Load with carrier matches"""
    load_origin: str
    load_destination: str
    commodity: str
    rate: float
    halal_status: str
    matches: List[DispatchMatch]


class DispatchResponse(BaseModel):
    """Response from Dispatch operation"""
    success: bool
    total_loads: int
    halal_loads: int
    haram_loads: int
    total_matches: int
    duration_seconds: float
    recommendations: List[DispatchLoadRecommendation]
    message: str


class LeadContact(BaseModel):
    """Contact information"""
    email: Optional[str] = None
    phone: Optional[str] = None


class VerifiedLead(BaseModel):
    """Verified lead summary"""
    id: str
    company_name: str
    mc_number: str
    owner_name: Optional[str] = None
    contact: LeadContact
    state: Optional[str] = None
    truck_count: int
    equipment_types: List[str]
    lead_score: float
    social_verified: bool
    high_intent: bool
    linkedin_url: Optional[str] = None
    facebook_url: Optional[str] = None
    website_url: Optional[str] = None
    verification_status: str
    created_at: Optional[str] = None


class VerifiedLeadsResponse(BaseModel):
    """List of verified leads"""
    total: int
    leads: List[VerifiedLead]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    timestamp: str
    database_connected: bool


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Al-Buraq API",
    description=(
        "Ethical AI Dispatch System API\n\n"
        "Exposes Al-Buraq's core functionality for external integrations:\n"
        "- Hunt for new carrier leads\n"
        "- Verify leads with social media intelligence\n"
        "- Match loads to verified carriers (halal-compliant)\n"
        "- Query verified leads database\n\n"
        "Built with integrity, dispatched with honesty."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.

    Returns system status, version, and database connectivity.
    """
    try:
        repo = get_repository()
        db_connected = True
    except Exception:
        db_connected = False

    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        version=settings.APP_VERSION,
        timestamp=datetime.utcnow().isoformat(),
        database_connected=db_connected,
    )


@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Al-Buraq API",
        "version": settings.APP_VERSION,
        "description": "Ethical AI Dispatch System",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "endpoints": {
            "hunt": "POST /v1/agent/hunt",
            "verify": "POST /v1/agent/verify",
            "dispatch": "POST /v1/agent/dispatch",
            "leads": "GET /v1/leads/verified",
        },
    }


# =============================================================================
# Agent Endpoints
# =============================================================================

@app.post("/v1/agent/hunt", response_model=HuntResponse, tags=["Agents"])
async def hunt_leads(request: HuntRequest):
    """
    Trigger the Hunter Agent to find new carrier leads.

    The Hunter Agent:
    - Searches configured sources (FMCSA SAFER, load boards)
    - Scores and qualifies leads based on criteria
    - Optionally saves results to database

    Example:
        ```json
        {
          "limit": 50,
          "source": "fmcsa",
          "min_score": 0.7,
          "save": true
        }
        ```
    """
    try:
        agent = HunterAgent()

        sources = [request.source] if request.source else None

        session = await agent.hunt(
            sources=sources,
            limit_per_source=request.limit,
            min_score=request.min_score,
            save_results=request.save,
        )

        return HuntResponse(
            success=True,
            duration_seconds=session.duration_seconds,
            total_found=session.total_found,
            total_qualified=session.total_qualified,
            qualification_rate=session.qualification_rate,
            message=f"Successfully found {session.total_qualified} qualified leads",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hunt operation failed: {str(e)}")


@app.post("/v1/agent/verify", response_model=VerifyResponse, tags=["Agents"])
async def verify_leads(request: VerifyRequest):
    """
    Trigger the Investigator Agent to verify leads.

    The Investigator Agent:
    - Searches for social media presence (LinkedIn, Facebook, etc.)
    - Identifies high-intent signals for outreach
    - Updates verification status in database

    Example:
        ```json
        {
          "limit": 10,
          "delay_seconds": 3.0
        }
        ```
    """
    try:
        repo = get_repository()
        agent = InvestigatorAgent(repository=repo)

        # Run investigation synchronously (since it's already sync)
        session = agent.investigate_batch(
            limit=request.limit,
            delay_seconds=request.delay_seconds,
        )

        return VerifyResponse(
            success=True,
            total_investigated=session.total_investigated,
            social_verified_count=session.social_verified_count,
            high_intent_count=session.high_intent_count,
            duration_seconds=session.duration_seconds,
            message=f"Verified {session.social_verified_count} leads with social presence",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@app.post("/v1/agent/dispatch", response_model=DispatchResponse, tags=["Agents"])
async def dispatch_loads(request: DispatchRequest):
    """
    Trigger the Dispatch Agent to match loads with carriers.

    The Dispatch Agent:
    - Filters loads through halal compliance checker
    - Matches loads to verified carriers using AI scoring
    - Calculates commission (7%) and charity contribution (5%)
    - Returns ranked carrier recommendations

    Example:
        ```json
        {
          "load_count": 5,
          "matches_per_load": 3,
          "mock_mode": true
        }
        ```
    """
    try:
        repo = get_repository()
        agent = DispatchAgent(repository=repo)

        session = agent.run_dispatch_session(
            load_count=request.load_count,
            matches_per_load=request.matches_per_load,
            use_sample_loads=request.mock_mode,
        )

        # Convert recommendations to API format
        recommendations = []
        for rec in session.recommendations:
            load = rec.load

            matches = [
                DispatchMatch(
                    carrier_name=match.carrier_name,
                    carrier_mc=match.carrier_mc,
                    carrier_state=match.carrier_state,
                    match_score=match.match_score,
                    estimated_commission=match.estimated_commission,
                    charity_contribution=match.charity_contribution,
                    match_reasons=match.match_reasons,
                )
                for match in rec.matches
            ]

            recommendations.append(DispatchLoadRecommendation(
                load_origin=f"{load.origin.city}, {load.origin.state}",
                load_destination=f"{load.destination.city}, {load.destination.state}",
                commodity=load.commodity,
                rate=load.rate,
                halal_status=rec.halal_status,
                matches=matches,
            ))

        return DispatchResponse(
            success=True,
            total_loads=session.total_loads,
            halal_loads=session.halal_loads,
            haram_loads=session.haram_loads,
            total_matches=session.total_matches,
            duration_seconds=session.duration_seconds,
            recommendations=recommendations,
            message=f"Matched {session.total_matches} carriers to {session.halal_loads} halal loads",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dispatch failed: {str(e)}")


# =============================================================================
# Data Endpoints
# =============================================================================

@app.get("/v1/leads/verified", response_model=VerifiedLeadsResponse, tags=["Data"])
async def get_verified_leads(
    limit: int = Query(default=20, ge=1, le=500, description="Max leads to return"),
    social_verified: Optional[bool] = Query(default=None, description="Filter by social verification"),
    high_intent: Optional[bool] = Query(default=None, description="Filter by high intent"),
):
    """
    Get list of verified leads ready for outreach.

    Returns leads that have been investigated and verified,
    with optional filters for social media presence and intent signals.

    Query Parameters:
    - limit: Maximum number of leads to return (1-500)
    - social_verified: Filter by social media verification (true/false)
    - high_intent: Filter by high-intent signals (true/false)

    Example:
        GET /v1/leads/verified?limit=50&social_verified=true
    """
    try:
        repo = get_repository()

        leads_list = repo.get_verified_leads(
            social_verified=social_verified,
            high_intent=high_intent,
            limit=limit,
        )

        # Convert to API format
        verified_leads = []
        for lead in leads_list:
            equipment = [
                e.value if hasattr(e, 'value') else str(e)
                for e in lead.fleet.equipment_types
            ]

            verified_leads.append(VerifiedLead(
                id=lead.id,
                company_name=lead.company_name,
                mc_number=lead.authority.mc_number,
                owner_name=lead.owner_name,
                contact=LeadContact(
                    email=lead.contact.email,
                    phone=lead.contact.phone_primary,
                ),
                state=lead.fleet.home_base_state,
                truck_count=lead.fleet.truck_count,
                equipment_types=equipment,
                lead_score=lead.lead_score,
                social_verified=lead.social_verified,
                high_intent=lead.high_intent,
                linkedin_url=lead.linkedin_url,
                facebook_url=lead.facebook_url,
                website_url=lead.website_url,
                verification_status=lead.verification_status,
                created_at=lead.created_at.isoformat() if lead.created_at else None,
            ))

        return VerifiedLeadsResponse(
            total=len(verified_leads),
            leads=verified_leads,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch leads: {str(e)}")


# =============================================================================
# Statistics Endpoints
# =============================================================================

@app.get("/v1/stats", tags=["Data"])
async def get_stats():
    """
    Get system statistics and metrics.

    Returns:
    - Lead pipeline counts (new, qualified, verified, converted)
    - Carrier counts (active, available)
    - Load counts (available, booked, delivered)
    - Verification statistics
    """
    try:
        repo = get_repository()
        db_stats = repo.get_stats()
        v_stats = repo.get_verification_stats()

        return {
            "success": True,
            "leads": {
                "total": db_stats["leads"]["total"],
                "new": db_stats["leads"]["new"],
                "qualified": db_stats["leads"]["qualified"],
                "converted": db_stats["leads"]["converted"],
            },
            "verification": {
                "verified": v_stats["verified"],
                "pending": v_stats["pending"],
                "social_verified": v_stats["social_verified"],
                "high_intent": v_stats["high_intent"],
            },
            "carriers": db_stats["carriers"],
            "loads": db_stats["loads"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


# =============================================================================
# Server Lifecycle
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("=" * 60)
    print("Al-Buraq API Server Starting...")
    print("=" * 60)
    print(f"Version: {settings.APP_VERSION}")
    print(f"Docs: http://localhost:8000/docs")
    print(f"OpenAPI: http://localhost:8000/openapi.json")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("Al-Buraq API Server Shutting Down...")


# =============================================================================
# Main Entry Point (for direct execution)
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "al_buraq.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
