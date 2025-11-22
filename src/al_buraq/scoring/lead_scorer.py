"""
Lead Scoring Algorithm

Scores and qualifies carrier leads based on likelihood of conversion
and fit with our dispatch services.
"""

from dataclasses import dataclass, field
from typing import Optional

from ..models.lead import Lead
from ..models.enums import LeadStatus
from ..config import settings, TARGET_EQUIPMENT, TARGET_STATES


@dataclass
class ScoringWeights:
    """
    Configurable weights for lead scoring.

    All weights should sum to 1.0 for normalized scoring.
    """

    authority_age: float = 0.15      # Newer authorities = more receptive
    fleet_size: float = 0.20         # Sweet spot: 1-10 trucks
    insurance: float = 0.15          # Meets minimum requirements
    safety: float = 0.15             # Good safety record
    equipment_match: float = 0.15    # Equipment we can dispatch
    location: float = 0.10           # In our operating area
    contact_quality: float = 0.10    # Has good contact info

    def __post_init__(self):
        """Validate weights sum to 1.0."""
        total = (
            self.authority_age
            + self.fleet_size
            + self.insurance
            + self.safety
            + self.equipment_match
            + self.location
            + self.contact_quality
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of lead score components."""

    authority_age: float = 0.0
    fleet_size: float = 0.0
    insurance: float = 0.0
    safety: float = 0.0
    equipment_match: float = 0.0
    location: float = 0.0
    contact_quality: float = 0.0

    # Additional insights
    authority_age_days: int = 0
    truck_count: int = 0
    meets_insurance_minimum: bool = False
    matching_equipment: list[str] = field(default_factory=list)
    matching_states: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "authority_age": self.authority_age,
            "fleet_size": self.fleet_size,
            "insurance": self.insurance,
            "safety": self.safety,
            "equipment_match": self.equipment_match,
            "location": self.location,
            "contact_quality": self.contact_quality,
            "authority_age_days": self.authority_age_days,
            "truck_count": self.truck_count,
            "meets_insurance_minimum": self.meets_insurance_minimum,
            "matching_equipment": self.matching_equipment,
            "matching_states": self.matching_states,
        }


class LeadScorer:
    """
    Scores leads based on likelihood of conversion and fit.

    Score range: 0.0 (worst) to 1.0 (best)
    Qualification threshold: 0.6 (configurable)

    Scoring Philosophy:
    - New authorities (< 6 months) are our best targets
    - Owner-operators and small fleets (1-10 trucks) are ideal
    - Equipment match is critical for dispatch capability
    - Insurance minimums are hard requirements
    """

    def __init__(
        self,
        weights: Optional[ScoringWeights] = None,
        qualification_threshold: Optional[float] = None,
        target_equipment: Optional[set[str]] = None,
        target_states: Optional[set[str]] = None,
    ):
        """
        Initialize the scorer.

        Args:
            weights: Custom scoring weights
            qualification_threshold: Minimum score to qualify (default 0.6)
            target_equipment: Set of equipment types we dispatch
            target_states: Set of states we operate in
        """
        self.weights = weights or ScoringWeights()
        self.threshold = qualification_threshold or settings.LEAD_QUALIFICATION_THRESHOLD
        self.target_equipment = target_equipment or TARGET_EQUIPMENT
        self.target_states = target_states or TARGET_STATES

    def score_authority_age(self, age_days: int) -> float:
        """
        Score based on authority age.

        New authorities are more receptive to dispatcher services.
        """
        if age_days < 30:
            return 1.0  # Brand new - very receptive
        elif age_days < 60:
            return 0.95
        elif age_days < 90:
            return 0.90
        elif age_days < 180:
            return 0.80
        elif age_days < 365:
            return 0.60
        elif age_days < 730:
            return 0.40
        else:
            return 0.20  # Established - less likely to switch

    def score_fleet_size(self, truck_count: int) -> float:
        """
        Score based on fleet size.

        Sweet spot: 1-5 trucks (owner-operators)
        These carriers most need dispatch services.
        """
        if truck_count == 1:
            return 1.0  # Perfect target - solo owner-operator
        elif truck_count == 2:
            return 0.95
        elif 3 <= truck_count <= 5:
            return 0.90
        elif 6 <= truck_count <= 10:
            return 0.75
        elif 11 <= truck_count <= 20:
            return 0.50
        elif 21 <= truck_count <= 50:
            return 0.35
        else:
            return 0.20  # Large fleets usually have in-house dispatch

    def score_insurance(self, lead: Lead) -> float:
        """
        Score based on insurance coverage.

        Meeting minimum requirements is essential.
        """
        if not lead.insurance.meets_minimum_requirements:
            return 0.0  # Disqualifying - hard requirement

        # Bonus for verified insurance
        if lead.insurance.insurance_verified:
            return 1.0
        elif lead.insurance.liability_coverage >= 1_500_000:
            return 0.90  # Above minimum
        else:
            return 0.75  # Meets minimum but not verified

    def score_safety(self, lead: Lead) -> float:
        """
        Score based on safety record.

        Lower CSA scores = better safety = higher score.
        """
        if lead.safety is None:
            return 0.5  # No data - neutral score

        overall = lead.safety.overall_safety_score
        if overall is None:
            return 0.5

        # CSA scores: 0-100, lower is better
        if overall < 30:
            return 1.0  # Excellent safety
        elif overall < 50:
            return 0.85  # Good
        elif overall < 70:
            return 0.60  # Acceptable
        elif overall < 85:
            return 0.30  # Concerning
        else:
            return 0.10  # Poor - risky to dispatch

    def score_equipment_match(self, lead: Lead) -> float:
        """
        Score based on equipment types.

        Higher score if carrier has equipment we can dispatch.
        """
        if not lead.fleet.equipment_types:
            return 0.3  # Unknown equipment

        # Convert enum values to strings for comparison
        equipment_set = set(
            e.value if hasattr(e, 'value') else str(e)
            for e in lead.fleet.equipment_types
        )
        matching = equipment_set & self.target_equipment

        if not matching:
            return 0.0  # No matching equipment

        # More matching equipment types = higher score
        match_ratio = len(matching) / len(self.target_equipment)
        return min(1.0, 0.5 + match_ratio * 0.5)

    def score_location(self, lead: Lead) -> float:
        """
        Score based on operating location.

        Higher score if carrier operates in our target states.
        """
        states_set = set(lead.fleet.operating_states)
        matching_states = states_set & self.target_states

        if matching_states:
            # More matching states = higher score
            if len(matching_states) >= 5:
                return 1.0
            elif len(matching_states) >= 3:
                return 0.85
            else:
                return 0.70
        elif lead.fleet.home_base_state in self.target_states:
            return 0.50  # Home base in target area
        else:
            return 0.20  # Outside our primary area

    def score_contact_quality(self, lead: Lead) -> float:
        """
        Score based on contact information quality.

        Better contact info = easier to reach = higher score.
        """
        score = 0.0

        # Phone is essential
        if lead.contact.phone_primary:
            score += 0.50

        # Email is valuable
        if lead.contact.email:
            score += 0.30

        # Secondary phone is bonus
        if lead.contact.phone_secondary:
            score += 0.15

        # Owner name helps personalization
        if lead.owner_name:
            score += 0.05

        return min(1.0, score)

    def score_lead(self, lead: Lead) -> tuple[float, ScoreBreakdown]:
        """
        Calculate overall lead score and detailed breakdown.

        Args:
            lead: The Lead to score

        Returns:
            Tuple of (total_score, breakdown)
        """
        breakdown = ScoreBreakdown()

        # Calculate individual component scores
        breakdown.authority_age = self.score_authority_age(lead.authority.authority_age_days)
        breakdown.fleet_size = self.score_fleet_size(lead.fleet.truck_count)
        breakdown.insurance = self.score_insurance(lead)
        breakdown.safety = self.score_safety(lead)
        breakdown.equipment_match = self.score_equipment_match(lead)
        breakdown.location = self.score_location(lead)
        breakdown.contact_quality = self.score_contact_quality(lead)

        # Additional insights
        breakdown.authority_age_days = lead.authority.authority_age_days
        breakdown.truck_count = lead.fleet.truck_count
        breakdown.meets_insurance_minimum = lead.insurance.meets_minimum_requirements
        breakdown.matching_equipment = list(
            set(str(e) for e in lead.fleet.equipment_types) & self.target_equipment
        )
        breakdown.matching_states = list(
            set(lead.fleet.operating_states) & self.target_states
        )

        # Calculate weighted total
        total_score = (
            breakdown.authority_age * self.weights.authority_age
            + breakdown.fleet_size * self.weights.fleet_size
            + breakdown.insurance * self.weights.insurance
            + breakdown.safety * self.weights.safety
            + breakdown.equipment_match * self.weights.equipment_match
            + breakdown.location * self.weights.location
            + breakdown.contact_quality * self.weights.contact_quality
        )

        return (round(total_score, 3), breakdown)

    def qualify_lead(self, lead: Lead) -> Lead:
        """
        Score and qualify a lead, updating the lead object.

        Args:
            lead: The Lead to qualify

        Returns:
            The updated Lead object
        """
        total_score, breakdown = self.score_lead(lead)

        # Update lead with score
        lead.lead_score = total_score
        lead.score_breakdown = breakdown.to_dict()

        # Determine qualification
        is_qualified = True
        disqualification_reason = None

        # Hard disqualifiers
        if breakdown.insurance == 0:
            is_qualified = False
            disqualification_reason = "Insurance does not meet minimum requirements"
        elif breakdown.equipment_match == 0:
            is_qualified = False
            disqualification_reason = "No matching equipment types for dispatch"
        elif breakdown.contact_quality == 0:
            is_qualified = False
            disqualification_reason = "Missing required contact information"
        elif total_score < self.threshold:
            is_qualified = False
            disqualification_reason = f"Lead score {total_score:.2f} below threshold {self.threshold}"

        # Update lead status
        if is_qualified:
            lead.qualify(total_score, breakdown.to_dict())
        else:
            lead.disqualify(disqualification_reason)

        return lead

    def rank_leads(self, leads: list[Lead]) -> list[Lead]:
        """
        Score and rank leads by score descending.

        Args:
            leads: List of leads to rank

        Returns:
            Sorted list of leads (highest score first)
        """
        for lead in leads:
            self.qualify_lead(lead)

        return sorted(leads, key=lambda x: x.lead_score, reverse=True)

    def get_qualification_summary(self, leads: list[Lead]) -> dict:
        """
        Get summary statistics for a batch of leads.

        Args:
            leads: List of scored leads

        Returns:
            Dict with qualification statistics
        """
        if not leads:
            return {
                "total": 0,
                "qualified": 0,
                "disqualified": 0,
                "qualification_rate": 0.0,
                "avg_score": 0.0,
                "top_score": 0.0,
            }

        qualified = [l for l in leads if l.is_qualified]
        scores = [l.lead_score for l in leads]

        return {
            "total": len(leads),
            "qualified": len(qualified),
            "disqualified": len(leads) - len(qualified),
            "qualification_rate": round(len(qualified) / len(leads), 3),
            "avg_score": round(sum(scores) / len(scores), 3),
            "top_score": max(scores),
            "score_distribution": {
                "excellent": len([s for s in scores if s >= 0.8]),
                "good": len([s for s in scores if 0.6 <= s < 0.8]),
                "fair": len([s for s in scores if 0.4 <= s < 0.6]),
                "poor": len([s for s in scores if s < 0.4]),
            },
        }


# =============================================================================
# Convenience Functions
# =============================================================================

# Global scorer instance
_scorer = LeadScorer()


def score_lead(lead: Lead) -> tuple[float, dict]:
    """
    Quick score a lead.

    Args:
        lead: The Lead to score

    Returns:
        Tuple of (score, breakdown_dict)
    """
    score, breakdown = _scorer.score_lead(lead)
    return (score, breakdown.to_dict())


def qualify_lead(lead: Lead) -> Lead:
    """Qualify a lead using default scorer."""
    return _scorer.qualify_lead(lead)


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    from datetime import datetime, timedelta
    from ..models.lead import Lead, ContactInfo, AuthorityInfo, InsuranceInfo, FleetInfo
    from ..models.enums import LeadSource, EquipmentType

    # Create test leads
    test_leads = [
        Lead(
            company_name="New Owner Operator LLC",
            contact=ContactInfo(phone_primary="5551234567", email="test@example.com"),
            authority=AuthorityInfo(
                mc_number="1234567",
                dot_number="7654321",
                authority_granted_date=datetime.utcnow() - timedelta(days=30),
            ),
            insurance=InsuranceInfo(liability_coverage=1_000_000, cargo_coverage=100_000),
            fleet=FleetInfo(
                truck_count=1,
                equipment_types=[EquipmentType.DRY_VAN],
                operating_states=["TX", "OK", "LA"],
                home_base_state="TX",
            ),
            source=LeadSource.FMCSA_SAFER,
        ),
        Lead(
            company_name="Big Fleet Inc",
            contact=ContactInfo(phone_primary="5559876543"),
            authority=AuthorityInfo(
                mc_number="9999999",
                dot_number="1111111",
                authority_granted_date=datetime.utcnow() - timedelta(days=1000),
            ),
            insurance=InsuranceInfo(liability_coverage=500_000, cargo_coverage=50_000),
            fleet=FleetInfo(
                truck_count=100,
                equipment_types=[EquipmentType.TANKER],
                operating_states=["AK"],
            ),
            source=LeadSource.DAT_LOADBOARD,
        ),
    ]

    scorer = LeadScorer()

    print("=" * 60)
    print("LEAD SCORING TEST RESULTS")
    print("=" * 60)

    for lead in test_leads:
        scorer.qualify_lead(lead)
        print(f"\n{lead.company_name}")
        print(f"  Score: {lead.lead_score:.2f}")
        print(f"  Qualified: {lead.is_qualified}")
        if lead.disqualification_reason:
            print(f"  Reason: {lead.disqualification_reason}")
        print(f"  Breakdown: {lead.score_breakdown}")
