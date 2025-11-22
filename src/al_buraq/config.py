"""Configuration management for Al-Buraq dispatch system."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ==========================================================================
    # Application
    # ==========================================================================
    APP_NAME: str = "Al-Buraq Dispatch"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ==========================================================================
    # AI Providers
    # ==========================================================================
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API key")
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # ==========================================================================
    # Database
    # ==========================================================================
    DATABASE_URL: str = "sqlite:///data/alburaq.db"

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION: str = "alburaq"
    CHROMA_PERSIST_DIR: str = "data/chroma"

    # ==========================================================================
    # Communication (Sales Agent - Future)
    # ==========================================================================
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    SENDGRID_API_KEY: Optional[str] = None

    # ==========================================================================
    # Load Boards (Future)
    # ==========================================================================
    DAT_API_KEY: Optional[str] = None
    DAT_API_SECRET: Optional[str] = None
    DAT_BASE_URL: str = "https://api.dat.com"

    TRUCKSTOP_API_KEY: Optional[str] = None

    # ==========================================================================
    # Business Rules (from MISSION.md)
    # ==========================================================================
    # Rate thresholds
    MIN_RATE_PER_MILE: float = 2.00  # Absolute floor - never accept below
    SOFT_FLOOR_RATE: float = 2.25  # Negotiate harder below this
    TARGET_RATE_PER_MILE: float = 2.75  # Optimal target

    # Commission structure
    COMMISSION_RATE: float = 0.07  # 7% standard
    COMMISSION_RATE_PREMIUM: float = 0.08  # 8% full service

    # Charity allocation (Zakat + Sadaqah)
    CHARITY_PERCENTAGE: float = 0.05  # 5% of profit to charity

    # Lead scoring
    LEAD_QUALIFICATION_THRESHOLD: float = 0.6  # Minimum score to qualify

    # Deadhead limits
    MAX_DEADHEAD_MILES: int = 150
    MAX_DEADHEAD_RATIO: float = 0.30  # 30% of loaded miles

    # Insurance minimums (from MISSION.md)
    MIN_LIABILITY_COVERAGE: int = 1_000_000  # $1M
    MIN_CARGO_COVERAGE: int = 100_000  # $100K

    # ==========================================================================
    # Hunter Agent Settings
    # ==========================================================================
    HUNTER_BATCH_SIZE: int = 50  # Leads to process per batch
    HUNTER_RATE_LIMIT_DELAY: float = 1.0  # Seconds between requests
    HUNTER_MAX_AUTHORITY_AGE_DAYS: int = 730  # 2 years max

    # ==========================================================================
    # Paths
    # ==========================================================================
    @property
    def data_dir(self) -> Path:
        """Get or create data directory."""
        path = Path("data")
        path.mkdir(exist_ok=True)
        return path

    @property
    def logs_dir(self) -> Path:
        """Get or create logs directory."""
        path = Path("logs")
        path.mkdir(exist_ok=True)
        return path

    @property
    def db_path(self) -> Path:
        """Get database file path."""
        # Extract path from DATABASE_URL (sqlite:///path/to/db)
        if self.DATABASE_URL.startswith("sqlite:///"):
            return Path(self.DATABASE_URL.replace("sqlite:///", ""))
        return self.data_dir / "alburaq.db"

    # ==========================================================================
    # Validation
    # ==========================================================================
    def validate_ai_keys(self) -> bool:
        """Check if AI API keys are configured."""
        return bool(self.OPENAI_API_KEY)

    def validate_communication_keys(self) -> bool:
        """Check if communication API keys are configured."""
        return bool(self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience alias
settings = get_settings()


# ==========================================================================
# Haram Keywords (from MISSION.md)
# ==========================================================================
HARAM_KEYWORDS: set[str] = {
    # Alcohol
    "alcohol", "beer", "wine", "liquor", "spirits", "vodka", "whiskey",
    "whisky", "rum", "gin", "tequila", "brandy", "bourbon", "scotch",
    "champagne", "malt beverage", "hard seltzer", "cider", "sake",
    "moonshine", "absinthe", "vermouth", "schnapps",

    # Pork
    "pork", "bacon", "ham", "swine", "pig", "sausage", "pepperoni",
    "prosciutto", "salami", "chorizo", "lard", "pork rinds",
    "carnitas", "pancetta",

    # Tobacco & Drugs
    "tobacco", "cigarette", "cigar", "vape", "e-cigarette", "nicotine",
    "cannabis", "marijuana", "weed", "thc", "cbd", "hemp flower",
    "delta-8", "delta-9", "edibles",

    # Gambling
    "gambling", "casino", "slot machine", "lottery", "betting",
    "poker machine", "gaming machine",

    # Adult Content
    "adult entertainment", "xxx", "pornography", "erotic",
    "adult novelty", "sex toy",

    # Weapons (civilian sales)
    "ammunition", "ammo", "firearms", "guns", "rifles", "pistols",
    "handguns", "shotguns", "assault rifle",
}

# Keywords requiring manual review
REVIEW_KEYWORDS: set[str] = {
    "meat", "sausage", "hot dog", "deli", "processed meat",
    "gelatin", "enzyme", "animal product", "rennet",
    "marshmallow", "gummy", "candy",
}

# Explicitly halal commodities
HALAL_COMMODITIES: set[str] = {
    "produce", "vegetables", "fruits", "grains", "rice", "wheat",
    "flour", "sugar", "salt", "spices", "coffee", "tea",
    "electronics", "furniture", "appliances", "machinery", "equipment",
    "paper", "plastic", "steel", "lumber", "building materials",
    "automotive parts", "tires", "medical supplies", "pharmaceuticals",
    "clothing", "textiles", "toys", "books", "office supplies",
    "cleaning supplies", "bottled water", "soft drinks", "juice",
}

# Target equipment types for dispatch
TARGET_EQUIPMENT: set[str] = {
    "dry_van", "reefer", "flatbed", "step_deck"
}

# Target operating states
TARGET_STATES: set[str] = {
    "TX", "CA", "FL", "IL", "GA", "OH", "PA", "NY", "NC", "TN",
    "AZ", "NJ", "MI", "IN", "MO", "WI", "MN", "CO", "AL", "LA",
    "SC", "KY", "OK", "WA", "OR", "NV", "VA", "MD", "MA", "CT",
}
