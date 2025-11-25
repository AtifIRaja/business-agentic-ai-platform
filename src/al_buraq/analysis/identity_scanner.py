"""
Cultural Intelligence Scanner

Identifies potential Muslim-owned businesses based on name patterns,
cultural markers, and community alignment indicators.

This is not a definitive classifier - it's a cultural affinity detector
to help identify potential community members for targeted outreach.
"""

import re
from dataclasses import dataclass
from typing import List, Optional
from ..models.lead import Lead


# Common Muslim/Arabic Name Patterns
MUSLIM_NAME_PATTERNS = [
    # Common names
    "muhammad", "mohammed", "mohammad", "mohamed",
    "ahmed", "ahmad", "ahmad",
    "ali", "hassan", "hussain", "hussein",
    "omar", "umar", "uthman", "osman",
    "ibrahim", "ismail", "ishmael",
    "yusuf", "yusef", "joseph",
    "abdullah", "abdul",
    "khalid", "khaled",
    "hamza", "hamzah",
    "amir", "aamir",
    "bilal", "jalal",
    "rashid", "rasheed",
    "salim", "saleem",
    "tariq", "tarik",
    "zaid", "zayd",
    "malik", "malek",
    "kareem", "karim",
    "rafiq", "rafi",
    "samir", "sameer",
    "walid", "waleed",
    "yasir", "yasser",
    "faisal", "faysal",

    # Common last names
    "khan", "shah", "sheikh", "shaikh",
    "syed", "sayyed", "sayyid",
    "malik", "ahmed", "mohammed",
    "ali", "hussain",
    "rahman", "rahim",
    "abdullah", "habib",
    "qureshi", "chaudhry", "chaudhary",
    "patel",  # Common South Asian Muslim name
    "iqbal", "javed",
    "hasan", "hakim",
    "aziz", "azeem",
    "farooq", "farouk",
    "raza", "rizvi",
    "ansari", "siddiqui",
    "mirza", "mughal",
]

# Business Name Patterns
MUSLIM_BUSINESS_MARKERS = [
    # Religious prefixes
    r"\bal[- ]",  # Al- prefix (Al-Amin, Al-Madina)
    r"^al[- ]",

    # Islamic city names
    "madina", "medina", "makkah", "mecca",
    "jeddah", "jedda",
    "damascus", "dimashq",
    "baghdad", "basra",
    "cairo", "misr",
    "istanbul", "istanbul",
    "karachi", "lahore", "islamabad",
    "dubai", "abu dhabi",
    "riyadh", "dammam",

    # Religious terms in business names
    "786",  # Bismillah numeric
    "halal", "zabiha",
    "bismillah", "basmallah",
    "islamic", "muslim",
    "masjid", "mosque",
    "jummah", "jumma",
    "ummah", "umma",
    "sunnah", "sunna",
    "deen", "din",
    "iman", "imaan",
    "sadaqah", "sadaqa",
    "baraka", "barakah",
    "hijrah", "hijra",
    "salaam", "salam",
    "shalom",  # Related

    # Arabic words
    "amanah", "amana",
    "noor", "nur",
    "shifa", "shifaa",
    "bayt", "bait",
    "dar", "darul",
    "ihsan", "ehsan",
    "khair", "khayr",
    "rizq", "rizk",
    "sabr", "sabur",
    "tawfiq", "taufiq",
]


@dataclass
class CommunityMatch:
    """Result of community affinity scan"""
    lead_id: str
    company_name: str
    owner_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    state: Optional[str]

    # Match details
    is_likely_muslim_owned: bool
    confidence_score: float  # 0.0 to 1.0
    match_reasons: List[str]
    matched_patterns: List[str]

    # Additional context
    lead_score: float
    social_verified: bool

    def __str__(self) -> str:
        confidence_pct = self.confidence_score * 100
        return (
            f"{self.company_name} ({confidence_pct:.0f}% confidence)\n"
            f"  Reasons: {', '.join(self.match_reasons[:3])}\n"
            f"  Contact: {self.email or self.phone or 'N/A'}"
        )


class IdentityScanner:
    """
    Cultural Intelligence Scanner

    Detects potential Muslim-owned businesses using name patterns
    and cultural markers for community-aligned outreach.
    """

    def __init__(self):
        self.name_patterns = MUSLIM_NAME_PATTERNS
        self.business_markers = MUSLIM_BUSINESS_MARKERS

    def _has_word_match(self, text: str, pattern: str) -> bool:
        """Check if pattern exists as a complete word in text"""
        # Use word boundaries for better matching
        word_pattern = r'\b' + re.escape(pattern) + r'\b'
        return bool(re.search(word_pattern, text, re.IGNORECASE))

    def scan_lead(self, lead: Lead) -> Optional[CommunityMatch]:
        """
        Scan a single lead for cultural affinity markers.

        Returns CommunityMatch if potential match found, None otherwise.
        """
        match_reasons = []
        matched_patterns = []
        confidence = 0.0

        # Check company name
        company_lower = lead.company_name.lower()

        # Check for business markers in company name
        for marker in self.business_markers:
            if isinstance(marker, str):
                # Use word boundary for string markers
                if self._has_word_match(company_lower, marker):
                    match_reasons.append(f"Company name contains '{marker}'")
                    matched_patterns.append(marker)
                    confidence += 0.4
            else:
                # Regex pattern (already has proper boundaries)
                if re.search(marker, company_lower):
                    match_reasons.append("Company name has Islamic prefix/pattern")
                    matched_patterns.append(str(marker))
                    confidence += 0.5

        # Check for Muslim names in company name (with word boundaries)
        for name in self.name_patterns:
            if self._has_word_match(company_lower, name):
                match_reasons.append(f"Company name contains '{name}'")
                matched_patterns.append(name)
                confidence += 0.35

        # Check owner name if available
        if lead.owner_name:
            owner_lower = lead.owner_name.lower()
            for name in self.name_patterns:
                if self._has_word_match(owner_lower, name):
                    match_reasons.append(f"Owner name contains '{name}'")
                    matched_patterns.append(name)
                    confidence += 0.45

        # Check email domain
        if lead.contact.email:
            email_lower = lead.contact.email.lower()
            email_local = email_lower.split('@')[0] if '@' in email_lower else email_lower

            for name in self.name_patterns:
                # For email, we can be slightly less strict
                if name in email_local:
                    match_reasons.append(f"Email contains '{name}'")
                    matched_patterns.append(name)
                    confidence += 0.25

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        # Only return match if we found something
        if not match_reasons:
            return None

        return CommunityMatch(
            lead_id=lead.id,
            company_name=lead.company_name,
            owner_name=lead.owner_name,
            email=lead.contact.email,
            phone=lead.contact.phone_primary,
            state=lead.fleet.home_base_state,
            is_likely_muslim_owned=confidence >= 0.3,
            confidence_score=confidence,
            match_reasons=match_reasons,
            matched_patterns=matched_patterns,
            lead_score=lead.lead_score,
            social_verified=lead.social_verified,
        )

    def scan_leads(self, leads: List[Lead]) -> List[CommunityMatch]:
        """
        Scan a list of leads for cultural affinity markers.

        Returns list of CommunityMatch objects, sorted by confidence.
        """
        matches = []

        for lead in leads:
            match = self.scan_lead(lead)
            if match and match.is_likely_muslim_owned:
                matches.append(match)

        # Sort by confidence score (highest first)
        matches.sort(key=lambda m: m.confidence_score, reverse=True)

        return matches

    def get_stats(self, matches: List[CommunityMatch]) -> dict:
        """Get summary statistics for a set of matches"""
        if not matches:
            return {
                "total_matches": 0,
                "high_confidence": 0,
                "medium_confidence": 0,
                "low_confidence": 0,
                "avg_confidence": 0.0,
                "social_verified_count": 0,
            }

        high_conf = sum(1 for m in matches if m.confidence_score >= 0.7)
        medium_conf = sum(1 for m in matches if 0.4 <= m.confidence_score < 0.7)
        low_conf = sum(1 for m in matches if m.confidence_score < 0.4)
        avg_conf = sum(m.confidence_score for m in matches) / len(matches)
        social_verified = sum(1 for m in matches if m.social_verified)

        return {
            "total_matches": len(matches),
            "high_confidence": high_conf,
            "medium_confidence": medium_conf,
            "low_confidence": low_conf,
            "avg_confidence": avg_conf,
            "social_verified_count": social_verified,
        }
