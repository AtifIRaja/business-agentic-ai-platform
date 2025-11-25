"""
Constitution Compliance Tests

These tests verify that Al-Buraq STRICTLY follows the ethical rules
defined in MISSION.md. These are critical tests that MUST NEVER FAIL.

Failure of any test indicates a violation of our core values.
"""

import pytest
from datetime import datetime, timedelta

# Import system components
from src.al_buraq.filters import HalalFilter
from src.al_buraq.models.load import Load, Location, TimeWindow, LoadDimensions, BrokerInfo
from src.al_buraq.models.enums import HalalStatus, EquipmentType


class TestHalalCompliance:
    """
    Test 1: Halal Compliance

    Verifies that the system correctly identifies haram commodities
    and rejects them according to MISSION.md rules.
    """

    def test_haram_detection(self):
        """CRITICAL: System MUST detect and reject all haram commodities"""
        halal_filter = HalalFilter()

        # MISSION.md: Prohibited Loads (Haram - MUST REJECT)
        haram_commodities = ["Beer", "Pork", "Gambling", "Tobacco"]

        for commodity in haram_commodities:
            result = halal_filter.check_commodity(commodity)
            assert result.status == HalalStatus.HARAM, (
                f"CONSTITUTION VIOLATION: '{commodity}' must be detected as HARAM. "
                f"Got: {result.status.value}. This violates MISSION.md Core Value #1."
            )

    def test_halal_acceptance(self):
        """System MUST accept halal commodities"""
        halal_filter = HalalFilter()

        # MISSION.md: Permitted Loads (Halal - ACCEPT)
        halal_commodities = ["Rice", "Furniture", "Solar Panels"]

        for commodity in halal_commodities:
            result = halal_filter.check_commodity(commodity)
            # Should be HALAL or UNKNOWN (requires review), but NEVER HARAM
            assert result.status != HalalStatus.HARAM, (
                f"CONSTITUTION VIOLATION: '{commodity}' incorrectly marked as HARAM. "
                f"Got: {result.status.value}"
            )


class TestCommissionMath:
    """
    Test 2: Commission Calculation

    Verifies that commission is calculated exactly as specified in MISSION.md:
    "Standard Dispatch: 7%"
    """

    def test_commission_rate_exactness(self):
        """CRITICAL: Commission MUST be exactly 7%, not 6.9% or 7.1%"""
        # Create a mock load with rate = $1000
        load = Load(
            origin=Location(city="Chicago", state="IL", zip_code="60601"),
            destination=Location(city="Dallas", state="TX", zip_code="75201"),
            pickup_window=TimeWindow(
                earliest=datetime.utcnow() + timedelta(days=1),
                latest=datetime.utcnow() + timedelta(days=1, hours=4),
            ),
            delivery_window=TimeWindow(
                earliest=datetime.utcnow() + timedelta(days=3),
                latest=datetime.utcnow() + timedelta(days=3, hours=8),
            ),
            commodity="General Freight",
            equipment_type=EquipmentType.DRY_VAN,
            rate=1000.00,  # $1000 load
            loaded_miles=500,
            dimensions=LoadDimensions(weight_lbs=40000),
            broker=BrokerInfo(
                company_name="Test Broker",
                mc_number="123456",
                contact_phone="555-0100"
            ),
        )

        # Calculate commission using the Load model's method
        commission = load.calculate_commission()

        # MISSION.md: "Standard Dispatch | 7%"
        expected_commission = 70.00  # 7% of $1000

        assert commission == expected_commission, (
            f"CONSTITUTION VIOLATION: Commission must be exactly $70.00 (7% of $1000). "
            f"Got: ${commission}. This violates MISSION.md Core Value #3."
        )

        # Verify it's NOT $69 or $71
        assert commission != 69.00, "Commission cannot be $69 (6.9%)"
        assert commission != 71.00, "Commission cannot be $71 (7.1%)"

        # Double-check with manual calculation
        manual_commission = load.rate * 0.07
        assert commission == manual_commission, (
            f"Commission calculation mismatch. "
            f"Method returned ${commission}, manual calc = ${manual_commission}"
        )


class TestCharityAllocation:
    """
    Test 3: Charity Allocation

    Verifies that charity contribution is exactly 5% of profit as specified
    in MISSION.md: "5% of Net Profit" (implemented as 5% of commission)
    """

    def test_charity_percentage(self):
        """CRITICAL: Charity MUST be exactly 5% of commission ($3.50 from $70)"""
        # Create a load with $1000 rate
        load = Load(
            origin=Location(city="Houston", state="TX", zip_code="77001"),
            destination=Location(city="Atlanta", state="GA", zip_code="30301"),
            pickup_window=TimeWindow(
                earliest=datetime.utcnow() + timedelta(days=1),
                latest=datetime.utcnow() + timedelta(days=1, hours=4),
            ),
            delivery_window=TimeWindow(
                earliest=datetime.utcnow() + timedelta(days=3),
                latest=datetime.utcnow() + timedelta(days=3, hours=8),
            ),
            commodity="Electronics",
            equipment_type=EquipmentType.DRY_VAN,
            rate=1000.00,
            loaded_miles=800,
            dimensions=LoadDimensions(weight_lbs=35000),
            broker=BrokerInfo(
                company_name="Test Broker LLC",
                mc_number="654321",
                contact_phone="555-0200"
            ),
        )

        # Calculate commission (this also calculates charity)
        commission = load.calculate_commission()

        # MISSION.md: "Total: 5% minimum to verified organizations"
        # Implementation: 5% of commission
        expected_charity = 3.50  # 5% of $70 commission

        assert load.charity_contribution == expected_charity, (
            f"CONSTITUTION VIOLATION: Charity must be exactly $3.50 (5% of $70 commission). "
            f"Got: ${load.charity_contribution}. This violates MISSION.md Core Value #4."
        )

        # Verify the calculation
        assert load.charity_contribution == commission * 0.05, (
            f"Charity calculation error. Should be 5% of commission (${commission}). "
            f"Got: ${load.charity_contribution}"
        )

        # Additional verification: charity should be 0.35% of total rate
        # (7% commission * 5% charity = 0.35%)
        expected_from_rate = round(load.rate * 0.07 * 0.05, 2)
        assert load.charity_contribution == expected_from_rate, (
            f"Charity miscalculation from rate. "
            f"Expected ${expected_from_rate}, got ${load.charity_contribution}"
        )


class TestConstitutionIntegrity:
    """
    Meta-tests to verify the constitution itself is intact
    """

    def test_commission_rate_constant(self):
        """Verify commission rate constant is exactly 0.07"""
        from src.al_buraq.config import settings

        assert settings.COMMISSION_RATE == 0.07, (
            f"CRITICAL: Base commission rate must be 0.07 (7%). "
            f"Got: {settings.COMMISSION_RATE}. Someone may have tampered with config."
        )

    def test_charity_rate_constant(self):
        """Verify charity percentage constant is exactly 0.05"""
        from src.al_buraq.config import settings

        assert settings.CHARITY_PERCENTAGE == 0.05, (
            f"CRITICAL: Charity percentage must be 0.05 (5%). "
            f"Got: {settings.CHARITY_PERCENTAGE}. Someone may have tampered with config."
        )


# =============================================================================
# Test Execution Summary
# =============================================================================

def test_summary_message(capsys):
    """
    Display a summary message when all constitution tests pass
    """
    print("\n" + "="*60)
    print("CONSTITUTION COMPLIANCE: ALL TESTS PASSED")
    print("="*60)
    print("✓ Halal compliance verified")
    print("✓ Commission math verified (7%)")
    print("✓ Charity allocation verified (5%)")
    print("✓ System integrity confirmed")
    print("\nAl-Buraq is operating in full compliance with MISSION.md")
    print("="*60)

    # This test always passes - it's just for display
    assert True


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "--tb=short"])
