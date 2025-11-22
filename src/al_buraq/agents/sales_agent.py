"""
Sales Agent - Automated outreach to verified leads.

Generates personalized emails and tracks communication history.
"""

import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from ..models.lead import Lead
from ..models.enums import LeadStatus
from ..db import Repository


class OutreachType(str, Enum):
    """Types of outreach messages."""
    INITIAL = "initial"
    FOLLOW_UP_1 = "follow_up_1"
    FOLLOW_UP_2 = "follow_up_2"
    FOLLOW_UP_3 = "follow_up_3"
    RE_ENGAGEMENT = "re_engagement"


@dataclass
class EmailDraft:
    """Email draft ready to send."""
    lead_id: str
    to_email: str
    to_name: str
    company_name: str
    subject: str
    body: str
    outreach_type: OutreachType
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OutreachResult:
    """Result of an outreach campaign."""
    total_leads: int = 0
    drafts_created: int = 0
    skipped_no_email: int = 0
    skipped_do_not_contact: int = 0
    skipped_recent_contact: int = 0
    drafts: list[EmailDraft] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Email Templates - Professional, honest, Islamic ethics compliant
EMAIL_TEMPLATES = {
    OutreachType.INITIAL: {
        "subject": "Dispatch Partnership Opportunity - {company_name}",
        "body": """Assalamu Alaikum,

I hope this message finds you well. My name is from Al-Buraq Dispatch Services.

I came across {company_name} and was impressed by your operation. We specialize in connecting quality carriers like yourself with consistent, well-paying freight.

What makes us different:
- Transparent 7-8% commission (no hidden fees, ever)
- Only halal freight (no alcohol, tobacco, or pork products)
- 24/7 dispatcher support
- Fast payment processing

We're currently looking to partner with {truck_count}-truck operations in {state} running {equipment_type} freight.

Would you be open to a brief call this week to discuss how we might work together?

Best regards,
Al-Buraq Dispatch Services
"Built with integrity, dispatched with honesty"

P.S. We donate 5% of our profits to support trucking families in need.
""",
    },
    OutreachType.FOLLOW_UP_1: {
        "subject": "Re: Dispatch Partnership - {company_name}",
        "body": """Assalamu Alaikum,

I wanted to follow up on my previous message about a potential dispatch partnership with {company_name}.

I understand you're busy running your operation. If now isn't the right time, no pressure at all.

But if you're currently:
- Looking for more consistent freight
- Tired of brokers with hidden fees
- Wanting a dispatcher who respects your time

I'd love to have a quick 10-minute conversation.

What does your schedule look like this week?

Best regards,
Al-Buraq Dispatch Services
""",
    },
    OutreachType.FOLLOW_UP_2: {
        "subject": "Quick question for {company_name}",
        "body": """Assalamu Alaikum,

Just a quick note - I've reached out a couple times about dispatch services for {company_name}.

If you're happy with your current setup, I completely understand and won't bother you again.

But if you'd like to explore what consistent freight at $2.50+/mile looks like, just reply "interested" and I'll send over more details.

Either way, safe travels and may your loads be plentiful.

Best,
Al-Buraq Dispatch
""",
    },
    OutreachType.FOLLOW_UP_3: {
        "subject": "Last note from Al-Buraq - {company_name}",
        "body": """Assalamu Alaikum,

This will be my last message unless you'd like to connect.

I've been trying to reach {company_name} about our dispatch services. If the timing isn't right or you're not interested, I respect that completely.

If anything changes in the future, my door is always open. Just reply to this email anytime.

Wishing you success on the road.

Best regards,
Al-Buraq Dispatch Services
""",
    },
}


class SalesAgent:
    """
    Agent that handles outreach to verified leads.

    Features:
    - Personalized email generation
    - Multi-touch follow-up sequences
    - Contact history tracking
    - Do-not-contact compliance
    """

    def __init__(self, repository: Repository):
        self.repository = repository
        self.min_days_between_contact = 3  # Wait at least 3 days between emails
        self.max_contact_attempts = 4  # Max emails before stopping

    def _get_outreach_type(self, lead: Lead) -> Optional[OutreachType]:
        """Determine what type of outreach to send based on contact history."""
        attempts = lead.contact_attempts

        if attempts == 0:
            return OutreachType.INITIAL
        elif attempts == 1:
            return OutreachType.FOLLOW_UP_1
        elif attempts == 2:
            return OutreachType.FOLLOW_UP_2
        elif attempts == 3:
            return OutreachType.FOLLOW_UP_3
        else:
            return None  # Max attempts reached

    def _should_contact(self, lead: Lead) -> tuple[bool, str]:
        """Check if we should contact this lead."""
        # Check do-not-contact flags
        if lead.contact.do_not_email:
            return False, "do_not_email flag set"

        if not lead.contact.email:
            return False, "no email address"

        # Check max attempts
        if lead.contact_attempts >= self.max_contact_attempts:
            return False, "max contact attempts reached"

        # Check recent contact
        if lead.last_contact_date:
            days_since = (datetime.utcnow() - lead.last_contact_date).days
            if days_since < self.min_days_between_contact:
                return False, f"contacted {days_since} days ago (min {self.min_days_between_contact})"

        return True, "ok"

    def _personalize_template(self, template: dict, lead: Lead) -> tuple[str, str]:
        """Personalize email template with lead data."""
        # Get equipment type display
        equipment = "dry van"
        if lead.fleet.equipment_types:
            eq = lead.fleet.equipment_types[0]
            equipment = eq.value if hasattr(eq, 'value') else str(eq)
            equipment = equipment.replace("_", " ")

        # Get owner name or company contact
        contact_name = lead.owner_name or lead.company_name.split()[0]

        # Replacement variables
        replacements = {
            "{company_name}": lead.company_name,
            "{owner_name}": contact_name,
            "{truck_count}": str(lead.fleet.truck_count),
            "{state}": lead.fleet.home_base_state or "your area",
            "{equipment_type}": equipment,
            "{mc_number}": lead.authority.mc_number,
        }

        subject = template["subject"]
        body = template["body"]

        for key, value in replacements.items():
            subject = subject.replace(key, value)
            body = body.replace(key, value)

        return subject, body

    def generate_draft(self, lead: Lead) -> Optional[EmailDraft]:
        """Generate an email draft for a lead."""
        # Check if we should contact
        should_contact, reason = self._should_contact(lead)
        if not should_contact:
            return None

        # Get outreach type
        outreach_type = self._get_outreach_type(lead)
        if not outreach_type:
            return None

        # Get template
        template = EMAIL_TEMPLATES.get(outreach_type)
        if not template:
            return None

        # Personalize
        subject, body = self._personalize_template(template, lead)

        # Get contact name
        contact_name = lead.owner_name or lead.company_name

        return EmailDraft(
            lead_id=lead.id,
            to_email=lead.contact.email,
            to_name=contact_name,
            company_name=lead.company_name,
            subject=subject,
            body=body,
            outreach_type=outreach_type,
        )

    def generate_campaign(
        self,
        limit: int = 10,
        verified_only: bool = True,
        high_intent_only: bool = False,
        social_verified_only: bool = False,
    ) -> OutreachResult:
        """
        Generate email drafts for a campaign.

        Args:
            limit: Maximum drafts to generate
            verified_only: Only include verified leads
            high_intent_only: Only include high-intent leads
            social_verified_only: Only include socially verified leads

        Returns:
            OutreachResult with drafts and statistics
        """
        result = OutreachResult()

        # Get leads based on filters
        if verified_only:
            leads = self.repository.get_verified_leads(
                social_verified=True if social_verified_only else None,
                high_intent=True if high_intent_only else None,
                limit=limit * 2,  # Get extra in case some are skipped
            )
        else:
            leads = self.repository.list_leads(
                is_qualified=True,
                limit=limit * 2,
            )

        result.total_leads = len(leads)

        for lead in leads:
            if result.drafts_created >= limit:
                break

            # Check if we should contact
            should_contact, reason = self._should_contact(lead)

            if not should_contact:
                if "no email" in reason:
                    result.skipped_no_email += 1
                elif "do_not" in reason:
                    result.skipped_do_not_contact += 1
                elif "contacted" in reason:
                    result.skipped_recent_contact += 1
                continue

            # Generate draft
            draft = self.generate_draft(lead)
            if draft:
                result.drafts.append(draft)
                result.drafts_created += 1

        return result

    def mark_sent(self, lead_id: str, outreach_type: OutreachType) -> bool:
        """Mark an email as sent and update lead contact history."""
        lead = self.repository.get_lead(lead_id)
        if not lead:
            return False

        # Update contact history
        lead.contact_attempts += 1
        lead.last_contact_date = datetime.utcnow()
        lead.last_contact_outcome = f"email_sent:{outreach_type.value}"
        lead.updated_at = datetime.utcnow()

        # Set next follow-up date
        lead.next_follow_up_date = datetime.utcnow() + timedelta(days=self.min_days_between_contact)

        # Update status if first contact
        if lead.status == LeadStatus.QUALIFIED:
            lead.status = LeadStatus.CONTACTED

        # Add note
        lead.add_note(f"Email sent: {outreach_type.value}")

        # Save
        self.repository.update_lead(lead)
        return True

    def get_pending_follow_ups(self, limit: int = 20) -> list[Lead]:
        """Get leads that are due for follow-up."""
        # This would query leads where next_follow_up_date <= now
        # For now, get contacted leads
        leads = self.repository.list_leads(limit=limit * 2)

        pending = []
        now = datetime.utcnow()

        for lead in leads:
            if lead.next_follow_up_date and lead.next_follow_up_date <= now:
                if lead.contact_attempts < self.max_contact_attempts:
                    pending.append(lead)
                    if len(pending) >= limit:
                        break

        return pending
