"""
Halal Filter for Load Commodities

Filters loads based on Islamic dietary and ethical guidelines.
This is a core component of Al-Buraq's ethical framework.
"""

from typing import Tuple
from dataclasses import dataclass

from ..models.load import Load
from ..models.enums import HalalStatus
from ..config import HARAM_KEYWORDS, REVIEW_KEYWORDS, HALAL_COMMODITIES


@dataclass
class HalalCheckResult:
    """Result of a halal compliance check."""

    status: HalalStatus
    reason: str
    matched_keyword: str | None = None
    confidence: float = 1.0  # 0-1, lower for UNKNOWN status


class HalalFilter:
    """
    Filters loads based on Islamic dietary and ethical guidelines.

    This filter implements the Halal Rizq principle from MISSION.md.
    It categorizes commodities as HALAL, HARAM, or UNKNOWN (requires review).
    """

    def __init__(
        self,
        haram_keywords: set[str] | None = None,
        review_keywords: set[str] | None = None,
        halal_commodities: set[str] | None = None,
    ):
        """
        Initialize the filter with keyword sets.

        Args:
            haram_keywords: Set of keywords indicating haram commodities
            review_keywords: Set of keywords requiring manual review
            halal_commodities: Set of known halal commodity types
        """
        self.haram_keywords = haram_keywords or HARAM_KEYWORDS
        self.review_keywords = review_keywords or REVIEW_KEYWORDS
        self.halal_commodities = halal_commodities or HALAL_COMMODITIES

    def check_commodity(self, commodity: str, description: str | None = None) -> HalalCheckResult:
        """
        Check if a commodity is halal.

        Args:
            commodity: The commodity name/type
            description: Optional detailed description

        Returns:
            HalalCheckResult with status, reason, and matched keyword
        """
        # Normalize text for comparison
        commodity_lower = commodity.lower().strip()
        description_lower = (description or "").lower().strip()
        combined_text = f"{commodity_lower} {description_lower}"

        # Step 1: Check for explicit haram keywords (highest priority)
        for keyword in self.haram_keywords:
            if keyword in combined_text:
                return HalalCheckResult(
                    status=HalalStatus.HARAM,
                    reason=f"Haram commodity detected: '{keyword}' found in '{commodity}'",
                    matched_keyword=keyword,
                    confidence=1.0,
                )

        # Step 2: Check for keywords requiring review
        for keyword in self.review_keywords:
            if keyword in combined_text:
                return HalalCheckResult(
                    status=HalalStatus.UNKNOWN,
                    reason=f"Manual review required: '{keyword}' found - verify halal compliance",
                    matched_keyword=keyword,
                    confidence=0.5,
                )

        # Step 3: Check if explicitly halal
        for halal_word in self.halal_commodities:
            if halal_word in combined_text:
                return HalalCheckResult(
                    status=HalalStatus.HALAL,
                    reason=f"Commodity verified halal: matches '{halal_word}'",
                    matched_keyword=halal_word,
                    confidence=0.95,
                )

        # Step 4: Default to unknown for unrecognized commodities
        return HalalCheckResult(
            status=HalalStatus.UNKNOWN,
            reason=f"Unrecognized commodity: '{commodity}' - manual verification recommended",
            matched_keyword=None,
            confidence=0.3,
        )

    def check_load(self, load: Load) -> HalalCheckResult:
        """
        Check if a load's commodity is halal.

        Args:
            load: The Load object to check

        Returns:
            HalalCheckResult with status and reason
        """
        return self.check_commodity(load.commodity, load.commodity_description)

    def filter_load(self, load: Load) -> Tuple[bool, str]:
        """
        Filter a load and update its halal status.

        Args:
            load: The Load object to filter

        Returns:
            Tuple of (should_accept, reason)
        """
        result = self.check_load(load)

        # Update load's halal status
        load.halal_status = result.status
        load.halal_review_notes = result.reason

        if result.status == HalalStatus.HARAM:
            load.reject_haram(result.reason)
            return (False, result.reason)

        if result.status == HalalStatus.UNKNOWN:
            # Accept but flag for review
            return (True, f"REVIEW NEEDED: {result.reason}")

        return (True, result.reason)

    def filter_loads(self, loads: list[Load]) -> dict[str, list[Load]]:
        """
        Filter a list of loads into halal/haram/unknown categories.

        Args:
            loads: List of Load objects to filter

        Returns:
            Dict with 'halal', 'haram', and 'review_needed' lists
        """
        result = {
            "halal": [],
            "haram": [],
            "review_needed": [],
        }

        for load in loads:
            check_result = self.check_load(load)
            load.halal_status = check_result.status
            load.halal_review_notes = check_result.reason

            if check_result.status == HalalStatus.HALAL:
                result["halal"].append(load)
            elif check_result.status == HalalStatus.HARAM:
                load.reject_haram(check_result.reason)
                result["haram"].append(load)
            else:
                result["review_needed"].append(load)

        return result

    def get_stats(self, loads: list[Load]) -> dict:
        """
        Get statistics about halal compliance in a list of loads.

        Args:
            loads: List of Load objects

        Returns:
            Dict with counts and percentages
        """
        total = len(loads)
        if total == 0:
            return {
                "total": 0,
                "halal": 0,
                "haram": 0,
                "review_needed": 0,
                "halal_rate": 0.0,
                "rejection_rate": 0.0,
            }

        filtered = self.filter_loads(loads)

        halal_count = len(filtered["halal"])
        haram_count = len(filtered["haram"])
        review_count = len(filtered["review_needed"])

        return {
            "total": total,
            "halal": halal_count,
            "haram": haram_count,
            "review_needed": review_count,
            "halal_rate": round(halal_count / total, 3),
            "rejection_rate": round(haram_count / total, 3),
        }


# =============================================================================
# Convenience Functions
# =============================================================================

# Global filter instance
_filter = HalalFilter()


def check_commodity(commodity: str, description: str | None = None) -> HalalCheckResult:
    """
    Quick check if a commodity is halal.

    Args:
        commodity: The commodity name
        description: Optional description

    Returns:
        HalalCheckResult
    """
    return _filter.check_commodity(commodity, description)


def is_halal(commodity: str) -> bool:
    """Simple check if commodity is halal."""
    result = check_commodity(commodity)
    return result.status == HalalStatus.HALAL


def is_haram(commodity: str) -> bool:
    """Simple check if commodity is haram."""
    result = check_commodity(commodity)
    return result.status == HalalStatus.HARAM


# =============================================================================
# Example Usage & Testing
# =============================================================================

if __name__ == "__main__":
    # Test cases
    test_commodities = [
        ("Beer", None),
        ("Dry Goods", None),
        ("Electronics - TVs", None),
        ("Pork Products", None),
        ("Fresh Produce - Vegetables", None),
        ("Meat Products", "Beef and chicken"),
        ("General Freight", None),
        ("Wine and Spirits", None),
        ("Cannabis Products", "THC edibles"),
        ("Building Materials", "Lumber and steel"),
        ("Tobacco Products", None),
        ("Medical Supplies", None),
        ("Gelatin Products", "Candy manufacturing"),
    ]

    filter = HalalFilter()

    print("=" * 60)
    print("HALAL FILTER TEST RESULTS")
    print("=" * 60)

    for commodity, description in test_commodities:
        result = filter.check_commodity(commodity, description)
        status_icon = {
            HalalStatus.HALAL: "[OK]",
            HalalStatus.HARAM: "[X]",
            HalalStatus.UNKNOWN: "[?]",
        }[result.status]

        print(f"\n{status_icon} {commodity}")
        print(f"    Status: {result.status.value}")
        print(f"    Reason: {result.reason}")
        if result.matched_keyword:
            print(f"    Matched: '{result.matched_keyword}'")
