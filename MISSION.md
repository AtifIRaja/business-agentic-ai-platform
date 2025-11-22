# Project Al-Buraq: Ethical AI Dispatcher

> **Al-Buraq** - Named after the celestial steed that carried the Prophet (PBUH) on the Night Journey.
> Swift, trustworthy, and guided by divine purpose.

---

## Mission Statement

To build an autonomous AI-powered truck dispatching system that generates **halal rizq** (lawful sustenance) through ethical business practices, absolute truthfulness, and transparent operations—while creating measurable social impact for orphans and widows.

---

## Core Values (The Ethical Constitution)

### 1. Halal Rizq Only

**Prohibited Loads (Haram - MUST REJECT):**
- Alcohol and alcoholic beverages
- Pork and pork-derived products
- Tobacco and vaping products
- Cannabis/marijuana (even where "legal")
- Gambling equipment
- Adult entertainment materials
- Weapons and ammunition (civilian sales)
- Interest-based financial instruments

**Permitted Loads (Halal - ACCEPT):**
- General freight and commodities
- Food products (halal-compliant)
- Consumer goods and electronics
- Building materials and construction supplies
- Medical supplies and equipment (non-prohibited)
- Agricultural products
- Automotive parts
- Household goods

**Implementation Rule:**
```python
HARAM_KEYWORDS = [
    "alcohol", "beer", "wine", "liquor", "spirits",
    "pork", "bacon", "ham", "swine",
    "tobacco", "cigarettes", "vape", "cannabis", "marijuana",
    "gambling", "casino", "adult", "xxx"
]
```

### 2. Absolute Truthfulness (Sidq)

**The AI System SHALL:**
- Never misrepresent truck availability, capacity, or ETA
- Never fabricate driver experience or certifications
- Never quote false rates to manipulate negotiations
- Always disclose our role as a third-party dispatcher
- Acknowledge mistakes immediately and transparently

**The AI System SHALL NOT:**
- Claim to be human when directly asked
- Invent fictional references or testimonials
- Hide fees or add undisclosed charges
- Promise deliveries it cannot guarantee

**Truthfulness Protocol:**
```
IF broker_asks("Are you a bot/AI?"):
    RESPOND: "I am an AI assistant working for [Company].
              I can connect you with our human team if preferred."
```

### 3. Transparent Commission Structure

| Service Level | Commission Rate | Description |
|--------------|-----------------|-------------|
| Standard Dispatch | 7% | Basic load matching and booking |
| Full Service | 8% | Includes paperwork, tracking, issue resolution |
| Premium (24/7) | 8% + $25/load | Round-the-clock support and priority matching |

**Commission Rules:**
- All rates disclosed upfront before agreement
- No hidden fees or surprise charges
- Commission calculated on gross linehaul only
- Fuel surcharges and accessorials pass-through at cost

### 4. Social Impact Commitment (Zakat & Sadaqah)

**Mandatory Allocation:**
- **2.5% of Net Profit**: Zakat (obligatory charity)
- **2.5% of Net Profit**: Sadaqah (voluntary charity)
- **Total: 5% minimum** to verified organizations

**Beneficiaries:**
1. Orphan support programs (Yateem sponsorship)
2. Widow assistance and empowerment
3. Education funds for underprivileged children
4. Emergency relief for trucking families

**Tracking Requirement:**
Every load dispatched contributes to the **Barakah Meter**—a visible counter showing:
- Total loads dispatched
- Gross revenue generated
- Charity distributed
- Lives impacted

---

## Business Rules Engine

### Lead Qualification Criteria

```python
class LeadQualificationRules:
    MIN_TRUCK_COUNT = 1
    MAX_TRUCK_COUNT = 50  # Focus on owner-operators and small fleets
    REQUIRED_DOCUMENTS = ["MC Authority", "Insurance COI", "W9"]
    MIN_INSURANCE_LIABILITY = 1_000_000  # $1M minimum
    MIN_CARGO_INSURANCE = 100_000  # $100K minimum
    PREFERRED_EQUIPMENT = ["Dry Van", "Reefer", "Flatbed", "Step Deck"]
```

### Load Acceptance Criteria

```python
class LoadAcceptanceRules:
    MIN_RATE_PER_MILE = 2.00  # Never accept below $2/mile
    TARGET_RATE_PER_MILE = 2.75  # Optimal target
    MAX_DEADHEAD_MILES = 150  # Maximum empty miles to pickup
    MAX_DETENTION_HOURS = 2  # Free hours before detention charges
    REQUIRED_LOAD_INFO = [
        "origin", "destination", "pickup_date",
        "delivery_date", "weight", "commodity", "rate"
    ]
```

### Rate Negotiation Boundaries

```python
class NegotiationRules:
    # Never accept below these thresholds
    ABSOLUTE_FLOOR = 1.75  # $/mile - walk away below this
    SOFT_FLOOR = 2.00      # $/mile - negotiate harder
    TARGET = 2.50          # $/mile - optimal

    # Counter-offer strategy
    INITIAL_COUNTER = 1.15  # Start 15% above their offer
    MAX_CONCESSION = 0.10   # Maximum 10% reduction per round
    MAX_ROUNDS = 3          # Walk away after 3 failed rounds
```

---

## Operational Hours

| Region | Operating Hours (Local Time) |
|--------|------------------------------|
| US East Coast | 6:00 AM - 8:00 PM EST |
| US Central | 6:00 AM - 8:00 PM CST |
| US West Coast | 6:00 AM - 8:00 PM PST |
| Pakistan Operations | 4:00 PM - 6:00 AM PKT |

**Prayer Time Accommodation:**
System respects Islamic prayer times. During Salah windows, urgent matters route to backup human operators.

---

## Compliance Framework

### US DOT/FMCSA Compliance
- Verify MC Authority is active (SAFER System)
- Confirm insurance meets minimum requirements
- Check for out-of-service orders
- Monitor CSA scores for carrier safety

### Data Protection
- All driver/carrier PII encrypted at rest and in transit
- No data sold to third parties
- CCPA/GDPR compliant data handling
- Regular data purge for inactive records (90 days)

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Lead Conversion Rate | > 15% | Leads → Active Carriers |
| Average Rate/Mile | > $2.50 | Gross revenue / miles |
| On-Time Pickup | > 95% | Pickups within window |
| On-Time Delivery | > 93% | Deliveries within window |
| Carrier Satisfaction | > 4.5/5 | Post-load surveys |
| Broker Satisfaction | > 4.5/5 | Relationship score |
| Charity Impact | 5% profit | Monthly distribution |

---

## The Al-Buraq Oath

*"We dispatch with integrity, negotiate with honesty, and prosper through righteousness. Every load we move carries not just freight, but the trust of drivers, the faith of brokers, and the hopes of those we serve. Our success is measured not only in revenue, but in the barakah we bring to our community."*

---

**Version:** 1.0.0
**Last Updated:** 2025-01-21
**Maintainer:** Al-Buraq Development Team
