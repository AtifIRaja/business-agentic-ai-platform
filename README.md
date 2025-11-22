# Al-Buraq: The First Ethical Level 5 AI Dispatcher

<p align="center">
  <img src="docs/logo.png" alt="Al-Buraq Logo" width="200"/>
</p>

<p align="center">
  <strong>Automating US Truck Dispatching with Islamic Values</strong>
</p>

<p align="center">
  <em>Named after the celestial steed that carried the Prophet (PBUH) on the Night Journey.<br/>Swift, trustworthy, and guided by divine purpose.</em>
</p>

---

## The Vision

**Al-Buraq** is not just another dispatch software. It is a complete paradigm shift in how freight dispatching operates.

While the trucking industry is plagued with hidden fees, deceptive practices, and exploitative brokers, Al-Buraq stands as proof that **technology and ethics can coexist**.

### Our Promise

| Principle | Implementation |
|-----------|----------------|
| **Halal Rizq Only** | AI automatically rejects alcohol, pork, tobacco, and gambling-related freight |
| **Absolute Truthfulness** | System cannot generate false rate quotes or deceptive communications |
| **Transparent Commission** | 7-8% commission disclosed upfront on every transaction |
| **Social Impact** | 5% of profits support orphans, widows, and trucking families in need |

---

## Live Architecture

Al-Buraq operates as a **Level 5 Autonomous AI System** with four specialized agents working in concert:

```
                         AL-BURAQ DISPATCH BRAIN
    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
    │   │   HUNTER     │    │ INVESTIGATOR │    │    SALES     │     │
    │   │    AGENT     │───▶│    AGENT     │───▶│    AGENT     │     │
    │   │              │    │              │    │              │     │
    │   │ FMCSA Import │    │  DuckDuckGo  │    │  4-Touch     │     │
    │   │ Lead Scoring │    │  Verification │    │  Outreach    │     │
    │   │ Qualification│    │  Intent Scan │    │  Follow-ups  │     │
    │   └──────────────┘    └──────────────┘    └──────┬───────┘     │
    │                                                   │             │
    │                                                   ▼             │
    │                                          ┌──────────────┐       │
    │                                          │   DISPATCH   │       │
    │                                          │    AGENT     │       │
    │                                          │              │       │
    │                                          │ Load Match   │       │
    │                                          │ Halal Filter │       │
    │                                          │ Commission   │       │
    │                                          └──────────────┘       │
    │                                                   │             │
    │   ┌─────────────────────────────────────────────────────────┐  │
    │   │              SHARED MEMORY LAYER                        │  │
    │   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │  │
    │   │  │ SQLite  │ │ChromaDB │ │  Halal  │ │ Vector  │       │  │
    │   │  │ Storage │ │ Vectors │ │ Filter  │ │ Search  │       │  │
    │   │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │  │
    │   └─────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent | Role | Key Capabilities |
|-------|------|------------------|
| **Hunter** | Lead Generation | FMCSA CSV import, web scraping, 12-point qualification scoring |
| **Investigator** | Verification | DuckDuckGo social media search, LinkedIn/Facebook detection, intent signals |
| **Sales** | Outreach | Personalized email generation, 4-touch sequences, do-not-contact compliance |
| **Dispatch** | Matching | Load-carrier matching, halal filtering, commission calculation, geographic scoring |

---

## Key Features

### Halal Compliance Filter

```
┌─────────────────────────────────────────────┐
│           HALAL COMPLIANCE ENGINE           │
├─────────────────────────────────────────────┤
│  HALAL (Auto-Approve):                      │
│    ✓ Electronics, Produce, Furniture        │
│    ✓ Medical Supplies, Auto Parts           │
│    ✓ Building Materials, Machinery          │
│                                             │
│  HARAM (Auto-Reject):                       │
│    ✗ Alcohol, Beer, Wine, Spirits           │
│    ✗ Pork Products, Bacon, Ham              │
│    ✗ Tobacco, Cigarettes, Vape              │
│    ✗ Gambling Equipment, Casino             │
│                                             │
│  REVIEW (Manual Check):                     │
│    ⚠ Unknown commodities flagged            │
└─────────────────────────────────────────────┘
```

### Transparent Commission Model

Every load displays complete financial transparency:

```
Load: Electronics from Dallas, TX → Los Angeles, CA
Rate: $4,200.00 | Miles: 1,400 | Rate/Mile: $3.00

┌────────────────────────────────────────┐
│ Commission Breakdown                   │
├────────────────────────────────────────┤
│ Broker Rate:        $4,200.00          │
│ Commission (7%):    $294.00            │
│ Charity (5%):       $14.70             │
│ Net to Carrier:     $3,906.00          │
└────────────────────────────────────────┘
```

### Social Verification Engine

```bash
$ alburaq investigate --limit 10

Investigating leads via DuckDuckGo...

✓ ABC Trucking LLC     [VERIFIED] LinkedIn + Facebook | High Intent
✓ Express Freight Inc  [VERIFIED] Website Found
✓ Fast Haul Transport  [VERIFIED] Instagram Active
✗ Unknown Carrier      [PENDING]  No social presence

Results: 10 investigated | 6 social verified | 3 high intent
```

### Semantic Lead Search

```bash
$ alburaq search "flatbed carriers in Texas with 5+ trucks"

Found 12 matches:

1. Texas Steel Haulers (MC: 123456)
   Score: 0.89 | Equipment: Flatbed, Step Deck | Trucks: 8

2. Lone Star Flatbed Inc (MC: 234567)
   Score: 0.85 | Equipment: Flatbed | Trucks: 6
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Language** | Python 3.12 | Modern async support, type hints |
| **Data Models** | Pydantic v2 | Runtime validation, serialization |
| **Relational DB** | SQLite + SQLAlchemy | Persistent lead/load storage |
| **Vector DB** | ChromaDB | Semantic search, embeddings |
| **Web Search** | DuckDuckGo API | Lead verification, intent detection |
| **CLI** | Typer + Rich | Beautiful terminal interface |
| **AI Ready** | OpenAI / Anthropic | LLM integration points |

---

## Installation & Usage

### Quick Start

```bash
# Clone the repository
git clone https://github.com/atif/al-buraq.git
cd al-buraq

# Install with dependencies
pip install -e .

# Initialize database
alburaq init

# Run demo
alburaq demo
```

### Complete Pipeline

```bash
# Step 1: Import carriers from FMCSA data
alburaq import-csv fmcsa_carriers.csv --limit 500

# Step 2: View qualified leads
alburaq leads --limit 20

# Step 3: Investigate leads (verify social presence)
alburaq investigate --limit 10 --delay 5

# Step 4: View verified leads
alburaq verified

# Step 5: Generate outreach campaign
alburaq outreach --limit 10

# Step 6: Run dispatch matching
alburaq dispatch --loads 5

# Step 7: Check full pipeline status
alburaq pipeline
```

### Sample Output

```
$ alburaq pipeline

╔═══════════════════════════════════════════════════╗
║           AL-BURAQ DISPATCH PIPELINE              ║
╠═══════════════════════════════════════════════════╣
║  STAGE          │ COUNT   │ STATUS               ║
╠═══════════════════════════════════════════════════╣
║  Imported       │    592  │ ████████████ 100%    ║
║  Qualified      │    559  │ ███████████░  94%    ║
║  Verified       │     13  │ ██░░░░░░░░░░   2%    ║
║  Contacted      │      0  │ ░░░░░░░░░░░░   0%    ║
║  Dispatching    │      0  │ ░░░░░░░░░░░░   0%    ║
╚═══════════════════════════════════════════════════╝

Next Action: Run 'alburaq investigate' to verify more leads
```

---

## CLI Commands Reference

| Command | Description |
|---------|-------------|
| `alburaq init` | Initialize database and vector store |
| `alburaq demo` | Run interactive demonstration |
| `alburaq import-csv <file>` | Import FMCSA carrier data |
| `alburaq hunt --limit N` | Hunt for new leads |
| `alburaq leads` | List all leads |
| `alburaq search <query>` | Semantic search leads |
| `alburaq investigate` | Verify leads via web search |
| `alburaq verified` | Show verified leads |
| `alburaq outreach` | Generate email campaign |
| `alburaq dispatch` | Run dispatch matching |
| `alburaq check-halal <commodity>` | Check halal status |
| `alburaq pipeline` | View full pipeline status |
| `alburaq stats` | Database statistics |

---

## Project Structure

```
al-buraq/
├── src/al_buraq/
│   ├── models/           # Pydantic data models
│   │   ├── lead.py       # Lead/Carrier model
│   │   ├── load.py       # Load/Freight model
│   │   ├── carrier.py    # Carrier entity
│   │   └── enums.py      # Shared enumerations
│   │
│   ├── agents/           # AI Agent implementations
│   │   ├── hunter_agent.py       # Lead generation
│   │   ├── investigator_agent.py # Web verification
│   │   ├── sales_agent.py        # Email outreach
│   │   └── dispatch_agent.py     # Load matching
│   │
│   ├── db/               # Database layer
│   │   ├── repository.py # CRUD operations
│   │   └── vector_store.py # ChromaDB integration
│   │
│   ├── filters/          # Halal compliance
│   │   └── halal.py      # Commodity filtering
│   │
│   ├── scoring/          # Lead qualification
│   │   └── lead_scorer.py # 12-point scoring
│   │
│   ├── hunters/          # Lead sources
│   │   └── csv_hunter.py # FMCSA import
│   │
│   └── cli/              # Command interface
│       └── main.py       # Typer CLI
│
├── data/                 # Database files
├── docs/                 # Documentation
└── tests/                # Test suite
```

---

## Roadmap

### Phase 1: Foundation (Complete)
- [x] Core data models (Lead, Load, Carrier)
- [x] SQLite + ChromaDB integration
- [x] Halal compliance filter
- [x] 12-point lead scoring
- [x] FMCSA CSV import
- [x] Semantic search

### Phase 2: Intelligence (Complete)
- [x] Hunter Agent - Lead generation
- [x] Investigator Agent - Web verification
- [x] Sales Agent - Email outreach
- [x] Dispatch Agent - Load matching

### Phase 3: Automation (Next)
- [ ] LLM-powered email personalization
- [ ] Automated email sending (SMTP)
- [ ] Real-time load board integration
- [ ] Rate negotiation AI

### Phase 4: Scale (Future)
- [ ] Multi-tenant SaaS deployment
- [ ] Mobile app for carriers
- [ ] Payment processing integration
- [ ] Performance analytics dashboard

---

## Business Model

```
┌─────────────────────────────────────────────────────────┐
│                 REVENUE FLOW                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   Load Rate: $4,200                                     │
│        │                                                │
│        ├──▶ 93% to Carrier ($3,906)                    │
│        │                                                │
│        └──▶ 7% Commission ($294)                       │
│              │                                          │
│              ├──▶ 95% Operating ($279.30)              │
│              │                                          │
│              └──▶ 5% Charity ($14.70)                  │
│                    │                                    │
│                    └──▶ Trucking Families Fund         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Why Al-Buraq?

### For Carriers
- **No hidden fees** - 7% commission, always disclosed
- **Halal freight only** - Align your business with your values
- **Quality loads** - Pre-screened, verified brokers
- **Respect** - Professional communication, no spam

### For Investors
- **$800B market** - US trucking is massive and fragmented
- **Ethical differentiation** - Unique positioning in the market
- **AI-first architecture** - Scalable, modern technology
- **Proven demand** - Muslim truck owners seeking halal options

### For Society
- **5% charity contribution** - Every load helps families in need
- **Ethical AI** - Proof that technology can embody values
- **Transparency** - Fighting deception in the industry

---

## Contact

**Developed by Atif**

*Open for Enterprise Partnerships*

- Email: atif@alburaq.ai
- LinkedIn: [linkedin.com/in/atif](https://linkedin.com)
- GitHub: [github.com/atif](https://github.com)

---

<p align="center">
  <strong>Built with integrity, dispatched with honesty.</strong>
</p>

<p align="center">
  <em>"And whoever fears Allah - He will make for him a way out, and will provide for him from where he does not expect."</em><br/>
  — Quran 65:2-3
</p>

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Al-Buraq Dispatch Systems &copy; 2024</sub>
</p>
