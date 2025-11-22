"""
CSV Hunter - Import leads from FMCSA CSV files.

Handles large CSV files (279MB+) efficiently using chunked reading.
Supports fuzzy column name matching for messy/unstructured data.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterator, Callable
from dataclasses import dataclass, field

import pandas as pd

from .base_hunter import BaseHunter, HuntResult
from ..models.lead import Lead, ContactInfo, AuthorityInfo, InsuranceInfo, FleetInfo
from ..models.enums import LeadSource, EquipmentType
from ..db import Repository, VectorStore
from ..scoring import LeadScorer


@dataclass
class ColumnMapping:
    """Mapping of CSV columns to Lead fields."""

    # Required fields
    mc_number: Optional[str] = None
    dot_number: Optional[str] = None
    legal_name: Optional[str] = None

    # Contact info
    phone: Optional[str] = None
    email: Optional[str] = None

    # Address
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None

    # Optional fields
    dba_name: Optional[str] = None
    owner_name: Optional[str] = None
    power_units: Optional[str] = None
    drivers: Optional[str] = None

    # Authority dates
    authority_granted: Optional[str] = None
    mcs150_date: Optional[str] = None

    # Insurance
    liability_insurance: Optional[str] = None
    cargo_insurance: Optional[str] = None

    # Cargo/Equipment
    cargo_carried: Optional[str] = None
    operation_type: Optional[str] = None


# Column name patterns for fuzzy matching
# IMPORTANT: Order matters! More specific patterns should come first.
COLUMN_PATTERNS = {
    # MC/DOT Numbers - be careful not to match MCS150
    "mc_number": [r"^mc[\s_-]?(number|#|num)$", r"^mc$", r"motor[\s_-]?carrier[\s_-]?num"],
    "dot_number": [r"dot[\s_-]?(number|#|num)?", r"usdot", r"^dot$", r"^dot_number$"],

    # Names
    "legal_name": [r"legal[\s_-]?name", r"company[\s_-]?name", r"carrier[\s_-]?name", r"^name$"],
    "dba_name": [r"dba[\s_-]?(name)?", r"doing[\s_-]?business", r"trade[\s_-]?name"],
    "owner_name": [r"owner[\s_-]?(name)?", r"contact[\s_-]?name", r"principal"],

    # Contact - email pattern must NOT match "mailing"
    "phone": [r"phone", r"telephone", r"tel[\s_-]?(number)?", r"contact[\s_-]?phone"],
    "email": [r"email[\s_-]?address", r"^email$", r"^e[\s_-]?mail$", r"email_address"],

    # Physical Address - be careful with "mailing" vs "mail"
    "street": [r"phy[\s_-]?street", r"physical[\s_-]?street", r"street[\s_-]?address"],
    "city": [r"phy[\s_-]?city", r"physical[\s_-]?city", r"^city$"],
    "state": [r"phy[\s_-]?state", r"physical[\s_-]?state", r"^state$", r"oic[\s_-]?state"],
    "zip_code": [r"phy[\s_-]?zip", r"physical[\s_-]?zip", r"zip[\s_-]?code", r"postal"],

    # Fleet info
    "power_units": [r"power[\s_-]?units?", r"nbr[\s_-]?power", r"trucks?", r"tractors?"],
    "drivers": [r"driver[\s_-]?total", r"drivers?", r"nbr[\s_-]?drivers?"],

    # Authority/Dates
    "authority_granted": [r"authority[\s_-]?granted", r"common[\s_-]?auth", r"auth[\s_-]?date"],
    "mcs150_date": [r"mcs[\s_-]?150[\s_-]?date", r"^mcs150_date$", r"mcs150"],

    # Insurance
    "liability_insurance": [r"liab(ility)?[\s_-]?(insurance|ins|coverage)?", r"bipd"],
    "cargo_insurance": [r"cargo[\s_-]?(insurance|ins|coverage)?"],

    # Operations
    "cargo_carried": [r"cargo[\s_-]?carried", r"commodity", r"freight[\s_-]?type"],
    "operation_type": [r"operation[\s_-]?(type|class)", r"carrier[\s_-]?operation"],
}


class CSVHunter(BaseHunter):
    """
    Hunter that imports leads from FMCSA CSV files.

    Features:
    - Chunked reading for large files (279MB+)
    - Fuzzy column name matching
    - Email-required filtering
    - Automatic scoring and qualification
    """

    def __init__(
        self,
        repository: Optional[Repository] = None,
        vector_store: Optional[VectorStore] = None,
        scorer: Optional[LeadScorer] = None,
    ):
        super().__init__(source_name="CSV_IMPORT")
        self.repository = repository
        self.vector_store = vector_store
        self.scorer = scorer or LeadScorer()

    def detect_columns(self, df: pd.DataFrame) -> ColumnMapping:
        """
        Auto-detect column mappings using fuzzy matching.

        Args:
            df: DataFrame with columns to analyze

        Returns:
            ColumnMapping with detected column names
        """
        mapping = ColumnMapping()
        columns_lower = {col.lower().strip(): col for col in df.columns}

        for field_name, patterns in COLUMN_PATTERNS.items():
            for col_lower, col_original in columns_lower.items():
                for pattern in patterns:
                    if re.search(pattern, col_lower, re.IGNORECASE):
                        setattr(mapping, field_name, col_original)
                        break
                if getattr(mapping, field_name):
                    break

        return mapping

    def _get_value(self, row: pd.Series, col_name: Optional[str], default: str = "") -> str:
        """Safely get a value from a row."""
        if col_name is None or col_name not in row.index:
            return default
        val = row[col_name]
        if pd.isna(val):
            return default
        return str(val).strip()

    def _get_int(self, row: pd.Series, col_name: Optional[str], default: int = 1) -> int:
        """Safely get an integer from a row."""
        val = self._get_value(row, col_name)
        if not val:
            return default
        try:
            # Handle values like "1.0" or "10"
            return int(float(val))
        except (ValueError, TypeError):
            return default

    def _clean_phone(self, phone: str) -> Optional[str]:
        """Clean and validate phone number."""
        if not phone:
            return None
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        elif len(digits) >= 10:
            # Take last 10 digits
            return f"+1{digits[-10:]}"
        return None

    def _clean_email(self, email: str) -> Optional[str]:
        """Clean and validate email."""
        if not email:
            return None
        email = email.strip().lower()
        # Basic email validation
        if re.match(r"^[\w\.\-\+]+@[\w\.\-]+\.\w{2,}$", email):
            return email
        return None

    def _clean_mc_dot(self, value: str) -> Optional[str]:
        """Clean MC/DOT number."""
        if not value:
            return None
        # Remove non-digits
        digits = re.sub(r"\D", "", value)
        return digits if digits else None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        if not date_str:
            return None

        # Common FMCSA date formats
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d-%b-%Y",
            "%Y%m%d",
            "%m-%d-%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _infer_equipment(self, cargo_str: str, operation_str: str) -> list[EquipmentType]:
        """Infer equipment types from cargo and operation strings."""
        equipment = []
        combined = f"{cargo_str} {operation_str}".lower()

        if any(x in combined for x in ["refrigerated", "reefer", "frozen", "fresh", "produce", "meat"]):
            equipment.append(EquipmentType.REEFER)
        if any(x in combined for x in ["flatbed", "flat bed", "machinery", "steel", "lumber", "building"]):
            equipment.append(EquipmentType.FLATBED)
        if any(x in combined for x in ["tanker", "tank", "liquid", "petroleum", "fuel", "chemical"]):
            equipment.append(EquipmentType.TANKER)
        if any(x in combined for x in ["auto", "car hauler", "vehicle"]):
            equipment.append(EquipmentType.CAR_HAULER)

        # Default to dry van for general freight
        if not equipment or "general" in combined or "freight" in combined:
            equipment.append(EquipmentType.DRY_VAN)

        return equipment

    def row_to_lead(self, row: pd.Series, mapping: ColumnMapping) -> Optional[Lead]:
        """
        Convert a CSV row to a Lead object.

        Args:
            row: DataFrame row
            mapping: Column mapping

        Returns:
            Lead object or None if invalid
        """
        # Get required fields
        mc_number = self._clean_mc_dot(self._get_value(row, mapping.mc_number))
        dot_number = self._clean_mc_dot(self._get_value(row, mapping.dot_number))
        legal_name = self._get_value(row, mapping.legal_name)
        email = self._clean_email(self._get_value(row, mapping.email))
        phone = self._clean_phone(self._get_value(row, mapping.phone))

        # Skip if missing critical data
        if not mc_number and not dot_number:
            return None
        if not legal_name:
            return None
        if not email:  # Email required per user request
            return None
        if not phone:
            return None

        # Use DOT as MC if MC missing (or vice versa)
        mc_number = mc_number or dot_number
        dot_number = dot_number or mc_number

        # Get optional fields
        dba_name = self._get_value(row, mapping.dba_name) or None
        owner_name = self._get_value(row, mapping.owner_name) or None
        city = self._get_value(row, mapping.city)
        state = self._get_value(row, mapping.state)
        power_units = self._get_int(row, mapping.power_units, 1)
        drivers = self._get_int(row, mapping.drivers, 1)

        # Parse dates
        authority_date = self._parse_date(self._get_value(row, mapping.authority_granted))
        mcs150_date = self._parse_date(self._get_value(row, mapping.mcs150_date))
        # Use most recent date available
        grant_date = authority_date or mcs150_date or datetime.utcnow()

        # Parse insurance (try to extract numeric values)
        liability = 0
        cargo = 0
        liability_str = self._get_value(row, mapping.liability_insurance)
        cargo_str = self._get_value(row, mapping.cargo_insurance)

        if liability_str:
            # Extract numbers, handle formats like "1,000,000" or "1000000"
            nums = re.findall(r"[\d,]+", liability_str)
            if nums:
                try:
                    liability = int(nums[0].replace(",", ""))
                except ValueError:
                    pass

        if cargo_str:
            nums = re.findall(r"[\d,]+", cargo_str)
            if nums:
                try:
                    cargo = int(nums[0].replace(",", ""))
                except ValueError:
                    pass

        # Default insurance if not found (assume minimums for active authority)
        if liability == 0:
            liability = 1_000_000  # Assume minimum for active carriers
        if cargo == 0:
            cargo = 100_000

        # Infer equipment
        cargo_carried = self._get_value(row, mapping.cargo_carried)
        operation_type = self._get_value(row, mapping.operation_type)
        equipment = self._infer_equipment(cargo_carried, operation_type)

        # Clean state code
        if state:
            state = state.upper()[:2]

        try:
            lead = Lead(
                company_name=legal_name,
                dba_name=dba_name,
                legal_name=legal_name,
                owner_name=owner_name,
                contact=ContactInfo(
                    phone_primary=phone,
                    email=email,
                    timezone=self._state_to_timezone(state),
                ),
                authority=AuthorityInfo(
                    mc_number=mc_number,
                    dot_number=dot_number,
                    authority_status="ACTIVE",
                    authority_granted_date=grant_date,
                    common_authority=True,
                ),
                insurance=InsuranceInfo(
                    liability_coverage=liability,
                    cargo_coverage=cargo,
                ),
                fleet=FleetInfo(
                    truck_count=power_units,
                    driver_count=drivers,
                    equipment_types=equipment,
                    home_base_city=city or None,
                    home_base_state=state or None,
                    operating_states=[state] if state else [],
                ),
                source=LeadSource.FMCSA_SAFER,
                scraped_at=datetime.utcnow(),
            )
            return lead
        except Exception as e:
            # Invalid data, skip this row
            return None

    def _state_to_timezone(self, state: Optional[str]) -> str:
        """Map state to timezone."""
        if not state:
            return "America/Chicago"

        eastern = {"CT", "DE", "FL", "GA", "IN", "KY", "ME", "MD", "MA", "MI",
                   "NH", "NJ", "NY", "NC", "OH", "PA", "RI", "SC", "TN", "VT",
                   "VA", "WV"}
        central = {"AL", "AR", "IL", "IA", "KS", "LA", "MN", "MS", "MO", "NE",
                   "ND", "OK", "SD", "TX", "WI"}
        mountain = {"AZ", "CO", "ID", "MT", "NM", "UT", "WY"}
        pacific = {"CA", "NV", "OR", "WA"}

        if state in eastern:
            return "America/New_York"
        elif state in central:
            return "America/Chicago"
        elif state in mountain:
            return "America/Denver"
        elif state in pacific:
            return "America/Los_Angeles"
        return "America/Chicago"

    async def hunt(
        self,
        limit: int = 50,
        **kwargs,
    ) -> HuntResult:
        """Not used for CSV import - use import_csv instead."""
        return HuntResult(source=self.source_name)

    async def hunt_stream(self, limit: int = 50, **kwargs):
        """Not used for CSV import."""
        return
        yield  # Make it a generator

    def import_csv(
        self,
        filepath: str | Path,
        limit: Optional[int] = None,
        chunk_size: int = 1000,
        require_email: bool = True,
        save_to_db: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> HuntResult:
        """
        Import leads from a CSV file.

        Args:
            filepath: Path to CSV file
            limit: Maximum leads to import (None = all)
            chunk_size: Rows to process at a time (for memory efficiency)
            require_email: Skip rows without email
            save_to_db: Save leads to database
            progress_callback: Called with (processed, found) counts

        Returns:
            HuntResult with imported leads
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"CSV file not found: {filepath}")

        result = HuntResult(source=self.source_name)

        # Read first chunk to detect columns
        first_chunk = pd.read_csv(filepath, nrows=100, low_memory=False)
        mapping = self.detect_columns(first_chunk)

        # Log detected columns
        detected = {k: v for k, v in mapping.__dict__.items() if v is not None}
        print(f"Detected column mappings: {detected}")

        if not mapping.mc_number and not mapping.dot_number:
            result.errors.append("Could not detect MC or DOT number column")
            return result.complete()

        if not mapping.email:
            result.errors.append("Could not detect email column")
            if require_email:
                return result.complete()

        # Process file in chunks
        leads_found = 0
        rows_processed = 0
        duplicates = 0

        for chunk in pd.read_csv(filepath, chunksize=chunk_size, low_memory=False):
            for _, row in chunk.iterrows():
                rows_processed += 1

                # Check limit
                if limit and leads_found >= limit:
                    break

                # Convert row to lead
                lead = self.row_to_lead(row, mapping)
                if lead is None:
                    continue

                # Check for duplicates
                if save_to_db and self.repository:
                    existing = self.repository.get_lead_by_mc(lead.authority.mc_number)
                    if existing:
                        duplicates += 1
                        continue

                # Score and qualify
                self.scorer.qualify_lead(lead)

                # Save to database
                if save_to_db and self.repository:
                    try:
                        self.repository.save_lead(lead)
                        if self.vector_store:
                            self.vector_store.add_lead(lead)
                    except Exception as e:
                        result.errors.append(f"DB error for MC {lead.authority.mc_number}: {e}")
                        continue

                result.leads.append(lead)
                leads_found += 1

                # Progress callback
                if progress_callback:
                    progress_callback(rows_processed, leads_found)

            # Check limit after chunk
            if limit and leads_found >= limit:
                break

        result.total_found = leads_found
        result.total_processed = rows_processed
        result.total_duplicates = duplicates

        return result.complete()

    def preview_csv(
        self,
        filepath: str | Path,
        rows: int = 5,
    ) -> dict:
        """
        Preview a CSV file and show detected columns.

        Args:
            filepath: Path to CSV file
            rows: Number of rows to preview

        Returns:
            Dict with columns, mapping, and sample data
        """
        filepath = Path(filepath)
        df = pd.read_csv(filepath, nrows=rows, low_memory=False)
        mapping = self.detect_columns(df)

        return {
            "columns": list(df.columns),
            "mapping": {k: v for k, v in mapping.__dict__.items() if v is not None},
            "unmapped": [k for k, v in mapping.__dict__.items() if v is None],
            "sample_rows": df.head(rows).to_dict(orient="records"),
            "total_columns": len(df.columns),
        }
