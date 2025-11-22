"""Enumerations for Al-Buraq dispatch system."""

from enum import Enum


class EquipmentType(str, Enum):
    """Types of trucking equipment."""

    DRY_VAN = "dry_van"
    REEFER = "reefer"
    FLATBED = "flatbed"
    STEP_DECK = "step_deck"
    LOWBOY = "lowboy"
    TANKER = "tanker"
    HOPPER = "hopper"
    CAR_HAULER = "car_hauler"
    POWER_ONLY = "power_only"
    BOX_TRUCK = "box_truck"
    SPRINTER = "sprinter"


class LeadStatus(str, Enum):
    """Status of a lead in the sales pipeline."""

    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    NURTURING = "nurturing"
    CONVERTED = "converted"
    REJECTED = "rejected"
    DO_NOT_CONTACT = "do_not_contact"


class LeadSource(str, Enum):
    """Source where the lead was acquired."""

    FMCSA_SAFER = "fmcsa_safer"
    DAT_LOADBOARD = "dat_loadboard"
    TRUCKSTOP = "truckstop"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    REFERRAL = "referral"
    INBOUND = "inbound"
    COLD_OUTREACH = "cold_outreach"


class CarrierStatus(str, Enum):
    """Status of a carrier in the system."""

    PROSPECT = "prospect"
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PAUSED = "paused"
    CHURNED = "churned"
    BLACKLISTED = "blacklisted"


class LoadStatus(str, Enum):
    """Status of a load/shipment."""

    AVAILABLE = "available"
    PENDING = "pending"
    OFFERED = "offered"
    BOOKED = "booked"
    DISPATCHED = "dispatched"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REJECTED_HARAM = "rejected_haram"
    REJECTED_RATE = "rejected_rate"


class HalalStatus(str, Enum):
    """Halal compliance status for loads."""

    HALAL = "halal"
    HARAM = "haram"
    UNKNOWN = "unknown"  # Requires manual review


class CommunicationChannel(str, Enum):
    """Communication channels for outreach."""

    VOICE_CALL = "voice"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class PaymentTerms(str, Enum):
    """Payment terms for brokers."""

    QUICK_PAY = "quick_pay"  # 1-3 days
    NET_15 = "net_15"
    NET_30 = "net_30"
    NET_45 = "net_45"
    FACTORING = "factoring"
