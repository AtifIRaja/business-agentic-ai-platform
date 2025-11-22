"""
Investigator Agent - Verify leads before outreach.

Uses DuckDuckGo search to find social media presence and intent signals.
"""

import re
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from ..models.lead import Lead
from ..db import Repository


@dataclass
class InvestigationResult:
    """Result of investigating a single lead."""

    lead_id: str
    company_name: str
    social_verified: bool = False
    high_intent: bool = False
    linkedin_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    website_url: Optional[str] = None
    snippets: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class InvestigationSession:
    """Results from an investigation session."""

    total_investigated: int = 0
    social_verified_count: int = 0
    high_intent_count: int = 0
    errors: int = 0
    results: list[InvestigationResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    def complete(self, start_time: datetime) -> "InvestigationSession":
        """Mark session as complete and calculate duration."""
        self.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return self


# Keywords that indicate high intent to work with dispatchers
HIGH_INTENT_KEYWORDS = [
    "hiring",
    "dispatcher",
    "dispatch service",
    "owner operator",
    "looking for loads",
    "need freight",
    "truck driver",
    "cdl driver",
    "freight broker",
    "trucking job",
    "hauling",
    "new authority",
    "dispatch partner",
]


class InvestigatorAgent:
    """
    Agent that investigates leads to verify their legitimacy.

    Uses DuckDuckGo search to find:
    - Social media presence (LinkedIn, Facebook, Instagram)
    - Website presence
    - Intent signals (hiring, looking for dispatch, etc.)
    """

    def __init__(self, repository: Repository):
        self.repository = repository
        self.ddgs = DDGS()

    def _extract_social_urls(self, results: list[dict]) -> dict:
        """Extract social media URLs from search results."""
        urls = {
            "linkedin": None,
            "facebook": None,
            "instagram": None,
            "website": None,
        }

        for result in results:
            url = result.get("href", "").lower()

            if "linkedin.com" in url and not urls["linkedin"]:
                urls["linkedin"] = result.get("href")
            elif "facebook.com" in url and not urls["facebook"]:
                urls["facebook"] = result.get("href")
            elif "instagram.com" in url and not urls["instagram"]:
                urls["instagram"] = result.get("href")
            elif not urls["website"]:
                # First non-social URL could be company website
                if not any(x in url for x in ["linkedin", "facebook", "instagram", "twitter", "yelp", "yellowpages"]):
                    urls["website"] = result.get("href")

        return urls

    def _check_high_intent(self, results: list[dict]) -> tuple[bool, list[str]]:
        """Check if search results indicate high intent."""
        snippets = []
        high_intent = False

        for result in results:
            title = result.get("title", "").lower()
            body = result.get("body", "").lower()
            combined = f"{title} {body}"

            for keyword in HIGH_INTENT_KEYWORDS:
                if keyword in combined:
                    high_intent = True
                    # Save relevant snippet
                    snippet = result.get("body", "")[:150]
                    if snippet and snippet not in snippets:
                        snippets.append(snippet)
                    break

        return high_intent, snippets[:3]  # Keep top 3 snippets

    def investigate_lead(self, lead: Lead) -> InvestigationResult:
        """
        Investigate a single lead using DuckDuckGo search.

        Args:
            lead: Lead to investigate

        Returns:
            InvestigationResult with findings
        """
        result = InvestigationResult(
            lead_id=lead.id,
            company_name=lead.company_name,
        )

        # Build search query
        query = f'"{lead.company_name}" trucking reviews linkedin facebook'

        try:
            # Run DuckDuckGo search
            search_results = list(self.ddgs.text(query, max_results=10))

            if not search_results:
                result.error = "No search results found"
                return result

            # Extract social URLs
            urls = self._extract_social_urls(search_results)
            result.linkedin_url = urls["linkedin"]
            result.facebook_url = urls["facebook"]
            result.instagram_url = urls["instagram"]
            result.website_url = urls["website"]

            # Check if any social media found
            result.social_verified = any([
                urls["linkedin"],
                urls["facebook"],
                urls["instagram"],
            ])

            # Check for high intent keywords
            result.high_intent, result.snippets = self._check_high_intent(search_results)

        except Exception as e:
            result.error = str(e)

        return result

    def investigate_batch(
        self,
        limit: int = 5,
        delay_seconds: float = 2.0,
        progress_callback=None,
    ) -> InvestigationSession:
        """
        Investigate a batch of pending leads.

        Args:
            limit: Maximum leads to investigate
            delay_seconds: Delay between searches (be polite to DDG)
            progress_callback: Called with (current, total, lead_name)

        Returns:
            InvestigationSession with all results
        """
        start_time = datetime.utcnow()
        session = InvestigationSession()

        # Fetch pending leads
        pending_leads = self.repository.get_leads_for_verification(limit=limit)

        if not pending_leads:
            return session.complete(start_time)

        for i, lead in enumerate(pending_leads):
            if progress_callback:
                progress_callback(i + 1, len(pending_leads), lead.company_name)

            # Investigate lead
            result = self.investigate_lead(lead)
            session.results.append(result)
            session.total_investigated += 1

            if result.error:
                session.errors += 1
            else:
                if result.social_verified:
                    session.social_verified_count += 1
                if result.high_intent:
                    session.high_intent_count += 1

                # Update lead in database
                lead.verification_status = "verified"
                lead.social_verified = result.social_verified
                lead.high_intent = result.high_intent
                lead.linkedin_url = result.linkedin_url
                lead.facebook_url = result.facebook_url
                lead.instagram_url = result.instagram_url
                lead.website_url = result.website_url
                lead.search_snippets = result.snippets
                lead.verified_at = datetime.utcnow()
                lead.updated_at = datetime.utcnow()

                # Save to database
                self.repository.update_lead(lead)

            # Be polite - wait between searches
            if i < len(pending_leads) - 1:
                time.sleep(delay_seconds)

        return session.complete(start_time)
