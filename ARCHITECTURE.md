# Al-Buraq System Architecture

> **Level 5 Agentic AI** - Fully autonomous dispatch operations with human oversight

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AL-BURAQ DISPATCH BRAIN                           │
│                         (Central Orchestration Layer)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│    │   HUNTER     │    │    SALES     │    │   DISPATCH   │                │
│    │   AGENT      │    │    AGENT     │    │    AGENT     │                │
│    │              │    │              │    │              │                │
│    │ Lead Gen &   │───▶│ Outbound     │───▶│ Load Match   │                │
│    │ Prospecting  │    │ Calls/Email  │    │ & Booking    │                │
│    └──────────────┘    └──────────────┘    └──────────────┘                │
│           │                   │                   │                        │
│           ▼                   ▼                   ▼                        │
│    ┌─────────────────────────────────────────────────────┐                 │
│    │              SHARED MEMORY (ChromaDB)               │                 │
│    │  Carriers │ Brokers │ Loads │ Conversations │ Rates │                 │
│    └─────────────────────────────────────────────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │   MCP       │ │   External  │ │   Human     │
            │   Servers   │ │   APIs      │ │   Dashboard │
            └─────────────┘ └─────────────┘ └─────────────┘
```

---

## Agent Hierarchy

### Level 5 Autonomy Breakdown

| Level | Capability | Al-Buraq Implementation |
|-------|------------|------------------------|
| L1 | Task Execution | Execute single commands |
| L2 | Task Planning | Break down complex tasks |
| L3 | Goal Pursuit | Pursue objectives autonomously |
| L4 | Strategy Formation | Develop and adapt strategies |
| **L5** | **Full Autonomy** | **Self-directed operation with ethical constraints** |

---

## Agent Specifications

### 1. Hunter Agent (Lead Generation)

**Purpose:** Find and qualify potential carrier partners (owner-operators, small fleets)

**Capabilities:**
- Web scraping for new MC authorities
- Load board monitoring (DAT, Truckstop, etc.)
- Social media prospecting (Facebook trucking groups)
- SAFER/FMCSA database queries
- Lead scoring and qualification

**Input Sources:**
```python
HUNTER_DATA_SOURCES = [
    "FMCSA_SAFER_API",      # New MC authorities
    "DAT_LOAD_BOARD",        # Active carriers
    "TRUCKING_FACEBOOK_GROUPS",
    "LINKEDIN_TRUCKER_PROFILES",
    "CARRIER_DIRECTORIES"
]
```

**Output Schema:**
```python
@dataclass
class QualifiedLead:
    mc_number: str
    dot_number: str
    company_name: str
    owner_name: str
    phone: str
    email: Optional[str]
    truck_count: int
    equipment_types: List[str]
    operating_lanes: List[str]
    authority_age_days: int
    insurance_verified: bool
    lead_score: float  # 0.0 - 1.0
    source: str
    scraped_at: datetime
```

**Ethical Constraints:**
- Only contact carriers who publicly list their information
- Respect opt-out requests immediately
- No deceptive scraping (proper User-Agent headers)
- Rate limit to avoid overloading sources

---

### 2. Sales Agent (Outreach & Conversion)

**Purpose:** Convert qualified leads into active carrier partners

**Capabilities:**
- Outbound voice calls (AI voice with disclosure)
- Email campaigns (personalized sequences)
- SMS follow-ups (with consent)
- Objection handling
- Contract negotiation
- Onboarding initiation

**Communication Modes:**
```python
class CommunicationChannel(Enum):
    VOICE_CALL = "voice"      # Primary - AI voice with Twilio/Bland.ai
    EMAIL = "email"           # Secondary - templated + personalized
    SMS = "sms"               # Follow-up only (with consent)
    WHATSAPP = "whatsapp"     # International carriers
```

**Conversation Flow:**
```
┌─────────────────┐
│  Initial Call   │
│  (Introduction) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Qualify Need   │────▶│   Not Ready     │──▶ Schedule Follow-up
│  (Pain Points)  │     │   (Nurture)     │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  Present Offer  │
│  (7-8% Model)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Handle Objects  │────▶│    Lost Lead    │──▶ Log Reason & Exit
│                 │     │                 │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│    Close &      │
│   Onboard       │
└─────────────────┘
```

**Objection Handling Matrix:**
```python
OBJECTION_RESPONSES = {
    "already_have_dispatcher": {
        "response": "I understand. Many of our best carriers started the same way. "
                   "We focus on finding loads others miss. Can I show you one lane "
                   "where we consistently beat market rates?",
        "next_action": "offer_trial_load"
    },
    "commission_too_high": {
        "response": "Our 7% covers everything - no hidden fees. We also find loads "
                   "averaging $0.25-0.50 more per mile than self-dispatch. "
                   "Would you like to see our rate history for your lanes?",
        "next_action": "show_rate_comparison"
    },
    "bad_experience_before": {
        "response": "I'm sorry to hear that. What specifically went wrong? "
                   "We operate on full transparency - you see every load and rate "
                   "before accepting. Can we earn your trust with one trial load?",
        "next_action": "address_specific_concern"
    }
}
```

**Ethical Constraints:**
- Always disclose AI nature when asked
- No pressure tactics or false urgency
- Respect "Do Not Call" requests instantly
- Record all calls (with consent) for quality/compliance

---

### 3. Dispatch Agent (Load Matching & Booking)

**Purpose:** Match carriers with optimal loads and manage booking lifecycle

**Capabilities:**
- Real-time load board monitoring
- Rate analysis and negotiation
- Load-to-truck matching algorithm
- Booking and confirmation
- Shipment tracking
- Issue resolution

**Matching Algorithm:**
```python
def calculate_load_score(load: Load, carrier: Carrier) -> float:
    """
    Score a load for a specific carrier (0.0 - 1.0)
    Higher = Better Match
    """
    score = 0.0

    # Distance efficiency (40% weight)
    deadhead_ratio = load.deadhead_miles / load.loaded_miles
    if deadhead_ratio < 0.1:
        score += 0.40
    elif deadhead_ratio < 0.2:
        score += 0.30
    elif deadhead_ratio < 0.3:
        score += 0.20

    # Rate quality (35% weight)
    rate_per_mile = load.rate / load.loaded_miles
    if rate_per_mile >= 3.00:
        score += 0.35
    elif rate_per_mile >= 2.50:
        score += 0.28
    elif rate_per_mile >= 2.00:
        score += 0.20

    # Lane familiarity (15% weight)
    if load.lane in carrier.preferred_lanes:
        score += 0.15
    elif load.origin_state in carrier.home_states:
        score += 0.10

    # Schedule fit (10% weight)
    if load.pickup_window_fits(carrier.availability):
        score += 0.10

    return score
```

**Booking Workflow:**
```
┌─────────────────┐
│  Load Sourced   │
│  (Load Board)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Halal Check     │──▶ REJECT if haram commodity
│ (Commodity)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Rate Analysis  │──▶ SKIP if below $2/mile floor
│  (Min Threshold)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Carrier Match  │──▶ Find best available truck
│  (Algorithm)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Carrier Accept │──▶ Present load to carrier
│  (Confirmation) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Book with      │──▶ Confirm with broker
│  Broker         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Rate Con &     │──▶ Generate documents
│  Dispatch       │
└─────────────────┘
```

---

## Data Architecture

### ChromaDB Collections

```python
VECTOR_COLLECTIONS = {
    "carriers": {
        "description": "Carrier profiles and preferences",
        "embedding_model": "text-embedding-3-small",
        "metadata_fields": ["mc_number", "equipment", "lanes", "rating"]
    },
    "brokers": {
        "description": "Broker relationships and history",
        "embedding_model": "text-embedding-3-small",
        "metadata_fields": ["mc_number", "avg_rate", "payment_terms", "reliability"]
    },
    "loads": {
        "description": "Historical load data for rate prediction",
        "embedding_model": "text-embedding-3-small",
        "metadata_fields": ["lane", "rate_per_mile", "commodity", "date"]
    },
    "conversations": {
        "description": "Call/email transcripts for context",
        "embedding_model": "text-embedding-3-small",
        "metadata_fields": ["carrier_id", "type", "outcome", "date"]
    }
}
```

### Relational Data (SQLite/PostgreSQL)

```python
# Core Tables
TABLES = {
    "carriers": "Carrier master data",
    "brokers": "Broker master data",
    "loads": "Load/shipment records",
    "bookings": "Confirmed bookings",
    "calls": "Call logs and transcripts",
    "payments": "Commission tracking",
    "charity": "Zakat/Sadaqah distributions"
}
```

---

## MCP Server Architecture

### Custom MCP Servers Required

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP SERVER LAYER                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ LoadBoard   │  │  Telephony  │  │   FMCSA     │         │
│  │ MCP Server  │  │ MCP Server  │  │ MCP Server  │         │
│  │             │  │             │  │             │         │
│  │ - DAT API   │  │ - Twilio    │  │ - SAFER     │         │
│  │ - Truckstop │  │ - Bland.ai  │  │ - CSA Data  │         │
│  │ - Direct    │  │ - SendGrid  │  │ - Insurance │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Document   │  │   Payment   │  │   Charity   │         │
│  │ MCP Server  │  │ MCP Server  │  │ MCP Server  │         │
│  │             │  │             │  │             │         │
│  │ - Rate Cons │  │ - Factoring │  │ - Track %   │         │
│  │ - BOLs      │  │ - Invoicing │  │ - Distribute│         │
│  │ - Contracts │  │ - Commission│  │ - Report    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### MCP Server Specifications

```python
# mcp_servers/loadboard/server.py
MCP_LOADBOARD = {
    "name": "loadboard-mcp",
    "tools": [
        "search_loads",       # Query available loads
        "get_load_details",   # Full load information
        "book_load",          # Confirm booking
        "get_rate_history",   # Historical rates for lane
        "post_truck"          # Post available capacity
    ],
    "resources": [
        "loads://active",     # Stream of available loads
        "rates://market"      # Market rate data
    ]
}

# mcp_servers/telephony/server.py
MCP_TELEPHONY = {
    "name": "telephony-mcp",
    "tools": [
        "make_call",          # Initiate outbound call
        "send_sms",           # Send text message
        "send_email",         # Send email
        "get_call_transcript",# Retrieve call recording/transcript
        "schedule_callback"   # Schedule future call
    ]
}

# mcp_servers/fmcsa/server.py
MCP_FMCSA = {
    "name": "fmcsa-mcp",
    "tools": [
        "verify_authority",   # Check MC/DOT status
        "get_safety_rating",  # CSA scores
        "verify_insurance",   # Insurance coverage
        "get_carrier_history" # Inspection/crash history
    ]
}
```

---

## API Integrations

### External Services

| Service | Purpose | Priority |
|---------|---------|----------|
| OpenAI API | GPT-4 for reasoning, embeddings | Critical |
| Anthropic API | Claude for complex decisions | Critical |
| Twilio | Voice calls, SMS | High |
| Bland.ai | AI voice conversations | High |
| SendGrid | Transactional email | High |
| DAT API | Load board access | High |
| FMCSA SAFER | Carrier verification | High |
| ChromaDB | Vector memory | Critical |
| Stripe | Payment processing | Medium |

### API Configuration

```python
# config/apis.py
from pydantic_settings import BaseSettings

class APISettings(BaseSettings):
    # AI Providers
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str

    # Communication
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str
    SENDGRID_API_KEY: str

    # Load Boards
    DAT_API_KEY: str
    DAT_API_SECRET: str

    # Database
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    DATABASE_URL: str = "sqlite:///alburaq.db"

    class Config:
        env_file = ".env"
```

---

## Security Architecture

### Authentication & Authorization

```python
class SecurityLayers:
    # API Key rotation every 30 days
    API_KEY_ROTATION_DAYS = 30

    # Rate limiting
    RATE_LIMITS = {
        "calls_per_minute": 10,
        "emails_per_hour": 100,
        "api_requests_per_minute": 60
    }

    # PII Encryption
    ENCRYPTION_ALGORITHM = "AES-256-GCM"
    KEY_DERIVATION = "PBKDF2-SHA256"
```

### Data Classification

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| MC/DOT Numbers | Public | Standard storage |
| Phone/Email | PII | Encrypted at rest |
| Call Recordings | Sensitive | Encrypted, 90-day retention |
| Financial Data | Confidential | Encrypted, access logged |
| Contracts | Confidential | Encrypted, versioned |

---

## Deployment Architecture

### Development Environment

```
Local Machine (Windows)
├── Python 3.12 + venv
├── ChromaDB (Docker)
├── SQLite (local)
├── MCP Servers (local processes)
└── Claude Code CLI
```

### Production Environment (Future)

```
AWS/GCP Cloud
├── ECS/Cloud Run (Agent containers)
├── RDS PostgreSQL (relational data)
├── ChromaDB Cloud (vector storage)
├── Lambda/Cloud Functions (MCP servers)
├── CloudWatch/Logging (monitoring)
└── Secrets Manager (API keys)
```

---

## Monitoring & Observability

### Key Metrics Dashboard

```python
DASHBOARD_METRICS = {
    "operational": [
        "leads_generated_today",
        "calls_made_today",
        "loads_dispatched_today",
        "active_shipments"
    ],
    "financial": [
        "gross_revenue_mtd",
        "commission_earned_mtd",
        "average_rate_per_mile",
        "charity_distributed_mtd"
    ],
    "quality": [
        "lead_conversion_rate",
        "on_time_delivery_rate",
        "carrier_satisfaction_score",
        "broker_relationship_score"
    ]
}
```

### Alerting Rules

```python
ALERTS = {
    "critical": [
        "api_error_rate > 5%",
        "booking_failure_rate > 10%",
        "haram_load_detected"  # Immediate escalation
    ],
    "warning": [
        "avg_rate_per_mile < 2.00",
        "carrier_response_time > 30min",
        "lead_conversion < 10%"
    ]
}
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-21 | Initial architecture |

---

**Next Document:** [SPEC-001-MVP.md](./SPEC-001-MVP.md) - 12-Hour Execution Plan
