"""Load model for freight shipment opportunities."""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field, computed_field

from .enums import LoadStatus, EquipmentType, HalalStatus, PaymentTerms


class Location(BaseModel):
    """Geographic location for pickup/delivery."""

    city: str
    state: str  # 2-letter abbreviation
    zip_code: Optional[str] = None
    address: Optional[str] = None
    facility_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    special_instructions: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.city}, {self.state}"

    @computed_field
    @property
    def full_address(self) -> str:
        """Return full address string."""
        parts = []
        if self.address:
            parts.append(self.address)
        parts.append(f"{self.city}, {self.state}")
        if self.zip_code:
            parts[-1] += f" {self.zip_code}"
        return ", ".join(parts)


class TimeWindow(BaseModel):
    """Pickup or delivery time window."""

    earliest: datetime
    latest: datetime
    appointment_required: bool = False
    appointment_time: Optional[datetime] = None
    fcfs: bool = False  # First Come First Serve

    @computed_field
    @property
    def window_hours(self) -> float:
        """Hours between earliest and latest."""
        delta = self.latest - self.earliest
        return delta.total_seconds() / 3600

    @computed_field
    @property
    def is_tight_window(self) -> bool:
        """Window less than 2 hours."""
        return self.window_hours < 2

    def fits_datetime(self, dt: datetime) -> bool:
        """Check if datetime fits within window."""
        return self.earliest <= dt <= self.latest


class LoadDimensions(BaseModel):
    """Physical dimensions and weight of the load."""

    weight_lbs: int = Field(default=0, ge=0)
    length_ft: Optional[float] = None
    width_ft: Optional[float] = None
    height_ft: Optional[float] = None
    pallets: Optional[int] = None
    pieces: Optional[int] = None
    stackable: bool = True
    hazmat: bool = False
    hazmat_class: Optional[str] = None
    temperature_controlled: bool = False
    temperature_min: Optional[float] = None  # Fahrenheit
    temperature_max: Optional[float] = None

    @computed_field
    @property
    def is_heavy(self) -> bool:
        """Load over 40,000 lbs."""
        return self.weight_lbs > 40_000

    @computed_field
    @property
    def is_oversized(self) -> bool:
        """Load exceeds standard dimensions."""
        if self.length_ft and self.length_ft > 53:
            return True
        if self.width_ft and self.width_ft > 8.5:
            return True
        if self.height_ft and self.height_ft > 8.5:
            return True
        return False


class BrokerInfo(BaseModel):
    """Broker/shipper information."""

    company_name: str
    mc_number: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: str
    contact_email: Optional[str] = None

    # Creditworthiness
    credit_rating: Optional[str] = None  # "A", "B", "C", "D", "F"
    credit_score: Optional[int] = None  # 0-100
    payment_terms: PaymentTerms = PaymentTerms.NET_30
    average_days_to_pay: Optional[int] = None
    factoring_approved: bool = False

    # Relationship
    loads_completed_with: int = 0
    average_rate_with: Optional[float] = None
    reliability_score: float = 1.0  # 0-1
    notes: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def is_trusted(self) -> bool:
        """Broker has good payment history."""
        if self.credit_rating and self.credit_rating in ["A", "B"]:
            return True
        if self.loads_completed_with >= 5 and self.reliability_score >= 0.9:
            return True
        return False


class Load(BaseModel):
    """
    Complete load model representing a freight shipment opportunity.
    """

    # Identifiers
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    external_id: Optional[str] = None  # ID from load board
    reference_number: Optional[str] = None
    broker_reference: Optional[str] = None

    # Route Information
    origin: Location
    destination: Location
    loaded_miles: int = Field(..., ge=1)
    deadhead_miles: int = Field(default=0, ge=0)
    route_description: Optional[str] = None

    # Multi-stop support
    stops: list[Location] = Field(default_factory=list)
    is_multi_stop: bool = False

    # Timing
    pickup_window: TimeWindow
    delivery_window: TimeWindow
    posted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Cargo Details
    commodity: str = Field(..., min_length=1)
    commodity_description: Optional[str] = None
    equipment_type: EquipmentType
    equipment_requirements: list[str] = Field(default_factory=list)  # e.g., "liftgate", "pallet jack"
    dimensions: LoadDimensions = Field(default_factory=LoadDimensions)
    special_requirements: list[str] = Field(default_factory=list)

    # Pricing
    rate: float = Field(..., ge=0)
    rate_type: str = "flat"  # flat, per_mile
    fuel_surcharge: float = 0.0
    accessorials: float = 0.0
    detention_rate: Optional[float] = None  # Per hour after free time
    layover_rate: Optional[float] = None

    # Halal Compliance
    halal_status: HalalStatus = HalalStatus.UNKNOWN
    halal_review_notes: Optional[str] = None
    halal_reviewed_at: Optional[datetime] = None
    halal_reviewed_by: Optional[str] = None

    # Broker/Shipper
    broker: BrokerInfo
    is_direct_shipper: bool = False

    # Assignment
    status: LoadStatus = LoadStatus.AVAILABLE
    assigned_carrier_id: Optional[str] = None
    assigned_carrier_name: Optional[str] = None
    assigned_driver_name: Optional[str] = None
    assigned_driver_phone: Optional[str] = None
    rate_confirmation_sent: bool = False
    rate_confirmation_signed: bool = False

    # Tracking
    current_status_note: Optional[str] = None
    tracking_updates: list[dict] = Field(default_factory=list)

    # Timestamps
    booked_at: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Commission tracking
    commission_rate: float = 0.07  # 7% default
    commission_amount: Optional[float] = None
    charity_contribution: Optional[float] = None

    class Config:
        use_enum_values = True

    @computed_field
    @property
    def rate_per_mile(self) -> float:
        """Calculate rate per loaded mile."""
        if self.loaded_miles == 0:
            return 0.0
        return round(self.rate / self.loaded_miles, 2)

    @computed_field
    @property
    def total_miles(self) -> int:
        """Total miles including deadhead."""
        return self.loaded_miles + self.deadhead_miles

    @computed_field
    @property
    def effective_rate_per_mile(self) -> float:
        """Rate per mile including deadhead."""
        if self.total_miles == 0:
            return 0.0
        return round(self.rate / self.total_miles, 2)

    @computed_field
    @property
    def total_rate(self) -> float:
        """Total rate including fuel surcharge and accessorials."""
        return self.rate + self.fuel_surcharge + self.accessorials

    @computed_field
    @property
    def lane(self) -> str:
        """Generate lane string (e.g., 'TX-CA')."""
        return f"{self.origin.state}-{self.destination.state}"

    @computed_field
    @property
    def is_good_rate(self) -> bool:
        """Rate meets our minimum threshold ($2.00/mi)."""
        return self.rate_per_mile >= 2.00

    @computed_field
    @property
    def is_excellent_rate(self) -> bool:
        """Rate exceeds our target ($2.75/mi)."""
        return self.rate_per_mile >= 2.75

    @computed_field
    @property
    def deadhead_ratio(self) -> float:
        """Deadhead as percentage of loaded miles."""
        if self.loaded_miles == 0:
            return 0.0
        return round(self.deadhead_miles / self.loaded_miles, 2)

    @computed_field
    @property
    def is_low_deadhead(self) -> bool:
        """Deadhead less than 15% of loaded miles."""
        return self.deadhead_ratio < 0.15

    def calculate_commission(self) -> float:
        """Calculate commission on this load."""
        self.commission_amount = round(self.rate * self.commission_rate, 2)
        self.charity_contribution = round(self.commission_amount * 0.05, 2)  # 5% to charity
        return self.commission_amount

    def book(self, carrier_id: str, carrier_name: str) -> None:
        """Book this load to a carrier."""
        self.status = LoadStatus.BOOKED
        self.assigned_carrier_id = carrier_id
        self.assigned_carrier_name = carrier_name
        self.booked_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.calculate_commission()

    def dispatch(self, driver_name: str, driver_phone: str) -> None:
        """Dispatch the load to driver."""
        self.status = LoadStatus.DISPATCHED
        self.assigned_driver_name = driver_name
        self.assigned_driver_phone = driver_phone
        self.dispatched_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_picked_up(self) -> None:
        """Mark load as picked up."""
        self.status = LoadStatus.IN_TRANSIT
        self.picked_up_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.add_tracking_update("Picked up at origin")

    def mark_delivered(self) -> None:
        """Mark load as delivered."""
        self.status = LoadStatus.DELIVERED
        self.delivered_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.add_tracking_update("Delivered at destination")

    def reject_haram(self, reason: str) -> None:
        """Reject load as haram."""
        self.status = LoadStatus.REJECTED_HARAM
        self.halal_status = HalalStatus.HARAM
        self.halal_review_notes = reason
        self.halal_reviewed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def reject_rate(self, reason: str) -> None:
        """Reject load due to low rate."""
        self.status = LoadStatus.REJECTED_RATE
        self.current_status_note = reason
        self.updated_at = datetime.utcnow()

    def add_tracking_update(self, message: str, location: Optional[str] = None) -> None:
        """Add a tracking update."""
        update = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "location": location,
        }
        self.tracking_updates.append(update)
        self.current_status_note = message
        self.updated_at = datetime.utcnow()

    def to_embedding_text(self) -> str:
        """Generate text for vector embedding."""
        return (
            f"Load from {self.origin} to {self.destination} | "
            f"{self.loaded_miles} miles | ${self.rate} (${self.rate_per_mile}/mi) | "
            f"{self.commodity} | {self.equipment_type} | "
            f"Pickup: {self.pickup_window.earliest.strftime('%Y-%m-%d')} | "
            f"Delivery: {self.delivery_window.earliest.strftime('%Y-%m-%d')}"
        )

    def to_offer_text(self) -> str:
        """Generate text for offering load to carrier."""
        lines = [
            f"**{self.origin} -> {self.destination}**",
            f"Miles: {self.loaded_miles} loaded + {self.deadhead_miles} DH",
            f"Rate: ${self.rate:,.2f} (${self.rate_per_mile}/mi)",
            f"Equipment: {self.equipment_type}",
            f"Commodity: {self.commodity}",
            f"Weight: {self.dimensions.weight_lbs:,} lbs",
            f"Pickup: {self.pickup_window.earliest.strftime('%m/%d %H:%M')} - {self.pickup_window.latest.strftime('%H:%M')}",
            f"Delivery: {self.delivery_window.earliest.strftime('%m/%d %H:%M')}",
            f"Broker: {self.broker.company_name}",
        ]
        if self.special_requirements:
            lines.append(f"Requirements: {', '.join(self.special_requirements)}")
        return "\n".join(lines)
