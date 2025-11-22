"""
FMCSA SAFER Hunter

Finds new carrier authorities from the FMCSA SAFER database.
This is a primary source for new owner-operator leads.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional, AsyncIterator
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from .base_hunter import BaseHunter, HuntResult
from ..models.lead import Lead, ContactInfo, AuthorityInfo, InsuranceInfo, FleetInfo
from ..models.enums import LeadSource, EquipmentType
from ..config import settings


@dataclass
class SAFERCarrierData:
    """Raw carrier data from SAFER."""

    mc_number: str
    dot_number: str
    legal_name: str
    dba_name: Optional[str] = None
    physical_address: Optional[str] = None
    phone: Optional[str] = None
    power_units: int = 1
    drivers: int = 1
    mcs150_date: Optional[datetime] = None
    operation_classification: Optional[str] = None
    carrier_operation: Optional[str] = None
    cargo_carried: list[str] = None

    def __post_init__(self):
        if self.cargo_carried is None:
            self.cargo_carried = []


class FMCSAHunter(BaseHunter):
    """
    Hunter that finds carriers from FMCSA SAFER database.

    The SAFER (Safety and Fitness Electronic Records) system
    contains registration data for all US motor carriers.

    Note: This implementation uses simulated data for development.
    In production, you would integrate with the actual FMCSA API
    or web scraping with proper rate limiting.
    """

    SAFER_BASE_URL = "https://safer.fmcsa.dot.gov"

    def __init__(self):
        super().__init__(source_name="FMCSA_SAFER")
        self.rate_limit_delay = settings.HUNTER_RATE_LIMIT_DELAY

    async def hunt(
        self,
        limit: int = 50,
        min_authority_age_days: int = 0,
        max_authority_age_days: int = 180,
        states: Optional[list[str]] = None,
        **kwargs,
    ) -> HuntResult:
        """
        Hunt for new carrier authorities.

        Args:
            limit: Maximum leads to find
            min_authority_age_days: Minimum days since authority granted
            max_authority_age_days: Maximum days since authority granted
            states: Filter by home state(s)

        Returns:
            HuntResult with discovered leads
        """
        result = HuntResult(source=self.source_name)

        leads = []
        async for lead in self.hunt_stream(
            limit=limit,
            min_authority_age_days=min_authority_age_days,
            max_authority_age_days=max_authority_age_days,
            states=states,
        ):
            leads.append(lead)

        result.leads = leads
        result.total_found = len(leads)
        result.total_processed = len(leads)

        return result.complete()

    async def hunt_stream(
        self,
        limit: int = 50,
        min_authority_age_days: int = 0,
        max_authority_age_days: int = 180,
        states: Optional[list[str]] = None,
        **kwargs,
    ) -> AsyncIterator[Lead]:
        """
        Stream leads as they're discovered.

        In production, this would query the FMCSA API or scrape SAFER.
        For development, we generate realistic test data.
        """
        # For MVP, generate simulated leads
        # TODO: Replace with actual FMCSA API integration
        count = 0

        for carrier_data in self._generate_test_carriers(limit, states):
            try:
                # Apply age filter
                if carrier_data.mcs150_date:
                    age_days = (datetime.utcnow() - carrier_data.mcs150_date).days
                    if age_days < min_authority_age_days:
                        continue
                    if age_days > max_authority_age_days:
                        continue

                lead = await self._carrier_to_lead(carrier_data)
                if lead:
                    count += 1
                    yield lead

                    if count >= limit:
                        break

                # Rate limiting
                await asyncio.sleep(self.rate_limit_delay)

            except Exception as e:
                # Log error but continue
                print(f"Error processing carrier {carrier_data.mc_number}: {e}")
                continue

    async def lookup_carrier(self, mc_number: str) -> Optional[Lead]:
        """
        Look up a specific carrier by MC number.

        Args:
            mc_number: The MC number to look up

        Returns:
            Lead if found, None otherwise
        """
        # In production, this would query SAFER directly
        # For now, return None (not found)
        return None

    async def verify_authority(self, mc_number: str) -> dict:
        """
        Verify a carrier's authority status.

        Args:
            mc_number: The MC number to verify

        Returns:
            Dict with authority status details
        """
        # In production, check SAFER for current status
        return {
            "mc_number": mc_number,
            "status": "ACTIVE",
            "verified_at": datetime.utcnow().isoformat(),
            "common_authority": True,
            "contract_authority": False,
            "broker_authority": False,
        }

    async def _carrier_to_lead(self, data: SAFERCarrierData) -> Optional[Lead]:
        """Convert SAFER data to a Lead object."""
        try:
            # Parse phone number
            phone = self._clean_phone(data.phone) if data.phone else None
            if not phone:
                return None  # Skip carriers without phone

            # Parse state from address
            state = self._extract_state(data.physical_address)

            # Determine equipment types from cargo carried
            equipment = self._infer_equipment(data.cargo_carried, data.carrier_operation)

            # Calculate authority date
            authority_date = data.mcs150_date or datetime.utcnow() - timedelta(days=30)

            lead = Lead(
                company_name=data.legal_name,
                dba_name=data.dba_name,
                legal_name=data.legal_name,
                contact=ContactInfo(
                    phone_primary=phone,
                    timezone=self._state_to_timezone(state),
                ),
                authority=AuthorityInfo(
                    mc_number=data.mc_number,
                    dot_number=data.dot_number,
                    authority_status="ACTIVE",
                    authority_granted_date=authority_date,
                    common_authority=True,
                ),
                insurance=InsuranceInfo(
                    liability_coverage=1_000_000,  # Assumed minimum for active authority
                    cargo_coverage=100_000,
                ),
                fleet=FleetInfo(
                    truck_count=data.power_units,
                    driver_count=data.drivers,
                    equipment_types=equipment,
                    home_base_state=state,
                    operating_states=[state] if state else [],
                ),
                source=LeadSource.FMCSA_SAFER,
                scraped_at=datetime.utcnow(),
            )

            return lead

        except Exception as e:
            print(f"Error converting carrier to lead: {e}")
            return None

    def _clean_phone(self, phone: str) -> Optional[str]:
        """Clean and validate phone number."""
        if not phone:
            return None
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        return None

    def _extract_state(self, address: Optional[str]) -> Optional[str]:
        """Extract state from address string."""
        if not address:
            return None

        # Common US state abbreviations
        states = [
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        ]

        # Look for state abbreviation
        for state in states:
            if f" {state} " in address or address.endswith(f" {state}"):
                return state

        return None

    def _state_to_timezone(self, state: Optional[str]) -> str:
        """Map state to timezone."""
        eastern = ["CT", "DE", "FL", "GA", "IN", "KY", "ME", "MD", "MA", "MI",
                   "NH", "NJ", "NY", "NC", "OH", "PA", "RI", "SC", "TN", "VT",
                   "VA", "WV"]
        central = ["AL", "AR", "IL", "IA", "KS", "LA", "MN", "MS", "MO", "NE",
                   "ND", "OK", "SD", "TX", "WI"]
        mountain = ["AZ", "CO", "ID", "MT", "NM", "UT", "WY"]
        pacific = ["CA", "NV", "OR", "WA"]

        if state in eastern:
            return "America/New_York"
        elif state in central:
            return "America/Chicago"
        elif state in mountain:
            return "America/Denver"
        elif state in pacific:
            return "America/Los_Angeles"
        return "America/Chicago"  # Default

    def _infer_equipment(
        self,
        cargo: list[str],
        operation: Optional[str],
    ) -> list[EquipmentType]:
        """Infer equipment types from cargo and operation."""
        equipment = []

        cargo_lower = " ".join(cargo).lower() if cargo else ""
        operation_lower = (operation or "").lower()

        # Refrigerated
        if any(x in cargo_lower for x in ["refrigerated", "fresh", "frozen", "produce"]):
            equipment.append(EquipmentType.REEFER)

        # Flatbed
        if any(x in cargo_lower for x in ["machinery", "building materials", "lumber", "steel"]):
            equipment.append(EquipmentType.FLATBED)

        # Tanker
        if any(x in cargo_lower for x in ["liquid", "petroleum", "chemicals"]):
            equipment.append(EquipmentType.TANKER)

        # Default to dry van for general freight
        if not equipment or "general freight" in cargo_lower:
            equipment.append(EquipmentType.DRY_VAN)

        return equipment

    def _generate_test_carriers(
        self,
        count: int,
        states: Optional[list[str]] = None,
    ) -> list[SAFERCarrierData]:
        """
        Generate realistic test carrier data for development.

        In production, this would be replaced with actual API calls.
        """
        import random

        test_states = states or ["TX", "CA", "FL", "IL", "GA", "OH", "PA", "NC", "TN", "AZ"]
        test_cities = {
            "TX": ["Houston", "Dallas", "San Antonio", "Austin"],
            "CA": ["Los Angeles", "San Francisco", "San Diego", "Fresno"],
            "FL": ["Miami", "Orlando", "Tampa", "Jacksonville"],
            "IL": ["Chicago", "Springfield", "Rockford"],
            "GA": ["Atlanta", "Savannah", "Augusta"],
            "OH": ["Columbus", "Cleveland", "Cincinnati"],
            "PA": ["Philadelphia", "Pittsburgh", "Harrisburg"],
            "NC": ["Charlotte", "Raleigh", "Greensboro"],
            "TN": ["Nashville", "Memphis", "Knoxville"],
            "AZ": ["Phoenix", "Tucson", "Mesa"],
        }

        company_prefixes = [
            "Swift", "Eagle", "Freedom", "Liberty", "Star", "American",
            "National", "United", "Express", "Direct", "First", "Prime",
            "Elite", "Alpha", "Apex", "Atlas", "Blue", "Red", "Golden",
        ]
        company_suffixes = [
            "Trucking", "Transport", "Logistics", "Freight", "Hauling",
            "Transportation", "Carriers", "Lines", "Express", "Services",
        ]

        cargo_types = [
            ["General Freight"],
            ["General Freight", "Household Goods"],
            ["Refrigerated Food", "Fresh Produce"],
            ["Building Materials", "Lumber"],
            ["Machinery", "Large Objects"],
            ["General Freight", "Paper Products"],
        ]

        carriers = []

        for i in range(count):
            state = random.choice(test_states)
            city = random.choice(test_cities.get(state, ["City"]))

            # Generate MC/DOT numbers (realistic ranges)
            mc = str(random.randint(1000000, 1500000))
            dot = str(random.randint(3000000, 4000000))

            # Random authority age (0-180 days for new authorities)
            age_days = random.randint(0, 180)
            authority_date = datetime.utcnow() - timedelta(days=age_days)

            # Generate company name
            company = f"{random.choice(company_prefixes)} {random.choice(company_suffixes)} LLC"

            # Generate phone
            area_codes = {
                "TX": ["214", "512", "713", "832"],
                "CA": ["213", "310", "415", "619"],
                "FL": ["305", "407", "813", "954"],
            }
            area = random.choice(area_codes.get(state, ["555"]))
            phone = f"{area}{random.randint(1000000, 9999999)}"

            carriers.append(
                SAFERCarrierData(
                    mc_number=mc,
                    dot_number=dot,
                    legal_name=company,
                    physical_address=f"{city}, {state}",
                    phone=phone,
                    power_units=random.choices([1, 2, 3, 5, 10], weights=[50, 25, 15, 7, 3])[0],
                    drivers=random.randint(1, 5),
                    mcs150_date=authority_date,
                    cargo_carried=random.choice(cargo_types),
                )
            )

        return carriers
