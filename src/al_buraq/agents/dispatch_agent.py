"""
Dispatch Agent - Match loads to carriers and manage assignments.

Core dispatching logic with halal compliance and transparent commission.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
import random

from ..models.load import Load, Location, TimeWindow, LoadDimensions, BrokerInfo
from ..models.carrier import Carrier
from ..models.lead import Lead
from ..models.enums import EquipmentType, LoadStatus, HalalStatus
from ..db import Repository
from ..filters import HalalFilter, check_commodity


@dataclass
class LoadMatch:
    """A potential match between a load and carrier."""
    load: Load
    carrier_name: str
    carrier_mc: str
    carrier_state: str
    carrier_equipment: list[str]
    match_score: float  # 0-1, higher is better
    match_reasons: list[str]
    estimated_commission: float
    charity_contribution: float
    rate_per_mile: float


@dataclass
class DispatchRecommendation:
    """Recommendation for dispatching a load."""
    load: Load
    matches: list[LoadMatch]
    best_match: Optional[LoadMatch]
    halal_status: str
    halal_reason: str


@dataclass
class DispatchSession:
    """Results from a dispatch matching session."""
    total_loads: int = 0
    total_matches: int = 0
    halal_loads: int = 0
    haram_loads: int = 0
    recommendations: list[DispatchRecommendation] = field(default_factory=list)
    duration_seconds: float = 0.0


# US State coordinates for distance estimation (approximate centroids)
STATE_COORDS = {
    "AL": (32.8, -86.8), "AK": (64.0, -153.0), "AZ": (34.3, -111.7),
    "AR": (34.9, -92.4), "CA": (37.2, -119.4), "CO": (39.0, -105.5),
    "CT": (41.6, -72.7), "DE": (39.0, -75.5), "FL": (28.6, -82.4),
    "GA": (32.6, -83.4), "HI": (20.8, -156.3), "ID": (44.4, -114.6),
    "IL": (40.0, -89.2), "IN": (39.9, -86.3), "IA": (42.0, -93.5),
    "KS": (38.5, -98.4), "KY": (37.8, -85.7), "LA": (31.0, -92.0),
    "ME": (45.3, -69.0), "MD": (39.0, -76.8), "MA": (42.2, -71.5),
    "MI": (44.3, -85.4), "MN": (46.3, -94.3), "MS": (32.7, -89.7),
    "MO": (38.4, -92.5), "MT": (47.0, -109.6), "NE": (41.5, -99.8),
    "NV": (39.3, -116.6), "NH": (43.7, -71.6), "NJ": (40.2, -74.7),
    "NM": (34.5, -106.0), "NY": (42.9, -75.5), "NC": (35.5, -79.4),
    "ND": (47.4, -100.5), "OH": (40.4, -82.8), "OK": (35.6, -97.5),
    "OR": (44.0, -120.5), "PA": (40.9, -77.8), "RI": (41.7, -71.5),
    "SC": (33.9, -80.9), "SD": (44.4, -100.2), "TN": (35.8, -86.3),
    "TX": (31.5, -99.4), "UT": (39.3, -111.7), "VT": (44.0, -72.7),
    "VA": (37.5, -78.8), "WA": (47.4, -120.5), "WV": (38.9, -80.5),
    "WI": (44.6, -89.7), "WY": (43.0, -107.5), "DC": (38.9, -77.0),
}


class DispatchAgent:
    """
    Agent that matches loads to carriers.

    Features:
    - Equipment type matching
    - Geographic proximity scoring
    - Rate optimization
    - Halal compliance checking
    - Transparent commission calculation (7-8%)
    - Charity contribution (5% of commission)
    """

    def __init__(self, repository: Repository):
        self.repository = repository
        self.halal_filter = HalalFilter()
        self.commission_rate = 0.07  # 7% default
        self.charity_rate = 0.05  # 5% of commission to charity

    def _estimate_distance(self, state1: str, state2: str) -> float:
        """Estimate distance between states in miles."""
        if state1 not in STATE_COORDS or state2 not in STATE_COORDS:
            return 1000  # Default distance

        lat1, lon1 = STATE_COORDS[state1.upper()]
        lat2, lon2 = STATE_COORDS[state2.upper()]

        # Simple approximation: 1 degree ≈ 69 miles
        lat_diff = abs(lat1 - lat2) * 69
        lon_diff = abs(lon1 - lon2) * 55  # Adjusted for longitude

        return (lat_diff**2 + lon_diff**2) ** 0.5

    def _score_carrier_match(self, load: Load, carrier: Lead) -> tuple[float, list[str]]:
        """
        Score how well a carrier matches a load.

        Returns score (0-1) and list of match reasons.
        """
        score = 0.0
        reasons = []

        # Equipment match (40% weight)
        load_equipment = load.equipment_type.value if hasattr(load.equipment_type, 'value') else str(load.equipment_type)
        carrier_equipment = [
            e.value if hasattr(e, 'value') else str(e)
            for e in carrier.fleet.equipment_types
        ]

        if load_equipment in carrier_equipment:
            score += 0.4
            reasons.append(f"Equipment match: {load_equipment}")
        elif carrier_equipment:
            # Partial match for similar equipment
            score += 0.1
            reasons.append(f"Has equipment: {', '.join(carrier_equipment[:2])}")

        # Location proximity (30% weight)
        carrier_state = carrier.fleet.home_base_state
        if carrier_state:
            distance = self._estimate_distance(carrier_state, load.origin.state)
            if distance < 100:
                score += 0.3
                reasons.append(f"Near origin ({carrier_state})")
            elif distance < 300:
                score += 0.2
                reasons.append(f"Reasonable distance ({int(distance)} mi)")
            elif distance < 500:
                score += 0.1
                reasons.append(f"Moderate distance ({int(distance)} mi)")

        # Lane preference (15% weight)
        lane = f"{load.origin.state}-{load.destination.state}"
        if lane in carrier.fleet.preferred_lanes:
            score += 0.15
            reasons.append(f"Preferred lane: {lane}")
        elif load.destination.state in carrier.fleet.operating_states:
            score += 0.08
            reasons.append(f"Operates in {load.destination.state}")

        # Fleet size bonus (10% weight)
        if carrier.fleet.truck_count >= 3:
            score += 0.1
            reasons.append(f"Fleet size: {carrier.fleet.truck_count} trucks")
        elif carrier.fleet.truck_count >= 1:
            score += 0.05

        # Verification bonus (5% weight)
        if carrier.social_verified:
            score += 0.03
            reasons.append("Verified (social)")
        if carrier.high_intent:
            score += 0.02
            reasons.append("High intent")

        return min(1.0, score), reasons

    def _calculate_commission(self, rate: float) -> tuple[float, float]:
        """Calculate commission and charity contribution."""
        commission = rate * self.commission_rate
        charity = commission * self.charity_rate
        return commission, charity

    def find_matches(
        self,
        load: Load,
        limit: int = 5,
        min_score: float = 0.3,
    ) -> list[LoadMatch]:
        """
        Find carrier matches for a load.

        Args:
            load: Load to match
            limit: Maximum matches to return
            min_score: Minimum match score

        Returns:
            List of LoadMatch sorted by score
        """
        matches = []

        # Get verified leads as potential carriers
        carriers = self.repository.get_verified_leads(limit=50)

        # Also get qualified leads if not enough verified
        if len(carriers) < 20:
            qualified = self.repository.list_leads(is_qualified=True, limit=50)
            carriers.extend(qualified)

        for carrier in carriers:
            score, reasons = self._score_carrier_match(load, carrier)

            if score >= min_score:
                commission, charity = self._calculate_commission(load.rate)

                carrier_equipment = [
                    e.value if hasattr(e, 'value') else str(e)
                    for e in carrier.fleet.equipment_types
                ]

                match = LoadMatch(
                    load=load,
                    carrier_name=carrier.company_name,
                    carrier_mc=carrier.authority.mc_number,
                    carrier_state=carrier.fleet.home_base_state or "?",
                    carrier_equipment=carrier_equipment,
                    match_score=score,
                    match_reasons=reasons,
                    estimated_commission=commission,
                    charity_contribution=charity,
                    rate_per_mile=load.rate_per_mile,
                )
                matches.append(match)

        # Sort by score descending
        matches.sort(key=lambda m: m.match_score, reverse=True)
        return matches[:limit]

    def generate_recommendations(
        self,
        loads: list[Load],
        matches_per_load: int = 3,
    ) -> list[DispatchRecommendation]:
        """
        Generate dispatch recommendations for multiple loads.

        Args:
            loads: Loads to process
            matches_per_load: Max matches per load

        Returns:
            List of DispatchRecommendation
        """
        recommendations = []

        for load in loads:
            # Check halal status
            halal_result = check_commodity(load.commodity)

            if halal_result.status == "haram":
                # Skip haram loads
                rec = DispatchRecommendation(
                    load=load,
                    matches=[],
                    best_match=None,
                    halal_status="HARAM",
                    halal_reason=halal_result.reason,
                )
            else:
                # Find matches
                matches = self.find_matches(load, limit=matches_per_load)

                rec = DispatchRecommendation(
                    load=load,
                    matches=matches,
                    best_match=matches[0] if matches else None,
                    halal_status="HALAL" if halal_result.status == "halal" else "REVIEW",
                    halal_reason=halal_result.reason,
                )

            recommendations.append(rec)

        return recommendations

    def create_sample_loads(self, count: int = 5) -> list[Load]:
        """Create sample loads for testing dispatch functionality."""
        commodities = [
            ("Electronics", EquipmentType.DRY_VAN),
            ("Fresh Produce", EquipmentType.REEFER),
            ("Steel Coils", EquipmentType.FLATBED),
            ("Packaged Food", EquipmentType.DRY_VAN),
            ("Medical Supplies", EquipmentType.DRY_VAN),
            ("Furniture", EquipmentType.DRY_VAN),
            ("Auto Parts", EquipmentType.DRY_VAN),
            ("Frozen Seafood", EquipmentType.REEFER),
            ("Building Materials", EquipmentType.FLATBED),
            ("Machinery", EquipmentType.FLATBED),
        ]

        routes = [
            ("Dallas", "TX", "Los Angeles", "CA", 1400),
            ("Chicago", "IL", "Atlanta", "GA", 720),
            ("Houston", "TX", "Miami", "FL", 1180),
            ("Phoenix", "AZ", "Denver", "CO", 600),
            ("Seattle", "WA", "Portland", "OR", 175),
            ("Nashville", "TN", "Charlotte", "NC", 410),
            ("Kansas City", "MO", "St. Louis", "MO", 250),
            ("Detroit", "MI", "Cleveland", "OH", 170),
            ("Minneapolis", "MN", "Milwaukee", "WI", 340),
            ("San Antonio", "TX", "Austin", "TX", 80),
        ]

        brokers = [
            ("TQL Logistics", "123456", "(800) 555-0101"),
            ("CH Robinson", "234567", "(800) 555-0102"),
            ("XPO Logistics", "345678", "(800) 555-0103"),
            ("Coyote Logistics", "456789", "(800) 555-0104"),
            ("Echo Global", "567890", "(800) 555-0105"),
        ]

        loads = []
        for i in range(count):
            commodity, equipment = random.choice(commodities)
            origin_city, origin_state, dest_city, dest_state, miles = random.choice(routes)
            broker_name, broker_mc, broker_phone = random.choice(brokers)

            # Generate rate ($2.00 - $3.50 per mile)
            rate_per_mile = round(random.uniform(2.0, 3.5), 2)
            rate = round(rate_per_mile * miles, 2)

            # Pickup date 1-5 days from now
            pickup_date = datetime.utcnow() + timedelta(days=random.randint(1, 5))
            delivery_date = pickup_date + timedelta(days=max(1, miles // 500))

            load = Load(
                origin=Location(
                    city=origin_city,
                    state=origin_state,
                    zip_code="00000",
                ),
                destination=Location(
                    city=dest_city,
                    state=dest_state,
                    zip_code="00000",
                ),
                pickup_window=TimeWindow(
                    earliest=pickup_date,
                    latest=pickup_date + timedelta(hours=4),
                ),
                delivery_window=TimeWindow(
                    earliest=delivery_date,
                    latest=delivery_date + timedelta(hours=8),
                ),
                commodity=commodity,
                equipment_type=equipment,
                rate=rate,
                loaded_miles=miles,
                dimensions=LoadDimensions(weight_lbs=random.randint(20000, 44000)),
                broker=BrokerInfo(
                    company_name=broker_name,
                    mc_number=broker_mc,
                    contact_phone=broker_phone,
                ),
            )

            # Check halal status
            halal_result = check_commodity(commodity)
            load.halal_status = halal_result.status

            loads.append(load)

        return loads

    def run_dispatch_session(
        self,
        load_count: int = 5,
        matches_per_load: int = 3,
        use_sample_loads: bool = True,
    ) -> DispatchSession:
        """
        Run a full dispatch matching session.

        Args:
            load_count: Number of loads to process
            matches_per_load: Matches per load
            use_sample_loads: Generate sample loads if True

        Returns:
            DispatchSession with results
        """
        start_time = datetime.utcnow()
        session = DispatchSession()

        # Get or create loads
        if use_sample_loads:
            loads = self.create_sample_loads(load_count)
        else:
            loads = self.repository.list_available_loads(limit=load_count)

        session.total_loads = len(loads)

        # Generate recommendations
        recommendations = self.generate_recommendations(loads, matches_per_load)
        session.recommendations = recommendations

        # Count stats
        for rec in recommendations:
            if rec.halal_status == "HARAM":
                session.haram_loads += 1
            else:
                session.halal_loads += 1
                session.total_matches += len(rec.matches)

        session.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return session
