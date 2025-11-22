"""Carrier model for active dispatch partners."""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
import uuid

from pydantic import BaseModel, Field, computed_field

from .enums import CarrierStatus, EquipmentType
from .lead import ContactInfo, AuthorityInfo, InsuranceInfo, FleetInfo, SafetyInfo

if TYPE_CHECKING:
    from .lead import Lead


class DispatcherAgreement(BaseModel):
    """Dispatcher agreement details."""

    agreement_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signed_date: datetime = Field(default_factory=datetime.utcnow)
    effective_date: datetime = Field(default_factory=datetime.utcnow)
    expiration_date: Optional[datetime] = None

    commission_rate: float = Field(default=0.07, ge=0.05, le=0.15)  # 5-15%
    agreement_type: str = "standard"  # standard, premium, trial
    auto_renew: bool = True
    termination_notice_days: int = 30
    exclusive: bool = False

    # Agreement documents
    signed_document_url: Optional[str] = None
    w9_received: bool = False
    insurance_coi_received: bool = False
    mc_authority_verified: bool = False

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if agreement is currently active."""
        now = datetime.utcnow()
        if self.expiration_date and now > self.expiration_date:
            return False
        return now >= self.effective_date

    @computed_field
    @property
    def onboarding_complete(self) -> bool:
        """Check if all onboarding documents received."""
        return (
            self.w9_received
            and self.insurance_coi_received
            and self.mc_authority_verified
        )


class CarrierPreferences(BaseModel):
    """Carrier dispatch preferences - what loads they want."""

    # Rate preferences
    min_rate_per_mile: float = Field(default=2.00, ge=1.50)
    preferred_rate_per_mile: float = Field(default=2.50, ge=1.50)

    # Distance preferences
    max_deadhead_miles: int = Field(default=150, ge=0)
    min_loaded_miles: int = Field(default=100, ge=0)
    max_loaded_miles: Optional[int] = None

    # Load type preferences
    preferred_commodities: list[str] = Field(default_factory=list)
    avoid_commodities: list[str] = Field(default_factory=list)

    # Geographic preferences
    preferred_origin_states: list[str] = Field(default_factory=list)
    preferred_destination_states: list[str] = Field(default_factory=list)
    avoid_states: list[str] = Field(default_factory=list)
    avoid_cities: list[str] = Field(default_factory=list)

    # Capacity
    max_weight_lbs: Optional[int] = None

    # Availability
    team_available: bool = False
    hazmat_willing: bool = False
    tanker_willing: bool = False
    weekend_available: bool = False
    overnight_loads: bool = True

    # Communication
    preferred_contact_method: str = "phone"  # phone, sms, email
    notification_enabled: bool = True


class CarrierPerformance(BaseModel):
    """Carrier performance metrics - track record."""

    # Load history
    total_loads_offered: int = 0
    total_loads_accepted: int = 0
    total_loads_completed: int = 0
    total_loads_cancelled: int = 0

    # On-time performance (0-1 percentage)
    on_time_pickup_rate: float = 1.0
    on_time_delivery_rate: float = 1.0

    # Acceptance metrics
    load_acceptance_rate: float = 1.0  # Accepted / Offered

    # Ratings
    average_broker_rating: float = 5.0  # 1-5 scale
    average_shipper_rating: float = 5.0
    internal_rating: float = 5.0  # Our assessment

    # Financial
    total_revenue_generated: float = 0.0
    total_miles_dispatched: int = 0
    commission_earned: float = 0.0
    average_rate_per_mile: float = 0.0

    # Activity
    last_load_date: Optional[datetime] = None
    last_offered_date: Optional[datetime] = None
    days_since_last_load: int = 0

    # Issues
    claims_count: int = 0
    complaints_count: int = 0
    falloffs_count: int = 0  # Accepted then cancelled

    @computed_field
    @property
    def reliability_score(self) -> float:
        """Calculate overall reliability (0-1)."""
        if self.total_loads_offered == 0:
            return 1.0  # New carrier, benefit of doubt

        # Weighted components
        acceptance_weight = 0.3
        ontime_pickup_weight = 0.25
        ontime_delivery_weight = 0.25
        falloff_weight = 0.2

        falloff_rate = (
            self.falloffs_count / self.total_loads_accepted
            if self.total_loads_accepted > 0
            else 0
        )

        score = (
            self.load_acceptance_rate * acceptance_weight
            + self.on_time_pickup_rate * ontime_pickup_weight
            + self.on_time_delivery_rate * ontime_delivery_weight
            + (1 - falloff_rate) * falloff_weight
        )
        return round(min(1.0, max(0.0, score)), 3)

    def record_load_completed(
        self,
        revenue: float,
        miles: int,
        on_time_pickup: bool,
        on_time_delivery: bool,
    ) -> None:
        """Record a completed load."""
        self.total_loads_completed += 1
        self.total_revenue_generated += revenue
        self.total_miles_dispatched += miles
        self.last_load_date = datetime.utcnow()

        # Update running averages
        n = self.total_loads_completed
        self.on_time_pickup_rate = (
            (self.on_time_pickup_rate * (n - 1) + (1 if on_time_pickup else 0)) / n
        )
        self.on_time_delivery_rate = (
            (self.on_time_delivery_rate * (n - 1) + (1 if on_time_delivery else 0)) / n
        )
        self.average_rate_per_mile = self.total_revenue_generated / max(1, self.total_miles_dispatched)


class Carrier(BaseModel):
    """
    Full carrier model for an active dispatch partner.
    Extends lead information with operational data.
    """

    # Identifiers
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: Optional[str] = None  # Reference to original lead

    # Core Information
    company_name: str
    dba_name: Optional[str] = None
    owner_name: str
    legal_name: Optional[str] = None

    # Nested Models (from Lead)
    contact: ContactInfo
    authority: AuthorityInfo
    insurance: InsuranceInfo
    fleet: FleetInfo
    safety: Optional[SafetyInfo] = None

    # Carrier-Specific
    status: CarrierStatus = CarrierStatus.PROSPECT
    agreement: Optional[DispatcherAgreement] = None
    preferences: CarrierPreferences = Field(default_factory=CarrierPreferences)
    performance: CarrierPerformance = Field(default_factory=CarrierPerformance)

    # Current Availability
    current_location_city: Optional[str] = None
    current_location_state: Optional[str] = None
    current_location_updated: Optional[datetime] = None
    available_date: Optional[datetime] = None
    is_available: bool = False
    next_available_equipment: Optional[EquipmentType] = None

    # Driver info (for owner-operators)
    primary_driver_name: Optional[str] = None
    primary_driver_phone: Optional[str] = None
    primary_driver_cdl: Optional[str] = None

    # Tags and notes
    tags: list[str] = Field(default_factory=list)
    internal_notes: list[str] = Field(default_factory=list)

    # Timestamps
    onboarded_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True

    @computed_field
    @property
    def is_dispatchable(self) -> bool:
        """Check if carrier can receive loads."""
        return (
            self.status == CarrierStatus.ACTIVE
            and self.agreement is not None
            and self.agreement.is_active
            and self.agreement.onboarding_complete
            and self.insurance.meets_minimum_requirements
            and not self.insurance.is_expired
        )

    @computed_field
    @property
    def days_inactive(self) -> int:
        """Days since last dispatched load."""
        if self.performance.last_load_date is None:
            if self.onboarded_at:
                return (datetime.utcnow() - self.onboarded_at).days
            return 0
        return (datetime.utcnow() - self.performance.last_load_date).days

    def update_location(self, city: str, state: str) -> None:
        """Update carrier's current location."""
        self.current_location_city = city
        self.current_location_state = state.upper()[:2]
        self.current_location_updated = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_available(self, available_date: Optional[datetime] = None) -> None:
        """Mark carrier as available for loads."""
        self.is_available = True
        self.available_date = available_date or datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_unavailable(self) -> None:
        """Mark carrier as unavailable."""
        self.is_available = False
        self.available_date = None
        self.updated_at = datetime.utcnow()

    def add_note(self, note: str) -> None:
        """Add an internal note."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        self.internal_notes.append(f"[{timestamp}] {note}")
        self.updated_at = datetime.utcnow()

    @classmethod
    def from_lead(cls, lead: "Lead", agreement: DispatcherAgreement) -> "Carrier":
        """Convert a qualified lead to a carrier."""
        return cls(
            lead_id=lead.id,
            company_name=lead.company_name,
            dba_name=lead.dba_name,
            owner_name=lead.owner_name or "Unknown",
            legal_name=lead.legal_name,
            contact=lead.contact,
            authority=lead.authority,
            insurance=lead.insurance,
            fleet=lead.fleet,
            safety=lead.safety,
            status=CarrierStatus.ONBOARDING,
            agreement=agreement,
            onboarded_at=datetime.utcnow(),
            current_location_city=lead.fleet.home_base_city,
            current_location_state=lead.fleet.home_base_state,
        )

    def to_embedding_text(self) -> str:
        """Generate text for vector embedding."""
        parts = [
            f"Carrier: {self.company_name}",
            f"MC: {self.authority.mc_number}",
            f"Trucks: {self.fleet.truck_count}",
            f"Equipment: {', '.join(str(e) for e in self.fleet.equipment_types)}",
            f"Location: {self.current_location_city or 'Unknown'}, {self.current_location_state or 'Unknown'}",
            f"Preferred lanes: {', '.join(self.fleet.preferred_lanes)}",
            f"Min rate: ${self.preferences.min_rate_per_mile}/mi",
            f"Reliability: {self.performance.reliability_score:.0%}",
        ]
        return " | ".join(parts)
