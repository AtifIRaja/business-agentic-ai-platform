"""SQLite repository for persistent storage."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from functools import lru_cache

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from ..config import settings
from ..models import Lead, Carrier, Load
from ..models.enums import LeadStatus, CarrierStatus, LoadStatus

Base = declarative_base()


# =============================================================================
# SQLAlchemy Models (Database Tables)
# =============================================================================

class LeadRecord(Base):
    """SQLAlchemy model for leads table."""

    __tablename__ = "leads"

    id = Column(String(36), primary_key=True)
    company_name = Column(String(255), nullable=False, index=True)
    dba_name = Column(String(255))
    owner_name = Column(String(255))
    legal_name = Column(String(255))

    # Authority
    mc_number = Column(String(20), nullable=False, unique=True, index=True)
    dot_number = Column(String(20), nullable=False, index=True)
    authority_status = Column(String(20), default="ACTIVE")
    authority_granted_date = Column(DateTime)

    # Contact
    phone_primary = Column(String(20), nullable=False)
    phone_secondary = Column(String(20))
    email = Column(String(255))
    timezone = Column(String(50), default="America/Chicago")

    # Fleet
    truck_count = Column(Integer, default=1)
    driver_count = Column(Integer, default=1)
    equipment_types = Column(Text)  # JSON array
    operating_states = Column(Text)  # JSON array
    preferred_lanes = Column(Text)  # JSON array
    home_base_city = Column(String(100))
    home_base_state = Column(String(2))

    # Insurance
    liability_coverage = Column(Integer, default=0)
    cargo_coverage = Column(Integer, default=0)
    insurance_verified = Column(Boolean, default=False)

    # Lead Management
    status = Column(String(20), default="new", index=True)
    source = Column(String(50), nullable=False, index=True)
    lead_score = Column(Float, default=0.0, index=True)
    score_breakdown = Column(Text)  # JSON object
    is_qualified = Column(Boolean, default=False, index=True)
    disqualification_reason = Column(Text)

    # Verification (Investigator Agent)
    verification_status = Column(String(20), default="pending", index=True)
    social_verified = Column(Boolean, default=False, index=True)
    high_intent = Column(Boolean, default=False, index=True)
    linkedin_url = Column(String(500))
    facebook_url = Column(String(500))
    instagram_url = Column(String(500))
    website_url = Column(String(500))
    search_snippets = Column(Text)  # JSON array
    verified_at = Column(DateTime)

    # Communication
    contact_attempts = Column(Integer, default=0)
    last_contact_date = Column(DateTime)
    next_follow_up_date = Column(DateTime, index=True)
    notes = Column(Text)  # JSON array
    tags = Column(Text)  # JSON array

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scraped_at = Column(DateTime)
    qualified_at = Column(DateTime)
    converted_at = Column(DateTime)

    # Full JSON blob for complete model
    full_data = Column(Text)

    __table_args__ = (
        Index("ix_leads_score_status", "lead_score", "status"),
        Index("ix_leads_state_equipment", "home_base_state", "equipment_types"),
    )


class CarrierRecord(Base):
    """SQLAlchemy model for carriers table."""

    __tablename__ = "carriers"

    id = Column(String(36), primary_key=True)
    lead_id = Column(String(36), index=True)
    company_name = Column(String(255), nullable=False, index=True)
    owner_name = Column(String(255), nullable=False)

    # Authority
    mc_number = Column(String(20), nullable=False, unique=True, index=True)
    dot_number = Column(String(20), nullable=False, index=True)

    # Contact
    phone_primary = Column(String(20), nullable=False)
    email = Column(String(255))

    # Fleet
    truck_count = Column(Integer, default=1)
    equipment_types = Column(Text)  # JSON array
    home_base_state = Column(String(2), index=True)

    # Status
    status = Column(String(20), default="prospect", index=True)
    is_available = Column(Boolean, default=False, index=True)
    current_location_state = Column(String(2), index=True)

    # Performance
    total_loads_completed = Column(Integer, default=0)
    on_time_delivery_rate = Column(Float, default=1.0)
    reliability_score = Column(Float, default=1.0)
    total_revenue_generated = Column(Float, default=0.0)

    # Agreement
    commission_rate = Column(Float, default=0.07)
    agreement_signed = Column(Boolean, default=False)

    # Timestamps
    onboarded_at = Column(DateTime)
    last_active_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Full JSON blob
    full_data = Column(Text)

    __table_args__ = (
        Index("ix_carriers_available_state", "is_available", "current_location_state"),
    )


class LoadRecord(Base):
    """SQLAlchemy model for loads table."""

    __tablename__ = "loads"

    id = Column(String(36), primary_key=True)
    external_id = Column(String(100), index=True)
    reference_number = Column(String(100))

    # Route
    origin_city = Column(String(100), nullable=False)
    origin_state = Column(String(2), nullable=False, index=True)
    destination_city = Column(String(100), nullable=False)
    destination_state = Column(String(2), nullable=False, index=True)
    lane = Column(String(10), index=True)  # e.g., "TX-CA"
    loaded_miles = Column(Integer, nullable=False)
    deadhead_miles = Column(Integer, default=0)

    # Timing
    pickup_date = Column(DateTime, nullable=False, index=True)
    delivery_date = Column(DateTime, nullable=False)

    # Cargo
    commodity = Column(String(255), nullable=False)
    equipment_type = Column(String(50), nullable=False, index=True)
    weight_lbs = Column(Integer, default=0)

    # Pricing
    rate = Column(Float, nullable=False)
    rate_per_mile = Column(Float, nullable=False, index=True)

    # Halal
    halal_status = Column(String(20), default="unknown", index=True)
    halal_review_notes = Column(Text)

    # Broker
    broker_name = Column(String(255), nullable=False)
    broker_mc = Column(String(20))
    broker_phone = Column(String(20))

    # Assignment
    status = Column(String(20), default="available", index=True)
    assigned_carrier_id = Column(String(36), index=True)
    assigned_carrier_name = Column(String(255))

    # Commission
    commission_rate = Column(Float, default=0.07)
    commission_amount = Column(Float)
    charity_contribution = Column(Float)

    # Timestamps
    posted_at = Column(DateTime)
    booked_at = Column(DateTime)
    picked_up_at = Column(DateTime)
    delivered_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Full JSON blob
    full_data = Column(Text)

    __table_args__ = (
        Index("ix_loads_lane_rate", "lane", "rate_per_mile"),
        Index("ix_loads_origin_dest", "origin_state", "destination_state"),
    )


# =============================================================================
# Repository Class
# =============================================================================

class Repository:
    """Repository for database operations."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.DATABASE_URL

        # Ensure data directory exists
        if self.database_url.startswith("sqlite:///"):
            db_path = Path(self.database_url.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(
            self.database_url,
            echo=settings.DEBUG,
            connect_args={"check_same_thread": False} if "sqlite" in self.database_url else {},
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

    def init_db(self) -> None:
        """Create all tables."""
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    # =========================================================================
    # Lead Operations
    # =========================================================================

    def save_lead(self, lead: Lead) -> Lead:
        """Save or update a lead."""
        with self.get_session() as session:
            record = session.query(LeadRecord).filter_by(id=lead.id).first()

            if record is None:
                record = LeadRecord(id=lead.id)
                session.add(record)

            # Map Lead to LeadRecord
            record.company_name = lead.company_name
            record.dba_name = lead.dba_name
            record.owner_name = lead.owner_name
            record.legal_name = lead.legal_name
            record.mc_number = lead.authority.mc_number
            record.dot_number = lead.authority.dot_number
            record.authority_status = lead.authority.authority_status
            record.authority_granted_date = lead.authority.authority_granted_date
            record.phone_primary = lead.contact.phone_primary
            record.phone_secondary = lead.contact.phone_secondary
            record.email = lead.contact.email
            record.timezone = lead.contact.timezone
            record.truck_count = lead.fleet.truck_count
            record.driver_count = lead.fleet.driver_count
            record.equipment_types = json.dumps([str(e) for e in lead.fleet.equipment_types])
            record.operating_states = json.dumps(lead.fleet.operating_states)
            record.preferred_lanes = json.dumps(lead.fleet.preferred_lanes)
            record.home_base_city = lead.fleet.home_base_city
            record.home_base_state = lead.fleet.home_base_state
            record.liability_coverage = lead.insurance.liability_coverage
            record.cargo_coverage = lead.insurance.cargo_coverage
            record.insurance_verified = lead.insurance.insurance_verified
            record.status = lead.status
            record.source = lead.source
            record.lead_score = lead.lead_score
            record.score_breakdown = json.dumps(lead.score_breakdown)
            record.is_qualified = lead.is_qualified
            record.disqualification_reason = lead.disqualification_reason
            record.verification_status = lead.verification_status
            record.social_verified = lead.social_verified
            record.high_intent = lead.high_intent
            record.linkedin_url = lead.linkedin_url
            record.facebook_url = lead.facebook_url
            record.instagram_url = lead.instagram_url
            record.website_url = lead.website_url
            record.search_snippets = json.dumps(lead.search_snippets)
            record.verified_at = lead.verified_at
            record.contact_attempts = lead.contact_attempts
            record.last_contact_date = lead.last_contact_date
            record.next_follow_up_date = lead.next_follow_up_date
            record.notes = json.dumps(lead.notes)
            record.tags = json.dumps(lead.tags)
            record.created_at = lead.created_at
            record.updated_at = lead.updated_at
            record.scraped_at = lead.scraped_at
            record.qualified_at = lead.qualified_at
            record.converted_at = lead.converted_at
            record.full_data = lead.model_dump_json()

            session.commit()
            return lead

    def get_lead(self, lead_id: str) -> Optional[Lead]:
        """Get a lead by ID."""
        with self.get_session() as session:
            record = session.query(LeadRecord).filter_by(id=lead_id).first()
            if record and record.full_data:
                return Lead.model_validate_json(record.full_data)
            return None

    def get_lead_by_mc(self, mc_number: str) -> Optional[Lead]:
        """Get a lead by MC number."""
        with self.get_session() as session:
            record = session.query(LeadRecord).filter_by(mc_number=mc_number).first()
            if record and record.full_data:
                return Lead.model_validate_json(record.full_data)
            return None

    def list_leads(
        self,
        status: Optional[LeadStatus] = None,
        is_qualified: Optional[bool] = None,
        min_score: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Lead]:
        """List leads with optional filters."""
        with self.get_session() as session:
            query = session.query(LeadRecord)

            if status:
                query = query.filter(LeadRecord.status == status)
            if is_qualified is not None:
                query = query.filter(LeadRecord.is_qualified == is_qualified)
            if min_score is not None:
                query = query.filter(LeadRecord.lead_score >= min_score)

            query = query.order_by(LeadRecord.lead_score.desc())
            query = query.offset(offset).limit(limit)

            leads = []
            for record in query.all():
                if record.full_data:
                    leads.append(Lead.model_validate_json(record.full_data))
            return leads

    def count_leads(self, status: Optional[LeadStatus] = None) -> int:
        """Count leads with optional status filter."""
        with self.get_session() as session:
            query = session.query(LeadRecord)
            if status:
                query = query.filter(LeadRecord.status == status)
            return query.count()

    def delete_lead(self, lead_id: str) -> bool:
        """Delete a lead."""
        with self.get_session() as session:
            record = session.query(LeadRecord).filter_by(id=lead_id).first()
            if record:
                session.delete(record)
                session.commit()
                return True
            return False

    def update_lead(self, lead: Lead) -> Lead:
        """Update an existing lead (alias for save_lead)."""
        return self.save_lead(lead)

    def get_leads_for_verification(self, limit: int = 5) -> list[Lead]:
        """Get leads pending verification."""
        with self.get_session() as session:
            query = session.query(LeadRecord).filter(
                LeadRecord.verification_status == "pending",
                LeadRecord.is_qualified == True,
            ).order_by(
                LeadRecord.lead_score.desc()
            ).limit(limit)

            leads = []
            for record in query.all():
                if record.full_data:
                    leads.append(Lead.model_validate_json(record.full_data))
            return leads

    def get_verified_leads(
        self,
        social_verified: Optional[bool] = None,
        high_intent: Optional[bool] = None,
        limit: int = 50,
    ) -> list[Lead]:
        """Get verified leads with optional filters."""
        with self.get_session() as session:
            query = session.query(LeadRecord).filter(
                LeadRecord.verification_status == "verified",
            )

            if social_verified is not None:
                query = query.filter(LeadRecord.social_verified == social_verified)
            if high_intent is not None:
                query = query.filter(LeadRecord.high_intent == high_intent)

            query = query.order_by(LeadRecord.lead_score.desc()).limit(limit)

            leads = []
            for record in query.all():
                if record.full_data:
                    leads.append(Lead.model_validate_json(record.full_data))
            return leads

    def get_verification_stats(self) -> dict:
        """Get verification statistics."""
        with self.get_session() as session:
            return {
                "pending": session.query(LeadRecord).filter_by(verification_status="pending").count(),
                "verified": session.query(LeadRecord).filter_by(verification_status="verified").count(),
                "social_verified": session.query(LeadRecord).filter_by(social_verified=True).count(),
                "high_intent": session.query(LeadRecord).filter_by(high_intent=True).count(),
            }

    # =========================================================================
    # Carrier Operations
    # =========================================================================

    def save_carrier(self, carrier: Carrier) -> Carrier:
        """Save or update a carrier."""
        with self.get_session() as session:
            record = session.query(CarrierRecord).filter_by(id=carrier.id).first()

            if record is None:
                record = CarrierRecord(id=carrier.id)
                session.add(record)

            record.lead_id = carrier.lead_id
            record.company_name = carrier.company_name
            record.owner_name = carrier.owner_name
            record.mc_number = carrier.authority.mc_number
            record.dot_number = carrier.authority.dot_number
            record.phone_primary = carrier.contact.phone_primary
            record.email = carrier.contact.email
            record.truck_count = carrier.fleet.truck_count
            record.equipment_types = json.dumps([str(e) for e in carrier.fleet.equipment_types])
            record.home_base_state = carrier.fleet.home_base_state
            record.status = carrier.status
            record.is_available = carrier.is_available
            record.current_location_state = carrier.current_location_state
            record.total_loads_completed = carrier.performance.total_loads_completed
            record.on_time_delivery_rate = carrier.performance.on_time_delivery_rate
            record.reliability_score = carrier.performance.reliability_score
            record.total_revenue_generated = carrier.performance.total_revenue_generated
            record.commission_rate = carrier.agreement.commission_rate if carrier.agreement else 0.07
            record.agreement_signed = carrier.agreement is not None
            record.onboarded_at = carrier.onboarded_at
            record.last_active_at = carrier.last_active_at
            record.created_at = carrier.created_at
            record.updated_at = carrier.updated_at
            record.full_data = carrier.model_dump_json()

            session.commit()
            return carrier

    def get_carrier(self, carrier_id: str) -> Optional[Carrier]:
        """Get a carrier by ID."""
        with self.get_session() as session:
            record = session.query(CarrierRecord).filter_by(id=carrier_id).first()
            if record and record.full_data:
                return Carrier.model_validate_json(record.full_data)
            return None

    def get_carrier_by_mc(self, mc_number: str) -> Optional[Carrier]:
        """Get a carrier by MC number."""
        with self.get_session() as session:
            record = session.query(CarrierRecord).filter_by(mc_number=mc_number).first()
            if record and record.full_data:
                return Carrier.model_validate_json(record.full_data)
            return None

    def list_available_carriers(
        self,
        state: Optional[str] = None,
        equipment_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[Carrier]:
        """List available carriers for dispatch."""
        with self.get_session() as session:
            query = session.query(CarrierRecord).filter(
                CarrierRecord.status == "active",
                CarrierRecord.is_available == True,
            )

            if state:
                query = query.filter(CarrierRecord.current_location_state == state.upper())

            query = query.order_by(CarrierRecord.reliability_score.desc())
            query = query.limit(limit)

            carriers = []
            for record in query.all():
                if record.full_data:
                    carrier = Carrier.model_validate_json(record.full_data)
                    # Filter by equipment if specified
                    if equipment_type:
                        if equipment_type in [str(e) for e in carrier.fleet.equipment_types]:
                            carriers.append(carrier)
                    else:
                        carriers.append(carrier)
            return carriers

    # =========================================================================
    # Load Operations
    # =========================================================================

    def save_load(self, load: Load) -> Load:
        """Save or update a load."""
        with self.get_session() as session:
            record = session.query(LoadRecord).filter_by(id=load.id).first()

            if record is None:
                record = LoadRecord(id=load.id)
                session.add(record)

            record.external_id = load.external_id
            record.reference_number = load.reference_number
            record.origin_city = load.origin.city
            record.origin_state = load.origin.state
            record.destination_city = load.destination.city
            record.destination_state = load.destination.state
            record.lane = load.lane
            record.loaded_miles = load.loaded_miles
            record.deadhead_miles = load.deadhead_miles
            record.pickup_date = load.pickup_window.earliest
            record.delivery_date = load.delivery_window.earliest
            record.commodity = load.commodity
            record.equipment_type = str(load.equipment_type)
            record.weight_lbs = load.dimensions.weight_lbs
            record.rate = load.rate
            record.rate_per_mile = load.rate_per_mile
            record.halal_status = load.halal_status
            record.halal_review_notes = load.halal_review_notes
            record.broker_name = load.broker.company_name
            record.broker_mc = load.broker.mc_number
            record.broker_phone = load.broker.contact_phone
            record.status = load.status
            record.assigned_carrier_id = load.assigned_carrier_id
            record.assigned_carrier_name = load.assigned_carrier_name
            record.commission_rate = load.commission_rate
            record.commission_amount = load.commission_amount
            record.charity_contribution = load.charity_contribution
            record.posted_at = load.posted_at
            record.booked_at = load.booked_at
            record.picked_up_at = load.picked_up_at
            record.delivered_at = load.delivered_at
            record.created_at = load.created_at
            record.updated_at = load.updated_at
            record.full_data = load.model_dump_json()

            session.commit()
            return load

    def get_load(self, load_id: str) -> Optional[Load]:
        """Get a load by ID."""
        with self.get_session() as session:
            record = session.query(LoadRecord).filter_by(id=load_id).first()
            if record and record.full_data:
                return Load.model_validate_json(record.full_data)
            return None

    def list_available_loads(
        self,
        origin_state: Optional[str] = None,
        equipment_type: Optional[str] = None,
        min_rate: Optional[float] = None,
        halal_only: bool = True,
        limit: int = 50,
    ) -> list[Load]:
        """List available loads for dispatch."""
        with self.get_session() as session:
            query = session.query(LoadRecord).filter(
                LoadRecord.status == "available",
            )

            if origin_state:
                query = query.filter(LoadRecord.origin_state == origin_state.upper())
            if equipment_type:
                query = query.filter(LoadRecord.equipment_type == equipment_type)
            if min_rate:
                query = query.filter(LoadRecord.rate_per_mile >= min_rate)
            if halal_only:
                query = query.filter(LoadRecord.halal_status != "haram")

            query = query.order_by(LoadRecord.rate_per_mile.desc())
            query = query.limit(limit)

            loads = []
            for record in query.all():
                if record.full_data:
                    loads.append(Load.model_validate_json(record.full_data))
            return loads

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self.get_session() as session:
            return {
                "leads": {
                    "total": session.query(LeadRecord).count(),
                    "new": session.query(LeadRecord).filter_by(status="new").count(),
                    "qualified": session.query(LeadRecord).filter_by(is_qualified=True).count(),
                    "converted": session.query(LeadRecord).filter_by(status="converted").count(),
                },
                "carriers": {
                    "total": session.query(CarrierRecord).count(),
                    "active": session.query(CarrierRecord).filter_by(status="active").count(),
                    "available": session.query(CarrierRecord).filter_by(is_available=True).count(),
                },
                "loads": {
                    "total": session.query(LoadRecord).count(),
                    "available": session.query(LoadRecord).filter_by(status="available").count(),
                    "booked": session.query(LoadRecord).filter_by(status="booked").count(),
                    "delivered": session.query(LoadRecord).filter_by(status="delivered").count(),
                },
            }


@lru_cache
def get_repository() -> Repository:
    """Get cached repository instance."""
    repo = Repository()
    repo.init_db()
    return repo
