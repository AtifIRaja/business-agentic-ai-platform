"""Base hunter interface for lead generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, AsyncIterator

from ..models.lead import Lead


@dataclass
class HuntResult:
    """Result of a hunting operation."""

    leads: list[Lead] = field(default_factory=list)
    total_found: int = 0
    total_processed: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    source: str = "unknown"

    @property
    def duration_seconds(self) -> float:
        """Calculate hunt duration."""
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_processed == 0:
            return 0.0
        return len(self.leads) / self.total_processed

    def complete(self) -> "HuntResult":
        """Mark hunt as complete."""
        self.completed_at = datetime.utcnow()
        return self

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "leads_count": len(self.leads),
            "total_found": self.total_found,
            "total_processed": self.total_processed,
            "errors_count": len(self.errors),
            "duration_seconds": self.duration_seconds,
            "success_rate": self.success_rate,
            "source": self.source,
        }


class BaseHunter(ABC):
    """
    Abstract base class for lead hunters.

    Hunters are responsible for finding and collecting potential
    carrier leads from various sources.
    """

    def __init__(self, source_name: str):
        """
        Initialize the hunter.

        Args:
            source_name: Name of the lead source
        """
        self.source_name = source_name

    @abstractmethod
    async def hunt(
        self,
        limit: int = 50,
        **kwargs,
    ) -> HuntResult:
        """
        Hunt for leads from this source.

        Args:
            limit: Maximum number of leads to find
            **kwargs: Source-specific parameters

        Returns:
            HuntResult with found leads
        """
        pass

    @abstractmethod
    async def hunt_stream(
        self,
        limit: int = 50,
        **kwargs,
    ) -> AsyncIterator[Lead]:
        """
        Hunt for leads and yield them as they're found.

        Args:
            limit: Maximum number of leads to find
            **kwargs: Source-specific parameters

        Yields:
            Lead objects as they're discovered
        """
        pass

    async def validate_lead(self, lead: Lead) -> tuple[bool, str]:
        """
        Validate a lead meets basic requirements.

        Args:
            lead: The lead to validate

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check required fields
        if not lead.company_name:
            return (False, "Missing company name")

        if not lead.authority.mc_number:
            return (False, "Missing MC number")

        if not lead.authority.dot_number:
            return (False, "Missing DOT number")

        if not lead.contact.phone_primary:
            return (False, "Missing phone number")

        return (True, "Valid lead")
