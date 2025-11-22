"""
Hunter Agent

The Hunter Agent is responsible for autonomous lead generation.
It orchestrates multiple hunters, scores leads, and manages the
lead pipeline.
"""

import asyncio
from datetime import datetime
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field

from ..models.lead import Lead
from ..models.enums import LeadStatus
from ..hunters import FMCSAHunter, HuntResult
from ..scoring import LeadScorer
from ..db import Repository, VectorStore, get_repository, get_vector_store
from ..config import settings


@dataclass
class HuntingSession:
    """Tracks a hunting session's progress and results."""

    session_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Counters
    total_found: int = 0
    total_scored: int = 0
    total_qualified: int = 0
    total_saved: int = 0
    total_duplicates: int = 0
    total_errors: int = 0

    # Results by source
    source_results: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    @property
    def qualification_rate(self) -> float:
        if self.total_scored == 0:
            return 0.0
        return self.total_qualified / self.total_scored

    def complete(self) -> "HuntingSession":
        self.completed_at = datetime.utcnow()
        return self

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "duration_seconds": self.duration_seconds,
            "total_found": self.total_found,
            "total_scored": self.total_scored,
            "total_qualified": self.total_qualified,
            "total_saved": self.total_saved,
            "total_duplicates": self.total_duplicates,
            "total_errors": self.total_errors,
            "qualification_rate": round(self.qualification_rate, 3),
            "source_results": self.source_results,
        }


class HunterAgent:
    """
    Autonomous lead generation agent.

    The Hunter Agent:
    1. Finds potential carriers from multiple sources
    2. Scores and qualifies leads
    3. Deduplicates against existing database
    4. Stores qualified leads for sales outreach

    This is a Level 5 autonomous agent that can run unsupervised.
    """

    def __init__(
        self,
        repository: Optional[Repository] = None,
        vector_store: Optional[VectorStore] = None,
        scorer: Optional[LeadScorer] = None,
    ):
        """
        Initialize the Hunter Agent.

        Args:
            repository: Database repository (uses default if None)
            vector_store: Vector store for semantic search (uses default if None)
            scorer: Lead scorer (uses default if None)
        """
        self.repository = repository or get_repository()
        self.vector_store = vector_store or get_vector_store()
        self.scorer = scorer or LeadScorer()

        # Initialize hunters
        self.hunters = {
            "fmcsa": FMCSAHunter(),
            # Future: Add more hunters here
            # "dat": DATHunter(),
            # "truckstop": TruckstopHunter(),
        }

    async def hunt(
        self,
        sources: Optional[list[str]] = None,
        limit_per_source: int = 50,
        min_score: Optional[float] = None,
        save_results: bool = True,
        **kwargs,
    ) -> HuntingSession:
        """
        Run a hunting session across specified sources.

        Args:
            sources: List of source names to hunt from (None = all)
            limit_per_source: Maximum leads per source
            min_score: Minimum score to save (None = use threshold)
            save_results: Whether to persist results to database

        Returns:
            HuntingSession with results
        """
        session = HuntingSession(
            session_id=f"hunt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        )

        # Determine which sources to use
        active_sources = sources or list(self.hunters.keys())

        for source_name in active_sources:
            if source_name not in self.hunters:
                session.errors.append(f"Unknown source: {source_name}")
                continue

            hunter = self.hunters[source_name]

            try:
                # Hunt from this source
                result = await hunter.hunt(limit=limit_per_source, **kwargs)
                session.source_results[source_name] = result.to_dict()
                session.total_found += result.total_found

                # Process each lead
                for lead in result.leads:
                    try:
                        processed_lead = await self._process_lead(
                            lead,
                            min_score=min_score,
                            save=save_results,
                        )

                        session.total_scored += 1

                        if processed_lead is None:
                            session.total_duplicates += 1
                        elif processed_lead.is_qualified:
                            session.total_qualified += 1
                            if save_results:
                                session.total_saved += 1

                    except Exception as e:
                        session.errors.append(f"Error processing lead: {e}")
                        session.total_errors += 1

            except Exception as e:
                session.errors.append(f"Error hunting from {source_name}: {e}")
                session.total_errors += 1

        return session.complete()

    async def hunt_stream(
        self,
        sources: Optional[list[str]] = None,
        limit_per_source: int = 50,
        **kwargs,
    ) -> AsyncIterator[Lead]:
        """
        Stream qualified leads as they're found.

        Args:
            sources: List of source names
            limit_per_source: Maximum leads per source

        Yields:
            Qualified Lead objects
        """
        active_sources = sources or list(self.hunters.keys())

        for source_name in active_sources:
            if source_name not in self.hunters:
                continue

            hunter = self.hunters[source_name]

            async for lead in hunter.hunt_stream(limit=limit_per_source, **kwargs):
                processed = await self._process_lead(lead, save=True)
                if processed and processed.is_qualified:
                    yield processed

    async def _process_lead(
        self,
        lead: Lead,
        min_score: Optional[float] = None,
        save: bool = True,
    ) -> Optional[Lead]:
        """
        Process a single lead: dedupe, score, qualify, save.

        Args:
            lead: The lead to process
            min_score: Minimum score threshold
            save: Whether to save to database

        Returns:
            Processed lead, or None if duplicate
        """
        threshold = min_score or settings.LEAD_QUALIFICATION_THRESHOLD

        # Check for duplicate by MC number
        existing = self.repository.get_lead_by_mc(lead.authority.mc_number)
        if existing:
            return None  # Duplicate

        # Score and qualify
        self.scorer.qualify_lead(lead)

        # Check threshold
        if lead.lead_score < threshold:
            lead.is_qualified = False
            lead.disqualification_reason = (
                f"Score {lead.lead_score:.2f} below threshold {threshold}"
            )

        # Save to database and vector store
        if save:
            self.repository.save_lead(lead)
            self.vector_store.add_lead(lead)

        return lead

    async def find_similar_carriers(
        self,
        query: str,
        limit: int = 10,
        qualified_only: bool = True,
    ) -> list[Lead]:
        """
        Find carriers similar to a query using semantic search.

        Args:
            query: Search query (e.g., "owner operator in Texas with reefer")
            limit: Maximum results
            qualified_only: Only return qualified leads

        Returns:
            List of matching leads
        """
        where = None
        if qualified_only:
            where = {"is_qualified": True}

        results = self.vector_store.search_leads(
            query=query,
            n_results=limit,
            where=where,
        )

        leads = []
        for result in results:
            lead = self.repository.get_lead(result["id"])
            if lead:
                leads.append(lead)

        return leads

    async def refresh_lead(self, lead_id: str) -> Optional[Lead]:
        """
        Refresh a lead's information from source.

        Args:
            lead_id: ID of lead to refresh

        Returns:
            Updated lead or None if not found
        """
        lead = self.repository.get_lead(lead_id)
        if not lead:
            return None

        # Re-verify authority status
        hunter = self.hunters.get("fmcsa")
        if hunter:
            status = await hunter.verify_authority(lead.authority.mc_number)
            lead.authority.authority_status = status.get("status", "UNKNOWN")

        # Re-score
        self.scorer.qualify_lead(lead)

        # Update
        self.repository.save_lead(lead)
        self.vector_store.add_lead(lead)

        return lead

    def get_lead_pipeline_stats(self) -> dict:
        """Get statistics about the lead pipeline."""
        db_stats = self.repository.get_stats()
        vector_stats = self.vector_store.get_collection_stats()

        return {
            "database": db_stats["leads"],
            "vector_store": {"leads": vector_stats["leads"]},
            "pipeline": {
                "new_leads": db_stats["leads"]["new"],
                "qualified_leads": db_stats["leads"]["qualified"],
                "conversion_rate": (
                    db_stats["leads"]["converted"] / max(1, db_stats["leads"]["total"])
                ),
            },
        }

    async def get_top_leads(
        self,
        limit: int = 20,
        status: Optional[LeadStatus] = None,
    ) -> list[Lead]:
        """
        Get top leads by score.

        Args:
            limit: Maximum leads to return
            status: Filter by status

        Returns:
            List of leads sorted by score
        """
        leads = self.repository.list_leads(
            status=status,
            is_qualified=True,
            limit=limit,
        )
        return sorted(leads, key=lambda x: x.lead_score, reverse=True)

    async def cleanup_old_leads(
        self,
        days_old: int = 90,
        status: LeadStatus = LeadStatus.REJECTED,
    ) -> int:
        """
        Clean up old rejected leads.

        Args:
            days_old: Minimum age in days
            status: Status to filter by

        Returns:
            Number of leads deleted
        """
        # Get old leads
        leads = self.repository.list_leads(status=status, limit=1000)

        deleted = 0
        cutoff = datetime.utcnow()

        for lead in leads:
            age_days = (cutoff - lead.created_at).days
            if age_days >= days_old:
                self.repository.delete_lead(lead.id)
                self.vector_store.delete_lead(lead.id)
                deleted += 1

        return deleted


# =============================================================================
# Convenience Functions
# =============================================================================

async def run_hunt(
    sources: Optional[list[str]] = None,
    limit: int = 50,
) -> HuntingSession:
    """Quick function to run a hunt."""
    agent = HunterAgent()
    return await agent.hunt(sources=sources, limit_per_source=limit)


async def find_carriers(query: str, limit: int = 10) -> list[Lead]:
    """Quick function to search carriers."""
    agent = HunterAgent()
    return await agent.find_similar_carriers(query=query, limit=limit)
