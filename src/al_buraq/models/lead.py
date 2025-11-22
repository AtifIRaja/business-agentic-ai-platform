"""Lead model for potential carrier partners."""

from datetime import datetime
from typing import Optional
import re
import uuid

from pydantic import BaseModel, Field, field_validator, computed_field

from .enums import EquipmentType, LeadStatus, LeadSource


class ContactInfo(BaseModel):
    """Contact information for a lead."""

    phone_primary: str = Field(..., description="Primary phone number")
    phone_secondary: Optional[str] = None
    email: Optional[str] = None
    preferred_contact_method: str = "phone"
    best_time_to_call: Optional[str] = None  # e.g., "morning", "afternoon"
    timezone: str = "America/Chicago"  # Default to Central
    do_not_call: bool = False
    do_not_email: bool = False

    @field_validator("phone_primary", "phone_secondary", mode="before")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        # Strip non-digits
        digits = re.sub(r"\D", "", str(v))
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        elif len(digits) == 0:
            return None
        raise ValueError(f"Invalid phone number: {v}")

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        v = str(v).strip()
        if not re.match(r"^[\w\.\-\+]+@[\w\.\-]+\.\w+$", v):
            raise ValueError(f"Invalid email: {v}")
        return v.lower()


class AuthorityInfo(BaseModel):
    """FMCSA Authority information."""

    mc_number: str = Field(..., description="Motor Carrier number")
    dot_number: str = Field(..., description="DOT number")
    authority_status: str = "ACTIVE"  # ACTIVE, INACTIVE, NOT_AUTHORIZED
    authority_granted_date: Optional[datetime] = None
    common_authority: bool = False
    contract_authority: bool = False
    broker_authority: bool = False

    @computed_field
    @property
    def authority_age_days(self) -> int:
        """Calculate days since authority was granted."""
        if self.authority_granted_date is None:
            return 0
        delta = datetime.utcnow() - self.authority_granted_date
        return max(0, delta.days)

    @computed_field
    @property
    def is_new_authority(self) -> bool:
        """Authority less than 90 days old."""
        return self.authority_age_days < 90

    @field_validator("mc_number", mode="before")
    @classmethod
    def validate_mc(cls, v: str) -> str:
        if v is None:
            raise ValueError("MC number is required")
        # Remove 'MC' prefix if present, ensure numeric
        clean = re.sub(r"[^\d]", "", str(v))
        if not clean:
            raise ValueError(f"Invalid MC number: {v}")
        return clean

    @field_validator("dot_number", mode="before")
    @classmethod
    def validate_dot(cls, v: str) -> str:
        if v is None:
            raise ValueError("DOT number is required")
        clean = re.sub(r"[^\d]", "", str(v))
        if not clean:
            raise ValueError(f"Invalid DOT number: {v}")
        return clean


class InsuranceInfo(BaseModel):
    """Insurance coverage information."""

    liability_coverage: int = Field(default=0, ge=0, description="Liability coverage in dollars")
    cargo_coverage: int = Field(default=0, ge=0, description="Cargo coverage in dollars")
    insurance_carrier: Optional[str] = None
    policy_number: Optional[str] = None
    policy_expiration: Optional[datetime] = None
    insurance_verified: bool = False
    verification_date: Optional[datetime] = None

    # Minimum requirements (from MISSION.md)
    MIN_LIABILITY: int = 1_000_000
    MIN_CARGO: int = 100_000

    @computed_field
    @property
    def meets_minimum_requirements(self) -> bool:
        """Check if insurance meets our minimum requirements."""
        return (
            self.liability_coverage >= self.MIN_LIABILITY
            and self.cargo_coverage >= self.MIN_CARGO
        )

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if insurance is expired."""
        if self.policy_expiration is None:
            return False  # Unknown, assume valid
        return datetime.utcnow() > self.policy_expiration


class FleetInfo(BaseModel):
    """Fleet and equipment information."""

    truck_count: int = Field(default=1, ge=1, description="Number of trucks")
    driver_count: int = Field(default=1, ge=1, description="Number of drivers")
    equipment_types: list[EquipmentType] = Field(default_factory=list)
    operating_states: list[str] = Field(default_factory=list)  # State abbreviations
    preferred_lanes: list[str] = Field(default_factory=list)  # e.g., "TX-CA", "IL-FL"
    home_base_city: Optional[str] = None
    home_base_state: Optional[str] = None
    average_miles_per_week: Optional[int] = None

    @field_validator("operating_states", mode="before")
    @classmethod
    def validate_states(cls, v: list) -> list[str]:
        if v is None:
            return []
        # Convert to uppercase 2-letter codes
        return [s.upper()[:2] for s in v if s]

    @field_validator("home_base_state", mode="before")
    @classmethod
    def validate_home_state(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return v.upper()[:2]


class SafetyInfo(BaseModel):
    """Safety and compliance information from FMCSA."""

    # CSA BASIC scores (0-100, lower is better)
    unsafe_driving_score: Optional[float] = None
    hours_of_service_score: Optional[float] = None
    driver_fitness_score: Optional[float] = None
    controlled_substances_score: Optional[float] = None
    vehicle_maintenance_score: Optional[float] = None
    crash_indicator_score: Optional[float] = None

    # Summary metrics
    out_of_service_rate: Optional[float] = None  # 0-1 percentage
    total_inspections: int = 0
    total_crashes: int = 0
    fatal_crashes: int = 0

    # Endorsements
    has_hazmat: bool = False
    has_tanker: bool = False
    has_doubles_triples: bool = False

    last_inspection_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None

    @computed_field
    @property
    def overall_safety_score(self) -> Optional[float]:
        """Calculate weighted average of available CSA scores."""
        scores = [
            self.unsafe_driving_score,
            self.hours_of_service_score,
            self.vehicle_maintenance_score,
            self.crash_indicator_score,
        ]
        valid_scores = [s for s in scores if s is not None]
        if not valid_scores:
            return None
        return sum(valid_scores) / len(valid_scores)

    @computed_field
    @property
    def safety_rating(self) -> str:
        """Return safety rating category."""
        score = self.overall_safety_score
        if score is None:
            return "UNKNOWN"
        if score < 50:
            return "EXCELLENT"
        if score < 70:
            return "GOOD"
        if score < 85:
            return "FAIR"
        return "POOR"


class Lead(BaseModel):
    """
    Complete lead model for a potential carrier partner.
    This is the primary output of the Hunter Agent.
    """

    # Identifiers
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Core Information
    company_name: str = Field(..., min_length=1)
    dba_name: Optional[str] = None
    owner_name: Optional[str] = None
    legal_name: Optional[str] = None

    # Nested Models
    contact: ContactInfo
    authority: AuthorityInfo
    insurance: InsuranceInfo = Field(default_factory=InsuranceInfo)
    fleet: FleetInfo = Field(default_factory=FleetInfo)
    safety: Optional[SafetyInfo] = None

    # Lead Management
    status: LeadStatus = LeadStatus.NEW
    source: LeadSource
    lead_score: float = Field(default=0.0, ge=0.0, le=1.0)
    score_breakdown: dict = Field(default_factory=dict)

    # Qualification
    is_qualified: bool = False
    disqualification_reason: Optional[str] = None

    # Verification (Investigator Agent)
    verification_status: str = "pending"  # pending, verified, failed
    social_verified: bool = False
    high_intent: bool = False
    linkedin_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    website_url: Optional[str] = None
    search_snippets: list[str] = Field(default_factory=list)
    verified_at: Optional[datetime] = None

    # Communication History
    contact_attempts: int = 0
    successful_contacts: int = 0
    last_contact_date: Optional[datetime] = None
    last_contact_outcome: Optional[str] = None
    next_follow_up_date: Optional[datetime] = None
    assigned_to: Optional[str] = None  # Sales agent ID

    # Notes and tags
    notes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    scraped_at: Optional[datetime] = None
    qualified_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None

    class Config:
        use_enum_values = True

    def add_note(self, note: str) -> None:
        """Add a timestamped note."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        self.notes.append(f"[{timestamp}] {note}")
        self.updated_at = datetime.utcnow()

    def mark_contacted(self, outcome: str) -> None:
        """Record a contact attempt."""
        self.contact_attempts += 1
        self.last_contact_date = datetime.utcnow()
        self.last_contact_outcome = outcome
        self.updated_at = datetime.utcnow()
        if self.status == LeadStatus.NEW:
            self.status = LeadStatus.CONTACTED

    def qualify(self, score: float, breakdown: dict) -> None:
        """Mark lead as qualified with score."""
        self.lead_score = score
        self.score_breakdown = breakdown
        self.is_qualified = True
        self.status = LeadStatus.QUALIFIED
        self.qualified_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def disqualify(self, reason: str) -> None:
        """Mark lead as disqualified."""
        self.is_qualified = False
        self.disqualification_reason = reason
        self.status = LeadStatus.REJECTED
        self.updated_at = datetime.utcnow()

    def to_embedding_text(self) -> str:
        """Generate text representation for vector embedding."""
        parts = [
            f"Company: {self.company_name}",
            f"MC: {self.authority.mc_number}",
            f"DOT: {self.authority.dot_number}",
            f"Trucks: {self.fleet.truck_count}",
            f"Equipment: {', '.join(str(e) for e in self.fleet.equipment_types)}",
            f"States: {', '.join(self.fleet.operating_states)}",
            f"Lanes: {', '.join(self.fleet.preferred_lanes)}",
        ]
        if self.fleet.home_base_state:
            parts.append(f"Based in: {self.fleet.home_base_city or ''}, {self.fleet.home_base_state}")
        return " | ".join(parts)

    def to_search_dict(self) -> dict:
        """Convert to dictionary for search/filter operations (ChromaDB compatible)."""
        # ChromaDB metadata only accepts str, int, float, bool - convert lists to strings
        equipment_str = ",".join(
            e.value if hasattr(e, 'value') else str(e)
            for e in self.fleet.equipment_types
        )
        states_str = ",".join(self.fleet.operating_states)

        return {
            "id": self.id,
            "company_name": self.company_name,
            "mc_number": self.authority.mc_number,
            "dot_number": self.authority.dot_number,
            "truck_count": self.fleet.truck_count,
            "equipment_types": equipment_str,
            "operating_states": states_str,
            "home_base_state": self.fleet.home_base_state or "",
            "lead_score": self.lead_score,
            "status": str(self.status),
            "source": str(self.source),
            "is_qualified": self.is_qualified,
            "authority_age_days": self.authority.authority_age_days,
            "meets_insurance": self.insurance.meets_minimum_requirements,
        }
