# SPEC-001: Hunter Agent MVP

> **Specification-Driven Development (SDD)**
> Write the spec first, then code to match.

---

## Executive Summary

**Objective:** Build the Hunter Agent - an autonomous lead generation system that finds and qualifies truck owner-operators and small fleet carriers.

**Deliverable:** Working Python module that can scrape, score, and store qualified leads.

**Time Budget:** 12 hours of focused development

---

## 12-Hour Execution Plan

### Phase 1: Foundation (Hours 1-3)

| Hour | Task | Deliverable |
|------|------|-------------|
| 1 | Project setup & dependencies | `pyproject.toml`, folder structure |
| 2 | Core data models (Pydantic) | `models/lead.py`, `models/carrier.py` |
| 3 | Database layer (SQLite + ChromaDB) | `db/repository.py`, `db/vectors.py` |

### Phase 2: Hunter Core (Hours 4-7)

| Hour | Task | Deliverable |
|------|------|-------------|
| 4 | FMCSA SAFER scraper | `hunters/fmcsa_hunter.py` |
| 5 | Lead scoring algorithm | `scoring/lead_scorer.py` |
| 6 | Halal commodity filter | `filters/halal_filter.py` |
| 7 | Hunter agent orchestration | `agents/hunter_agent.py` |

### Phase 3: Integration (Hours 8-10)

| Hour | Task | Deliverable |
|------|------|-------------|
| 8 | OpenAI Agent SDK integration | `agents/base_agent.py` |
| 9 | MCP server skeleton | `mcp_servers/hunter_mcp/` |
| 10 | CLI interface | `cli/hunter_cli.py` |

### Phase 4: Testing & Polish (Hours 11-12)

| Hour | Task | Deliverable |
|------|------|-------------|
| 11 | Unit tests | `tests/test_hunter.py` |
| 12 | Integration test & documentation | Working demo, updated docs |

---

## Project Structure

```
al_buraq/
├── pyproject.toml
├── .env.example
├── README.md
├── MISSION.md
├── ARCHITECTURE.md
├── SPEC-001-MVP.md
│
├── src/
│   └── al_buraq/
│       ├── __init__.py
│       ├── config.py              # Settings & environment
│       │
│       ├── models/                # Pydantic data models
│       │   ├── __init__.py
│       │   ├── lead.py
│       │   ├── carrier.py
│       │   ├── load.py
│       │   └── enums.py
│       │
│       ├── db/                    # Database layer
│       │   ├── __init__.py
│       │   ├── repository.py      # SQLite operations
│       │   └── vectors.py         # ChromaDB operations
│       │
│       ├── hunters/               # Lead generation sources
│       │   ├── __init__.py
│       │   ├── base_hunter.py
│       │   ├── fmcsa_hunter.py    # SAFER system scraper
│       │   └── loadboard_hunter.py
│       │
│       ├── filters/               # Ethical filters
│       │   ├── __init__.py
│       │   └── halal_filter.py
│       │
│       ├── scoring/               # Lead qualification
│       │   ├── __init__.py
│       │   └── lead_scorer.py
│       │
│       ├── agents/                # AI agents
│       │   ├── __init__.py
│       │   ├── base_agent.py
│       │   └── hunter_agent.py
│       │
│       └── cli/                   # Command line interface
│           ├── __init__.py
│           └── main.py
│
├── mcp_servers/                   # MCP server implementations
│   └── hunter_mcp/
│       ├── __init__.py
│       └── server.py
│
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_hunter.py
    ├── test_filters.py
    └── test_scoring.py
```

---

## Python Schemas (Pydantic Models)

### Core Enums

```python
# src/al_buraq/models/enums.py
from enum import Enum

class EquipmentType(str, Enum):
    DRY_VAN = "dry_van"
    REEFER = "reefer"
    FLATBED = "flatbed"
    STEP_DECK = "step_deck"
    LOWBOY = "lowboy"
    TANKER = "tanker"
    HOPPER = "hopper"
    CAR_HAULER = "car_hauler"
    POWER_ONLY = "power_only"

class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    REJECTED = "rejected"
    DO_NOT_CONTACT = "do_not_contact"

class LeadSource(str, Enum):
    FMCSA_SAFER = "fmcsa_safer"
    DAT_LOADBOARD = "dat_loadboard"
    TRUCKSTOP = "truckstop"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    REFERRAL = "referral"
    INBOUND = "inbound"

class CarrierStatus(str, Enum):
    PROSPECT = "prospect"
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PAUSED = "paused"
    CHURNED = "churned"
    BLACKLISTED = "blacklisted"

class LoadStatus(str, Enum):
    AVAILABLE = "available"
    PENDING = "pending"
    BOOKED = "booked"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REJECTED_HARAM = "rejected_haram"

class HalalStatus(str, Enum):
    HALAL = "halal"
    HARAM = "haram"
    UNKNOWN = "unknown"  # Requires manual review
```

### Lead Model

```python
# src/al_buraq/models/lead.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re

from .enums import EquipmentType, LeadStatus, LeadSource

class ContactInfo(BaseModel):
    """Contact information for a lead."""
    phone_primary: str = Field(..., description="Primary phone number")
    phone_secondary: Optional[str] = None
    email: Optional[str] = None
    preferred_contact_method: str = "phone"
    best_time_to_call: Optional[str] = None  # e.g., "morning", "afternoon"
    timezone: str = "America/Chicago"  # Default to Central

    @field_validator("phone_primary", "phone_secondary")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Strip non-digits
        digits = re.sub(r"\D", "", v)
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        raise ValueError(f"Invalid phone number: {v}")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", v):
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

    @property
    def authority_age_days(self) -> int:
        """Calculate days since authority was granted."""
        if self.authority_granted_date is None:
            return 0
        return (datetime.utcnow() - self.authority_granted_date).days

    @field_validator("mc_number")
    @classmethod
    def validate_mc(cls, v: str) -> str:
        # Remove 'MC' prefix if present, ensure numeric
        clean = re.sub(r"[^\d]", "", v)
        if not clean:
            raise ValueError(f"Invalid MC number: {v}")
        return clean

    @field_validator("dot_number")
    @classmethod
    def validate_dot(cls, v: str) -> str:
        clean = re.sub(r"[^\d]", "", v)
        if not clean:
            raise ValueError(f"Invalid DOT number: {v}")
        return clean

class InsuranceInfo(BaseModel):
    """Insurance coverage information."""
    liability_coverage: int = Field(..., ge=0, description="Liability coverage in dollars")
    cargo_coverage: int = Field(..., ge=0, description="Cargo coverage in dollars")
    insurance_carrier: Optional[str] = None
    policy_expiration: Optional[datetime] = None
    insurance_verified: bool = False
    verification_date: Optional[datetime] = None

    @property
    def meets_minimum_requirements(self) -> bool:
        """Check if insurance meets our minimum requirements."""
        return (
            self.liability_coverage >= 1_000_000 and
            self.cargo_coverage >= 100_000
        )

class FleetInfo(BaseModel):
    """Fleet and equipment information."""
    truck_count: int = Field(..., ge=1, description="Number of trucks")
    driver_count: int = Field(..., ge=1, description="Number of drivers")
    equipment_types: List[EquipmentType] = Field(default_factory=list)
    operating_states: List[str] = Field(default_factory=list)  # State abbreviations
    preferred_lanes: List[str] = Field(default_factory=list)  # e.g., "TX-CA", "IL-FL"
    home_base_city: Optional[str] = None
    home_base_state: Optional[str] = None

class SafetyInfo(BaseModel):
    """Safety and compliance information."""
    csa_score: Optional[float] = None  # 0-100, lower is better
    out_of_service_rate: Optional[float] = None
    crash_indicator: Optional[str] = None  # "None", "Alert", "Warning"
    has_hazmat: bool = False
    has_tanker: bool = False
    last_inspection_date: Optional[datetime] = None

class Lead(BaseModel):
    """
    Complete lead model for a potential carrier partner.
    This is the primary output of the Hunter Agent.
    """
    # Identifiers
    id: Optional[str] = None  # UUID, set by database

    # Core Information
    company_name: str = Field(..., min_length=1)
    dba_name: Optional[str] = None
    owner_name: Optional[str] = None

    # Nested Models
    contact: ContactInfo
    authority: AuthorityInfo
    insurance: InsuranceInfo
    fleet: FleetInfo
    safety: Optional[SafetyInfo] = None

    # Lead Management
    status: LeadStatus = LeadStatus.NEW
    source: LeadSource
    lead_score: float = Field(default=0.0, ge=0.0, le=1.0)
    score_breakdown: dict = Field(default_factory=dict)

    # Qualification
    is_qualified: bool = False
    disqualification_reason: Optional[str] = None

    # Communication History
    contact_attempts: int = 0
    last_contact_date: Optional[datetime] = None
    next_follow_up_date: Optional[datetime] = None
    notes: List[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    scraped_at: Optional[datetime] = None

    class Config:
        use_enum_values = True

    def to_embedding_text(self) -> str:
        """Generate text representation for vector embedding."""
        parts = [
            f"Company: {self.company_name}",
            f"MC: {self.authority.mc_number}",
            f"Trucks: {self.fleet.truck_count}",
            f"Equipment: {', '.join(self.fleet.equipment_types)}",
            f"States: {', '.join(self.fleet.operating_states)}",
            f"Lanes: {', '.join(self.fleet.preferred_lanes)}"
        ]
        return " | ".join(parts)
```

### Carrier Model

```python
# src/al_buraq/models/carrier.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from .enums import CarrierStatus, EquipmentType
from .lead import AuthorityInfo, InsuranceInfo, FleetInfo, SafetyInfo, ContactInfo

class DispatcherAgreement(BaseModel):
    """Dispatcher agreement details."""
    signed_date: datetime
    commission_rate: float = Field(..., ge=0.05, le=0.15)  # 5-15%
    agreement_type: str = "standard"  # standard, premium, trial
    auto_renew: bool = True
    termination_notice_days: int = 30
    exclusive: bool = False

class CarrierPreferences(BaseModel):
    """Carrier dispatch preferences."""
    min_rate_per_mile: float = Field(default=2.00, ge=1.50)
    max_deadhead_miles: int = Field(default=150, ge=0)
    preferred_load_types: List[str] = Field(default_factory=list)
    avoid_states: List[str] = Field(default_factory=list)
    avoid_cities: List[str] = Field(default_factory=list)
    max_weight_lbs: Optional[int] = None
    team_available: bool = False
    hazmat_willing: bool = False
    weekend_available: bool = False

class CarrierPerformance(BaseModel):
    """Carrier performance metrics."""
    total_loads_completed: int = 0
    on_time_pickup_rate: float = 1.0  # 0-1
    on_time_delivery_rate: float = 1.0  # 0-1
    load_acceptance_rate: float = 1.0  # 0-1
    average_rating: float = 5.0  # 1-5
    total_revenue_generated: float = 0.0
    commission_earned: float = 0.0
    last_load_date: Optional[datetime] = None

class Carrier(BaseModel):
    """
    Full carrier model for an active dispatch partner.
    Extends lead information with operational data.
    """
    # Identifiers
    id: Optional[str] = None
    lead_id: Optional[str] = None  # Reference to original lead

    # Core Information
    company_name: str
    dba_name: Optional[str] = None
    owner_name: str

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

    # Availability
    current_location_city: Optional[str] = None
    current_location_state: Optional[str] = None
    available_date: Optional[datetime] = None
    is_available: bool = False

    # Timestamps
    onboarded_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True

    @classmethod
    def from_lead(cls, lead: "Lead", agreement: DispatcherAgreement) -> "Carrier":
        """Convert a qualified lead to a carrier."""
        return cls(
            lead_id=lead.id,
            company_name=lead.company_name,
            dba_name=lead.dba_name,
            owner_name=lead.owner_name or "Unknown",
            contact=lead.contact,
            authority=lead.authority,
            insurance=lead.insurance,
            fleet=lead.fleet,
            safety=lead.safety,
            status=CarrierStatus.ONBOARDING,
            agreement=agreement,
            onboarded_at=datetime.utcnow()
        )
```

### Load Model

```python
# src/al_buraq/models/load.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, computed_field

from .enums import LoadStatus, EquipmentType, HalalStatus

class Location(BaseModel):
    """Geographic location for pickup/delivery."""
    city: str
    state: str  # 2-letter abbreviation
    zip_code: Optional[str] = None
    address: Optional[str] = None
    facility_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def __str__(self) -> str:
        return f"{self.city}, {self.state}"

class TimeWindow(BaseModel):
    """Pickup or delivery time window."""
    earliest: datetime
    latest: datetime
    appointment_required: bool = False
    appointment_time: Optional[datetime] = None

class LoadDimensions(BaseModel):
    """Physical dimensions and weight of the load."""
    weight_lbs: int = Field(..., ge=0)
    length_ft: Optional[float] = None
    width_ft: Optional[float] = None
    height_ft: Optional[float] = None
    pallets: Optional[int] = None
    pieces: Optional[int] = None
    stackable: bool = True

class BrokerInfo(BaseModel):
    """Broker/shipper information."""
    company_name: str
    mc_number: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: str
    contact_email: Optional[str] = None
    credit_rating: Optional[str] = None  # e.g., "A", "B", "C"
    average_days_to_pay: Optional[int] = None

class Load(BaseModel):
    """
    Complete load model representing a freight shipment opportunity.
    """
    # Identifiers
    id: Optional[str] = None
    external_id: Optional[str] = None  # ID from load board
    reference_number: Optional[str] = None

    # Route Information
    origin: Location
    destination: Location
    loaded_miles: int = Field(..., ge=1)
    deadhead_miles: int = Field(default=0, ge=0)

    # Timing
    pickup_window: TimeWindow
    delivery_window: TimeWindow

    # Cargo Details
    commodity: str = Field(..., min_length=1)
    commodity_description: Optional[str] = None
    equipment_type: EquipmentType
    dimensions: LoadDimensions
    special_requirements: List[str] = Field(default_factory=list)

    # Pricing
    rate: float = Field(..., ge=0)
    rate_type: str = "flat"  # flat, per_mile
    fuel_surcharge: float = 0.0
    accessorials: float = 0.0

    # Halal Compliance
    halal_status: HalalStatus = HalalStatus.UNKNOWN
    halal_review_notes: Optional[str] = None

    # Broker/Shipper
    broker: BrokerInfo

    # Assignment
    status: LoadStatus = LoadStatus.AVAILABLE
    assigned_carrier_id: Optional[str] = None
    assigned_driver_name: Optional[str] = None

    # Timestamps
    posted_at: Optional[datetime] = None
    booked_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

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
    def lane(self) -> str:
        """Generate lane string (e.g., 'TX-CA')."""
        return f"{self.origin.state}-{self.destination.state}"

    def to_embedding_text(self) -> str:
        """Generate text for vector embedding."""
        return (
            f"Load from {self.origin} to {self.destination} | "
            f"{self.loaded_miles} miles | ${self.rate} ({self.rate_per_mile}/mi) | "
            f"{self.commodity} | {self.equipment_type} | "
            f"Pickup: {self.pickup_window.earliest.date()}"
        )
```

---

## Halal Filter Implementation

```python
# src/al_buraq/filters/halal_filter.py
from typing import Tuple
from ..models.load import Load
from ..models.enums import HalalStatus

# Comprehensive haram keyword list
HARAM_KEYWORDS = {
    # Alcohol
    "alcohol", "beer", "wine", "liquor", "spirits", "vodka", "whiskey",
    "whisky", "rum", "gin", "tequila", "brandy", "bourbon", "scotch",
    "champagne", "malt beverage", "hard seltzer", "cider",

    # Pork
    "pork", "bacon", "ham", "swine", "pig", "sausage", "pepperoni",
    "prosciutto", "salami", "chorizo", "lard", "gelatin",

    # Tobacco & Drugs
    "tobacco", "cigarette", "cigar", "vape", "e-cigarette", "nicotine",
    "cannabis", "marijuana", "weed", "thc", "cbd", "hemp",

    # Gambling
    "gambling", "casino", "slot machine", "lottery", "betting",

    # Adult Content
    "adult", "xxx", "pornography", "erotic",

    # Weapons (civilian sales)
    "ammunition", "ammo", "firearms", "guns", "rifles", "pistols"
}

# Keywords that require manual review
REVIEW_KEYWORDS = {
    "meat", "sausage", "hot dog", "deli", "processed meat",
    "gelatin", "enzyme", "animal product"
}

# Explicitly halal commodities
HALAL_COMMODITIES = {
    "produce", "vegetables", "fruits", "grains", "rice", "wheat",
    "electronics", "furniture", "appliances", "machinery", "equipment",
    "paper", "plastic", "steel", "lumber", "building materials",
    "automotive parts", "tires", "medical supplies", "pharmaceuticals",
    "clothing", "textiles", "toys", "books"
}

class HalalFilter:
    """
    Filters loads based on Islamic dietary and ethical guidelines.
    """

    def __init__(self):
        self.haram_keywords = HARAM_KEYWORDS
        self.review_keywords = REVIEW_KEYWORDS
        self.halal_commodities = HALAL_COMMODITIES

    def check_load(self, load: Load) -> Tuple[HalalStatus, str]:
        """
        Check if a load's commodity is halal.

        Returns:
            Tuple of (HalalStatus, reason_string)
        """
        commodity_lower = load.commodity.lower()
        description_lower = (load.commodity_description or "").lower()
        combined_text = f"{commodity_lower} {description_lower}"

        # Check for explicit haram keywords
        for keyword in self.haram_keywords:
            if keyword in combined_text:
                return (
                    HalalStatus.HARAM,
                    f"Haram commodity detected: '{keyword}' found in '{load.commodity}'"
                )

        # Check for keywords requiring review
        for keyword in self.review_keywords:
            if keyword in combined_text:
                return (
                    HalalStatus.UNKNOWN,
                    f"Manual review required: '{keyword}' found - verify halal compliance"
                )

        # Check if explicitly halal
        for halal_word in self.halal_commodities:
            if halal_word in combined_text:
                return (
                    HalalStatus.HALAL,
                    f"Commodity verified halal: matches '{halal_word}'"
                )

        # Default to unknown for unrecognized commodities
        return (
            HalalStatus.UNKNOWN,
            f"Unrecognized commodity: '{load.commodity}' - manual verification recommended"
        )

    def filter_loads(self, loads: list[Load]) -> dict[str, list[Load]]:
        """
        Filter a list of loads into halal/haram/unknown categories.
        """
        result = {
            "halal": [],
            "haram": [],
            "review_needed": []
        }

        for load in loads:
            status, reason = self.check_load(load)
            load.halal_status = status
            load.halal_review_notes = reason

            if status == HalalStatus.HALAL:
                result["halal"].append(load)
            elif status == HalalStatus.HARAM:
                result["haram"].append(load)
            else:
                result["review_needed"].append(load)

        return result
```

---

## Lead Scoring Algorithm

```python
# src/al_buraq/scoring/lead_scorer.py
from dataclasses import dataclass
from typing import Dict
from ..models.lead import Lead

@dataclass
class ScoringWeights:
    """Configurable weights for lead scoring."""
    authority_age: float = 0.15      # Newer = potentially more receptive
    fleet_size: float = 0.20         # Sweet spot: 1-10 trucks
    insurance: float = 0.15          # Meets minimums
    safety: float = 0.15             # Good safety record
    equipment_match: float = 0.15    # Equipment we can dispatch
    location: float = 0.10           # In our operating area
    contact_quality: float = 0.10    # Has good contact info

class LeadScorer:
    """
    Scores leads based on likelihood of conversion and fit.
    Score range: 0.0 (worst) to 1.0 (best)
    """

    # Target equipment types (what we can dispatch)
    TARGET_EQUIPMENT = {"dry_van", "reefer", "flatbed", "step_deck"}

    # Target operating states
    TARGET_STATES = {
        "TX", "CA", "FL", "IL", "GA", "OH", "PA", "NY", "NC", "TN",
        "AZ", "NJ", "MI", "IN", "MO", "WI", "MN", "CO", "AL", "LA"
    }

    def __init__(self, weights: ScoringWeights = None):
        self.weights = weights or ScoringWeights()

    def score_lead(self, lead: Lead) -> float:
        """
        Calculate overall lead score and breakdown.
        """
        breakdown = {}

        # Authority Age Score (0-1)
        # New authorities (< 180 days) often need dispatchers
        age_days = lead.authority.authority_age_days
        if age_days < 30:
            breakdown["authority_age"] = 1.0  # Brand new - very receptive
        elif age_days < 90:
            breakdown["authority_age"] = 0.9
        elif age_days < 180:
            breakdown["authority_age"] = 0.8
        elif age_days < 365:
            breakdown["authority_age"] = 0.6
        elif age_days < 730:
            breakdown["authority_age"] = 0.4
        else:
            breakdown["authority_age"] = 0.2  # Established - less likely to switch

        # Fleet Size Score (0-1)
        # Sweet spot: 1-5 trucks (owner-operators)
        trucks = lead.fleet.truck_count
        if 1 <= trucks <= 3:
            breakdown["fleet_size"] = 1.0  # Perfect target
        elif 4 <= trucks <= 5:
            breakdown["fleet_size"] = 0.9
        elif 6 <= trucks <= 10:
            breakdown["fleet_size"] = 0.7
        elif 11 <= trucks <= 20:
            breakdown["fleet_size"] = 0.5
        else:
            breakdown["fleet_size"] = 0.3  # Large fleets usually have in-house

        # Insurance Score (0-1)
        if lead.insurance.meets_minimum_requirements:
            if lead.insurance.insurance_verified:
                breakdown["insurance"] = 1.0
            else:
                breakdown["insurance"] = 0.8
        else:
            breakdown["insurance"] = 0.0  # Disqualifying

        # Safety Score (0-1)
        if lead.safety:
            csa = lead.safety.csa_score
            if csa is None:
                breakdown["safety"] = 0.5  # Unknown
            elif csa < 50:
                breakdown["safety"] = 1.0  # Excellent
            elif csa < 70:
                breakdown["safety"] = 0.7  # Good
            elif csa < 85:
                breakdown["safety"] = 0.4  # Concerning
            else:
                breakdown["safety"] = 0.1  # Poor - risky
        else:
            breakdown["safety"] = 0.5  # No data

        # Equipment Match Score (0-1)
        equipment_set = set(lead.fleet.equipment_types)
        matching = equipment_set & self.TARGET_EQUIPMENT
        if matching:
            breakdown["equipment_match"] = len(matching) / len(self.TARGET_EQUIPMENT)
        else:
            breakdown["equipment_match"] = 0.0

        # Location Score (0-1)
        states_set = set(lead.fleet.operating_states)
        matching_states = states_set & self.TARGET_STATES
        if matching_states:
            breakdown["location"] = min(1.0, len(matching_states) / 5)
        elif lead.fleet.home_base_state in self.TARGET_STATES:
            breakdown["location"] = 0.5
        else:
            breakdown["location"] = 0.2

        # Contact Quality Score (0-1)
        contact_score = 0.0
        if lead.contact.phone_primary:
            contact_score += 0.5
        if lead.contact.email:
            contact_score += 0.3
        if lead.contact.phone_secondary:
            contact_score += 0.2
        breakdown["contact_quality"] = contact_score

        # Calculate weighted total
        total_score = (
            breakdown["authority_age"] * self.weights.authority_age +
            breakdown["fleet_size"] * self.weights.fleet_size +
            breakdown["insurance"] * self.weights.insurance +
            breakdown["safety"] * self.weights.safety +
            breakdown["equipment_match"] * self.weights.equipment_match +
            breakdown["location"] * self.weights.location +
            breakdown["contact_quality"] * self.weights.contact_quality
        )

        # Store breakdown in lead
        lead.score_breakdown = breakdown
        lead.lead_score = round(total_score, 3)

        # Determine qualification
        lead.is_qualified = (
            total_score >= 0.6 and
            breakdown["insurance"] > 0 and
            breakdown["equipment_match"] > 0
        )

        if not lead.is_qualified:
            if breakdown["insurance"] == 0:
                lead.disqualification_reason = "Insurance does not meet minimum requirements"
            elif breakdown["equipment_match"] == 0:
                lead.disqualification_reason = "No matching equipment types"
            else:
                lead.disqualification_reason = f"Lead score {total_score:.2f} below threshold 0.6"

        return total_score

    def rank_leads(self, leads: list[Lead]) -> list[Lead]:
        """Score and rank leads by score descending."""
        for lead in leads:
            self.score_lead(lead)
        return sorted(leads, key=lambda x: x.lead_score, reverse=True)
```

---

## Configuration

```python
# src/al_buraq/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application configuration from environment variables."""

    # Application
    APP_NAME: str = "Al-Buraq Dispatch"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # AI Providers
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: Optional[str] = None

    # Database
    DATABASE_URL: str = "sqlite:///data/alburaq.db"
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION: str = "alburaq"

    # Communication (for future use)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # Business Rules
    MIN_RATE_PER_MILE: float = 2.00
    TARGET_RATE_PER_MILE: float = 2.75
    COMMISSION_RATE: float = 0.07
    CHARITY_PERCENTAGE: float = 0.05

    # Lead Scoring Thresholds
    LEAD_QUALIFICATION_THRESHOLD: float = 0.6

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Global settings instance
settings = Settings()
```

---

## Success Criteria (MVP)

### Must Have (Hour 12 Checkpoint)
- [ ] All Pydantic models validate correctly
- [ ] Lead scoring produces consistent results
- [ ] Halal filter correctly classifies test commodities
- [ ] Can persist leads to SQLite database
- [ ] Can store/retrieve lead embeddings from ChromaDB
- [ ] CLI can run a mock hunt and display results

### Nice to Have
- [ ] FMCSA SAFER web scraping working
- [ ] Basic unit test coverage (>60%)
- [ ] MCP server responds to tool calls

### Future (Post-MVP)
- [ ] DAT/Truckstop API integration
- [ ] Voice calling with Twilio/Bland.ai
- [ ] Sales Agent implementation
- [ ] Dispatch Agent implementation

---

## Dependencies

```toml
# pyproject.toml
[project]
name = "al-buraq"
version = "0.1.0"
description = "Ethical AI Dispatch System"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "openai>=1.0",
    "anthropic>=0.18",
    "chromadb>=0.4",
    "sqlalchemy>=2.0",
    "httpx>=0.25",
    "beautifulsoup4>=4.12",
    "python-dotenv>=1.0",
    "typer>=0.9",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "ruff>=0.1",
    "mypy>=1.0",
]
```

---

## Next Steps After MVP

1. **SPEC-002**: Sales Agent - Outbound calling and email sequences
2. **SPEC-003**: Dispatch Agent - Load matching and booking
3. **SPEC-004**: MCP Server Suite - Full tool implementations
4. **SPEC-005**: Dashboard - Real-time monitoring and Barakah Meter

---

**Bismillah. Let's build.**

---

**Version:** 1.0.0
**Created:** 2025-01-21
**Status:** READY FOR IMPLEMENTATION
