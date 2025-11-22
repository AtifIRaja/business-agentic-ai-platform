"""
Al-Buraq CLI

Command-line interface for the Al-Buraq Ethical AI Dispatch System.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from ..config import settings

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from ..agents import HunterAgent
from ..db import get_repository, get_vector_store
from ..filters import HalalFilter, check_commodity
from ..scoring import LeadScorer

app = typer.Typer(
    name="alburaq",
    help="Al-Buraq: Ethical AI Dispatch System",
    add_completion=False,
)
console = Console()


# =============================================================================
# Hunt Commands
# =============================================================================

@app.command()
def hunt(
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum leads to find"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Specific source to hunt from"),
    min_score: float = typer.Option(0.6, "--min-score", help="Minimum lead score"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save results to database"),
):
    """
    Hunt for new carrier leads.

    Runs the Hunter Agent to find and qualify new carrier leads
    from configured sources (FMCSA SAFER, load boards, etc.).
    """
    console.print(Panel.fit(
        "[bold green]Al-Buraq Hunter Agent[/bold green]\n"
        "Finding new carrier leads...",
        title="Bismillah",
    ))

    sources = [source] if source else None

    async def run_hunt():
        agent = HunterAgent()

        console.print("[dim]Hunting for leads...[/dim]")

        session = await agent.hunt(
            sources=sources,
            limit_per_source=limit,
            min_score=min_score,
            save_results=save,
        )

        console.print("[dim]Hunt complete.[/dim]")

        return session

    session = asyncio.run(run_hunt())

    # Display results
    console.print()

    table = Table(title="Hunt Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Duration", f"{session.duration_seconds:.1f}s")
    table.add_row("Total Found", str(session.total_found))
    table.add_row("Scored", str(session.total_scored))
    table.add_row("Qualified", f"[bold green]{session.total_qualified}[/bold green]")
    table.add_row("Duplicates Skipped", str(session.total_duplicates))
    table.add_row("Errors", str(session.total_errors))
    table.add_row("Qualification Rate", f"{session.qualification_rate:.1%}")

    console.print(table)

    if session.total_qualified > 0:
        console.print(f"\n[green]Successfully found {session.total_qualified} qualified leads![/green]")
    else:
        console.print("\n[yellow]No qualified leads found. Try adjusting filters.[/yellow]")


@app.command()
def leads(
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum leads to show"),
    qualified: bool = typer.Option(True, "--qualified/--all", help="Show only qualified leads"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """
    List leads from the database.

    Shows leads sorted by score, with qualification status.
    """
    repo = get_repository()

    from ..models.enums import LeadStatus
    status_filter = LeadStatus(status) if status else None

    leads_list = repo.list_leads(
        status=status_filter,
        is_qualified=qualified if qualified else None,
        limit=limit,
    )

    if not leads_list:
        console.print("[yellow]No leads found.[/yellow]")
        return

    table = Table(title=f"Leads ({len(leads_list)} found)")
    table.add_column("Score", style="cyan", width=6)
    table.add_column("Company", style="white", width=25)
    table.add_column("MC#", style="dim", width=10)
    table.add_column("Trucks", style="green", width=6)
    table.add_column("State", width=5)
    table.add_column("Equipment", width=15)
    table.add_column("Status", width=10)

    for lead in leads_list:
        score_color = "green" if lead.lead_score >= 0.7 else "yellow" if lead.lead_score >= 0.5 else "red"
        equipment = ", ".join(str(e)[:3] for e in lead.fleet.equipment_types[:2])

        table.add_row(
            f"[{score_color}]{lead.lead_score:.2f}[/{score_color}]",
            lead.company_name[:25],
            lead.authority.mc_number,
            str(lead.fleet.truck_count),
            lead.fleet.home_base_state or "?",
            equipment or "?",
            lead.status,
        )

    console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results"),
):
    """
    Search for carriers using semantic search.

    Examples:
        alburaq search "owner operator in Texas with dry van"
        alburaq search "reefer carrier in California"
    """
    async def run_search():
        agent = HunterAgent()
        return await agent.find_similar_carriers(query=query, limit=limit)

    console.print(f"[cyan]Searching for:[/cyan] {query}\n")

    results = asyncio.run(run_search())

    if not results:
        console.print("[yellow]No matching carriers found.[/yellow]")
        return

    table = Table(title=f"Search Results ({len(results)} found)")
    table.add_column("Score", style="cyan", width=6)
    table.add_column("Company", width=25)
    table.add_column("Location", width=15)
    table.add_column("Equipment", width=15)
    table.add_column("Trucks", width=6)

    for lead in results:
        location = f"{lead.fleet.home_base_city or '?'}, {lead.fleet.home_base_state or '?'}"
        equipment = ", ".join(str(e).replace("_", " ")[:8] for e in lead.fleet.equipment_types[:2])

        table.add_row(
            f"{lead.lead_score:.2f}",
            lead.company_name[:25],
            location[:15],
            equipment,
            str(lead.fleet.truck_count),
        )

    console.print(table)


# =============================================================================
# Filter Commands
# =============================================================================

@app.command()
def check_halal(
    commodity: str = typer.Argument(..., help="Commodity to check"),
):
    """
    Check if a commodity is halal.

    Checks the commodity against the halal filter and shows
    the result with reasoning.
    """
    result = check_commodity(commodity)

    status_display = {
        "halal": "[bold green]HALAL[/bold green]",
        "haram": "[bold red]HARAM[/bold red]",
        "unknown": "[bold yellow]REVIEW NEEDED[/bold yellow]",
    }

    console.print(Panel(
        f"Commodity: [white]{commodity}[/white]\n\n"
        f"Status: {status_display[result.status]}\n"
        f"Reason: {result.reason}\n"
        f"Confidence: {result.confidence:.0%}",
        title="Halal Check Result",
    ))


# =============================================================================
# Stats Commands
# =============================================================================

@app.command()
def stats():
    """
    Show database and pipeline statistics.

    Displays counts of leads, carriers, and loads in the system.
    """
    repo = get_repository()
    vector_store = get_vector_store()

    db_stats = repo.get_stats()
    vector_stats = vector_store.get_collection_stats()

    console.print(Panel.fit(
        "[bold]Al-Buraq System Statistics[/bold]",
        title="Dashboard",
    ))

    # Leads table
    table = Table(title="Leads Pipeline")
    table.add_column("Status", style="cyan")
    table.add_column("Count", style="green")

    table.add_row("Total", str(db_stats["leads"]["total"]))
    table.add_row("New", str(db_stats["leads"]["new"]))
    table.add_row("Qualified", str(db_stats["leads"]["qualified"]))
    table.add_row("Converted", str(db_stats["leads"]["converted"]))

    console.print(table)

    # Carriers table
    table = Table(title="Carriers")
    table.add_column("Status", style="cyan")
    table.add_column("Count", style="green")

    table.add_row("Total", str(db_stats["carriers"]["total"]))
    table.add_row("Active", str(db_stats["carriers"]["active"]))
    table.add_row("Available", str(db_stats["carriers"]["available"]))

    console.print(table)

    # Loads table
    table = Table(title="Loads")
    table.add_column("Status", style="cyan")
    table.add_column("Count", style="green")

    table.add_row("Total", str(db_stats["loads"]["total"]))
    table.add_row("Available", str(db_stats["loads"]["available"]))
    table.add_row("Booked", str(db_stats["loads"]["booked"]))
    table.add_row("Delivered", str(db_stats["loads"]["delivered"]))

    console.print(table)

    # Vector store
    console.print(f"\n[dim]Vector Store: {vector_stats}[/dim]")


@app.command()
def init():
    """
    Initialize the database and vector store.

    Run this once to set up the system before first use.
    """
    console.print("[cyan]Initializing Al-Buraq...[/cyan]")

    # Initialize database
    repo = get_repository()
    console.print("[green]Database initialized.[/green]")

    # Initialize vector store
    vector_store = get_vector_store()
    console.print("[green]Vector store initialized.[/green]")

    console.print(Panel.fit(
        "[bold green]Al-Buraq is ready![/bold green]\n\n"
        "Next steps:\n"
        "1. Run [cyan]alburaq hunt[/cyan] to find new leads\n"
        "2. Run [cyan]alburaq leads[/cyan] to view leads\n"
        "3. Run [cyan]alburaq stats[/cyan] to see statistics",
        title="Setup Complete",
    ))


@app.command()
def version():
    """Show version information."""
    console.print(Panel(
        f"[bold]Al-Buraq[/bold] v{settings.APP_VERSION}\n"
        "Ethical AI Dispatch System\n\n"
        "[dim]Built with integrity, dispatched with honesty.[/dim]",
        title="Version",
    ))


# =============================================================================
# Demo Command
# =============================================================================

@app.command()
def demo():
    """
    Run a demonstration of the system.

    Creates sample leads and shows the full pipeline.
    """
    console.print(Panel.fit(
        "[bold green]Al-Buraq Demo Mode[/bold green]\n"
        "Demonstrating the Ethical AI Dispatch System",
        title="Bismillah",
    ))

    # Step 1: Initialize
    console.print("\n[cyan]Step 1: Initializing system...[/cyan]")
    repo = get_repository()
    vector_store = get_vector_store()
    console.print("[green]System ready.[/green]")

    # Step 2: Hunt for leads
    console.print("\n[cyan]Step 2: Hunting for leads...[/cyan]")

    async def run_demo_hunt():
        agent = HunterAgent()
        return await agent.hunt(
            sources=["fmcsa"],
            limit_per_source=10,
            save_results=True,
        )

    session = asyncio.run(run_demo_hunt())
    console.print(f"[green]Found {session.total_qualified} qualified leads![/green]")

    # Step 3: Show top leads
    console.print("\n[cyan]Step 3: Top qualified leads:[/cyan]")

    leads_list = repo.list_leads(is_qualified=True, limit=5)

    if leads_list:
        table = Table()
        table.add_column("Company", width=25)
        table.add_column("Score", width=6)
        table.add_column("Trucks", width=6)
        table.add_column("State", width=5)

        for lead in leads_list:
            table.add_row(
                lead.company_name[:25],
                f"{lead.lead_score:.2f}",
                str(lead.fleet.truck_count),
                lead.fleet.home_base_state or "?",
            )

        console.print(table)

    # Step 4: Test halal filter
    console.print("\n[cyan]Step 4: Testing halal filter...[/cyan]")

    test_commodities = ["Electronics", "Beer", "Fresh Produce", "Tobacco"]
    for commodity in test_commodities:
        result = check_commodity(commodity)
        status = "[green]HALAL" if result.status == "halal" else "[red]HARAM" if result.status == "haram" else "[yellow]REVIEW"
        console.print(f"  {commodity}: {status}[/]")

    # Summary
    console.print(Panel.fit(
        "[bold green]Demo Complete![/bold green]\n\n"
        "The Al-Buraq system is ready for production use.\n"
        "Run [cyan]alburaq hunt[/cyan] to find more leads.",
        title="Alhamdulillah",
    ))


# =============================================================================
# Investigator Commands
# =============================================================================

@app.command()
def investigate(
    limit: int = typer.Option(5, "--limit", "-l", help="Number of leads to investigate"),
    delay: float = typer.Option(2.0, "--delay", "-d", help="Seconds between searches"),
):
    """
    Investigate leads to verify their legitimacy.

    Uses DuckDuckGo to find social media presence and intent signals.
    Only investigates qualified leads with pending verification status.

    Examples:
        alburaq investigate --limit 10
        alburaq investigate --limit 5 --delay 3
    """
    from ..agents import InvestigatorAgent

    repo = get_repository()

    console.print(Panel.fit(
        "[bold green]Lead Investigator[/bold green]\n"
        f"Verifying up to {limit} leads...",
        title="Bismillah",
    ))

    # Check pending count
    v_stats = repo.get_verification_stats()
    console.print(f"[dim]Pending verification: {v_stats['pending']} leads[/dim]\n")

    if v_stats['pending'] == 0:
        console.print("[yellow]No leads pending verification.[/yellow]")
        return

    agent = InvestigatorAgent(repository=repo)

    def progress_callback(current: int, total: int, company: str):
        console.print(f"  [{current}/{total}] Investigating: [cyan]{company[:40]}[/cyan]...")

    session = agent.investigate_batch(
        limit=limit,
        delay_seconds=delay,
        progress_callback=progress_callback,
    )

    # Show results
    console.print()

    table = Table(title="Investigation Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Leads Investigated", str(session.total_investigated))
    table.add_row("Social Media Found", f"[bold green]{session.social_verified_count}[/bold green]")
    table.add_row("High Intent Signals", f"[bold cyan]{session.high_intent_count}[/bold cyan]")
    table.add_row("Errors", str(session.errors))
    table.add_row("Duration", f"{session.duration_seconds:.1f}s")

    console.print(table)

    # Show individual results
    if session.results:
        console.print("\n[cyan]Details:[/cyan]")
        detail_table = Table()
        detail_table.add_column("Company", width=25)
        detail_table.add_column("Social", width=8)
        detail_table.add_column("Intent", width=8)
        detail_table.add_column("Links Found", width=40)

        for result in session.results:
            links = []
            if result.linkedin_url:
                links.append("LinkedIn")
            if result.facebook_url:
                links.append("Facebook")
            if result.instagram_url:
                links.append("Instagram")
            if result.website_url:
                links.append("Website")

            social_status = "[green]Yes[/green]" if result.social_verified else "[dim]No[/dim]"
            intent_status = "[green]Yes[/green]" if result.high_intent else "[dim]No[/dim]"

            detail_table.add_row(
                result.company_name[:25],
                social_status,
                intent_status,
                ", ".join(links) if links else "[dim]None[/dim]",
            )

        console.print(detail_table)

    # Updated stats
    new_stats = repo.get_verification_stats()
    console.print(f"\n[green]Verification complete![/green]")
    console.print(f"[dim]Remaining pending: {new_stats['pending']} | Total verified: {new_stats['verified']}[/dim]")


@app.command()
def verified(
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum leads to show"),
    social_only: bool = typer.Option(False, "--social", "-s", help="Only show socially verified"),
    high_intent_only: bool = typer.Option(False, "--intent", "-i", help="Only show high intent"),
):
    """
    List verified leads ready for outreach.

    Shows leads that have been investigated and verified.
    """
    repo = get_repository()

    social = True if social_only else None
    intent = True if high_intent_only else None

    leads_list = repo.get_verified_leads(
        social_verified=social,
        high_intent=intent,
        limit=limit,
    )

    if not leads_list:
        console.print("[yellow]No verified leads found matching criteria.[/yellow]")
        return

    table = Table(title=f"Verified Leads ({len(leads_list)} found)")
    table.add_column("Score", style="cyan", width=6)
    table.add_column("Company", width=22)
    table.add_column("State", width=5)
    table.add_column("Social", width=8)
    table.add_column("Intent", width=8)
    table.add_column("Links", width=25)

    for lead in leads_list:
        links = []
        if lead.linkedin_url:
            links.append("LI")
        if lead.facebook_url:
            links.append("FB")
        if lead.instagram_url:
            links.append("IG")
        if lead.website_url:
            links.append("Web")

        social_status = "[green]Yes[/green]" if lead.social_verified else "[dim]No[/dim]"
        intent_status = "[green]Yes[/green]" if lead.high_intent else "[dim]No[/dim]"

        table.add_row(
            f"{lead.lead_score:.2f}",
            lead.company_name[:22],
            lead.fleet.home_base_state or "?",
            social_status,
            intent_status,
            ", ".join(links) if links else "-",
        )

    console.print(table)

    # Show stats
    stats = repo.get_verification_stats()
    console.print(f"\n[dim]Stats: {stats['social_verified']} with social | {stats['high_intent']} high intent[/dim]")


# =============================================================================
# Sales Agent Commands
# =============================================================================

@app.command()
def outreach(
    limit: int = typer.Option(5, "--limit", "-l", help="Number of drafts to generate"),
    verified_only: bool = typer.Option(True, "--verified/--all", help="Only verified leads"),
    high_intent: bool = typer.Option(False, "--intent", "-i", help="Only high-intent leads"),
    social: bool = typer.Option(False, "--social", "-s", help="Only socially verified leads"),
):
    """
    Generate email drafts for outreach campaign.

    Creates personalized emails for verified leads ready for contact.

    Examples:
        alburaq outreach --limit 10
        alburaq outreach --intent --limit 5
    """
    from ..agents import SalesAgent

    repo = get_repository()

    console.print(Panel.fit(
        "[bold green]Sales Outreach Campaign[/bold green]\n"
        f"Generating up to {limit} email drafts...",
        title="Bismillah",
    ))

    agent = SalesAgent(repository=repo)

    result = agent.generate_campaign(
        limit=limit,
        verified_only=verified_only,
        high_intent_only=high_intent,
        social_verified_only=social,
    )

    # Show stats
    table = Table(title="Campaign Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Leads Evaluated", str(result.total_leads))
    table.add_row("Drafts Created", f"[bold green]{result.drafts_created}[/bold green]")
    table.add_row("Skipped (No Email)", str(result.skipped_no_email))
    table.add_row("Skipped (Do Not Contact)", str(result.skipped_do_not_contact))
    table.add_row("Skipped (Recent Contact)", str(result.skipped_recent_contact))

    console.print(table)

    if not result.drafts:
        console.print("\n[yellow]No drafts generated. Try different filters or investigate more leads.[/yellow]")
        return

    # Show drafts
    console.print(f"\n[cyan]Email Drafts ({len(result.drafts)}):[/cyan]\n")

    for i, draft in enumerate(result.drafts, 1):
        console.print(Panel(
            f"[bold]To:[/bold] {draft.to_name} <{draft.to_email}>\n"
            f"[bold]Company:[/bold] {draft.company_name}\n"
            f"[bold]Type:[/bold] {draft.outreach_type.value}\n"
            f"[bold]Subject:[/bold] {draft.subject}\n\n"
            f"[dim]--- Preview ---[/dim]\n"
            f"{draft.body[:500]}{'...' if len(draft.body) > 500 else ''}",
            title=f"Draft #{i} - {draft.lead_id[:8]}",
            width=80,
        ))

    console.print(f"\n[green]Generated {result.drafts_created} email drafts![/green]")
    console.print("[dim]Use 'alburaq send <lead_id>' to mark as sent after manual sending.[/dim]")


@app.command()
def send(
    lead_id: str = typer.Argument(..., help="Lead ID (or partial ID) to mark as sent"),
):
    """
    Mark an email as sent for a lead.

    Updates contact history after manually sending an email.
    Use after copying and sending the email draft.
    """
    from ..agents import SalesAgent
    from ..agents.sales_agent import OutreachType

    repo = get_repository()

    # Find lead by ID (partial match)
    leads = repo.list_leads(limit=100)
    matching_lead = None

    for lead in leads:
        if lead.id.startswith(lead_id) or lead_id in lead.id:
            matching_lead = lead
            break

    if not matching_lead:
        console.print(f"[red]Lead not found: {lead_id}[/red]")
        return

    # Determine outreach type based on contact attempts
    attempts = matching_lead.contact_attempts
    if attempts == 0:
        outreach_type = OutreachType.INITIAL
    elif attempts == 1:
        outreach_type = OutreachType.FOLLOW_UP_1
    elif attempts == 2:
        outreach_type = OutreachType.FOLLOW_UP_2
    else:
        outreach_type = OutreachType.FOLLOW_UP_3

    agent = SalesAgent(repository=repo)
    success = agent.mark_sent(matching_lead.id, outreach_type)

    if success:
        console.print(Panel.fit(
            f"[bold green]Email Marked as Sent[/bold green]\n\n"
            f"Company: {matching_lead.company_name}\n"
            f"Email: {matching_lead.contact.email}\n"
            f"Type: {outreach_type.value}\n"
            f"Contact Attempts: {attempts + 1}",
            title="Success",
        ))
    else:
        console.print("[red]Failed to update lead.[/red]")


@app.command()
def followups(
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum leads to show"),
):
    """
    Show leads that need follow-up.

    Lists leads that have been contacted but need another touch.
    """
    from ..agents import SalesAgent

    repo = get_repository()
    agent = SalesAgent(repository=repo)

    pending = agent.get_pending_follow_ups(limit=limit)

    if not pending:
        console.print("[yellow]No pending follow-ups at this time.[/yellow]")
        return

    table = Table(title=f"Pending Follow-ups ({len(pending)})")
    table.add_column("Company", width=22)
    table.add_column("Email", width=25)
    table.add_column("Attempts", width=8)
    table.add_column("Last Contact", width=12)
    table.add_column("Next Type", width=12)

    for lead in pending:
        # Calculate next outreach type
        attempts = lead.contact_attempts
        if attempts == 1:
            next_type = "follow_up_1"
        elif attempts == 2:
            next_type = "follow_up_2"
        elif attempts == 3:
            next_type = "follow_up_3"
        else:
            next_type = "done"

        last_contact = lead.last_contact_date.strftime("%m/%d") if lead.last_contact_date else "Never"

        table.add_row(
            lead.company_name[:22],
            (lead.contact.email or "")[:25],
            str(lead.contact_attempts),
            last_contact,
            next_type,
        )

    console.print(table)


@app.command()
def pipeline():
    """
    Show the complete sales pipeline status.

    Displays leads at each stage from import to conversion.
    """
    repo = get_repository()

    # Get stats
    db_stats = repo.get_stats()
    v_stats = repo.get_verification_stats()

    console.print(Panel.fit(
        "[bold]Al-Buraq Sales Pipeline[/bold]",
        title="Dashboard",
    ))

    # Pipeline stages
    table = Table(title="Lead Pipeline")
    table.add_column("Stage", style="cyan", width=20)
    table.add_column("Count", style="green", width=10)
    table.add_column("Status", width=15)

    total = db_stats["leads"]["total"]
    qualified = db_stats["leads"]["qualified"]
    verified = v_stats["verified"]
    social = v_stats["social_verified"]
    high_intent = v_stats["high_intent"]
    pending_v = v_stats["pending"]

    table.add_row("1. Imported", str(total), "[green]Complete[/green]")
    table.add_row("2. Qualified", str(qualified), "[green]Complete[/green]")
    table.add_row("3. Pending Verification", str(pending_v), "[yellow]In Progress[/yellow]")
    table.add_row("4. Verified", str(verified), "[green]Ready[/green]")
    table.add_row("   - Social Media", str(social), "[dim]Subset[/dim]")
    table.add_row("   - High Intent", str(high_intent), "[dim]Subset[/dim]")
    table.add_row("5. Contacted", str(db_stats["leads"]["new"]), "[cyan]Outreach[/cyan]")
    table.add_row("6. Converted", str(db_stats["leads"]["converted"]), "[bold green]Goal[/bold green]")

    console.print(table)

    # Recommendations
    console.print("\n[cyan]Recommendations:[/cyan]")
    if pending_v > 0:
        console.print(f"  - Run [bold]alburaq investigate --limit 10[/bold] to verify {pending_v} pending leads")
    if verified > 0:
        console.print(f"  - Run [bold]alburaq outreach --limit 5[/bold] to generate emails for {verified} verified leads")
    if social > 0:
        console.print(f"  - Prioritize [bold]alburaq outreach --social[/bold] for {social} socially verified leads")


# =============================================================================
# Dispatch Agent Commands
# =============================================================================

@app.command()
def dispatch(
    loads: int = typer.Option(5, "--loads", "-l", help="Number of loads to match"),
    matches: int = typer.Option(3, "--matches", "-m", help="Matches per load"),
):
    """
    Run dispatch matching to find carriers for loads.

    Generates sample loads and matches them to verified carriers.
    Shows halal status, match scores, and commission calculations.

    Examples:
        alburaq dispatch --loads 5
        alburaq dispatch --loads 10 --matches 5
    """
    from ..agents import DispatchAgent

    repo = get_repository()

    console.print(Panel.fit(
        "[bold green]Al-Buraq Dispatch[/bold green]\n"
        f"Matching {loads} loads to carriers...",
        title="Bismillah",
    ))

    agent = DispatchAgent(repository=repo)
    session = agent.run_dispatch_session(
        load_count=loads,
        matches_per_load=matches,
        use_sample_loads=True,
    )

    # Summary stats
    table = Table(title="Dispatch Session Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Loads", str(session.total_loads))
    table.add_row("Halal Loads", f"[green]{session.halal_loads}[/green]")
    table.add_row("Haram Loads (Skipped)", f"[red]{session.haram_loads}[/red]")
    table.add_row("Total Matches Found", str(session.total_matches))
    table.add_row("Duration", f"{session.duration_seconds:.2f}s")

    console.print(table)

    if not session.recommendations:
        console.print("\n[yellow]No loads to dispatch.[/yellow]")
        return

    # Show each load with matches
    console.print(f"\n[cyan]Load Recommendations ({len(session.recommendations)}):[/cyan]\n")

    for i, rec in enumerate(session.recommendations, 1):
        load = rec.load

        # Halal status color
        if rec.halal_status == "HALAL":
            halal_display = "[green]HALAL[/green]"
        elif rec.halal_status == "HARAM":
            halal_display = "[red]HARAM[/red]"
        else:
            halal_display = "[yellow]REVIEW[/yellow]"

        # Load header
        console.print(Panel(
            f"[bold]Route:[/bold] {load.origin.city}, {load.origin.state} → {load.destination.city}, {load.destination.state}\n"
            f"[bold]Commodity:[/bold] {load.commodity} | {halal_display}\n"
            f"[bold]Equipment:[/bold] {load.equipment_type.value if hasattr(load.equipment_type, 'value') else load.equipment_type}\n"
            f"[bold]Miles:[/bold] {load.loaded_miles} | [bold]Rate:[/bold] ${load.rate:,.2f} (${load.rate_per_mile:.2f}/mi)\n"
            f"[bold]Broker:[/bold] {load.broker.company_name}",
            title=f"Load #{i}",
            width=75,
        ))

        if rec.halal_status == "HARAM":
            console.print(f"  [red]Skipped: {rec.halal_reason}[/red]\n")
            continue

        if not rec.matches:
            console.print("  [yellow]No matching carriers found.[/yellow]\n")
            continue

        # Show matches
        match_table = Table(show_header=True, width=75)
        match_table.add_column("Carrier", width=22)
        match_table.add_column("State", width=5)
        match_table.add_column("Score", width=6)
        match_table.add_column("Commission", width=10)
        match_table.add_column("Charity", width=8)
        match_table.add_column("Why", width=20)

        for match in rec.matches:
            score_color = "green" if match.match_score >= 0.5 else "yellow"
            match_table.add_row(
                match.carrier_name[:22],
                match.carrier_state,
                f"[{score_color}]{match.match_score:.2f}[/{score_color}]",
                f"${match.estimated_commission:,.2f}",
                f"${match.charity_contribution:.2f}",
                match.match_reasons[0][:20] if match.match_reasons else "-",
            )

        console.print(match_table)
        console.print()

    # Commission summary
    total_commission = sum(
        rec.best_match.estimated_commission
        for rec in session.recommendations
        if rec.best_match
    )
    total_charity = sum(
        rec.best_match.charity_contribution
        for rec in session.recommendations
        if rec.best_match
    )

    if total_commission > 0:
        console.print(Panel.fit(
            f"[bold]Potential Revenue (if all dispatched):[/bold]\n\n"
            f"Total Commission (7%): [green]${total_commission:,.2f}[/green]\n"
            f"Charity Contribution (5%): [cyan]${total_charity:,.2f}[/cyan]\n\n"
            f"[dim]\"Built with integrity, dispatched with honesty\"[/dim]",
            title="Revenue Summary",
        ))


@app.command()
def match_load(
    origin: str = typer.Argument(..., help="Origin state (e.g., TX)"),
    destination: str = typer.Argument(..., help="Destination state (e.g., CA)"),
    commodity: str = typer.Option("General Freight", "--commodity", "-c", help="Commodity type"),
    equipment: str = typer.Option("dry_van", "--equipment", "-e", help="Equipment type"),
    rate: float = typer.Option(3000.0, "--rate", "-r", help="Total rate in dollars"),
    miles: int = typer.Option(1000, "--miles", "-m", help="Loaded miles"),
):
    """
    Find carrier matches for a specific load.

    Examples:
        alburaq match-load TX CA --commodity "Electronics" --rate 4200 --miles 1400
        alburaq match-load IL GA --equipment reefer --commodity "Fresh Produce"
    """
    from ..agents import DispatchAgent
    from ..models.load import Load, Location, TimeWindow, LoadDimensions, BrokerInfo
    from ..models.enums import EquipmentType

    repo = get_repository()

    # Parse equipment type
    try:
        equip_type = EquipmentType(equipment.lower())
    except ValueError:
        equip_type = EquipmentType.DRY_VAN

    # Check halal
    halal_result = check_commodity(commodity)

    if halal_result.status == "haram":
        console.print(Panel.fit(
            f"[red]HARAM Load Rejected[/red]\n\n"
            f"Commodity: {commodity}\n"
            f"Reason: {halal_result.reason}\n\n"
            f"[dim]Al-Buraq does not dispatch haram freight.[/dim]",
            title="Halal Filter",
        ))
        return

    # Create load
    load = Load(
        origin=Location(city="Origin", state=origin.upper(), zip_code="00000"),
        destination=Location(city="Destination", state=destination.upper(), zip_code="00000"),
        pickup_window=TimeWindow(
            earliest=datetime.utcnow() + timedelta(days=1),
            latest=datetime.utcnow() + timedelta(days=1, hours=4),
        ),
        delivery_window=TimeWindow(
            earliest=datetime.utcnow() + timedelta(days=3),
            latest=datetime.utcnow() + timedelta(days=3, hours=8),
        ),
        commodity=commodity,
        equipment_type=equip_type,
        rate=rate,
        loaded_miles=miles,
        dimensions=LoadDimensions(weight_lbs=40000),
        broker=BrokerInfo(company_name="Direct", mc_number="000000", contact_phone="N/A"),
        halal_status=halal_result.status,
    )

    console.print(Panel.fit(
        f"[bold green]Load Matching[/bold green]\n\n"
        f"Route: {origin.upper()} → {destination.upper()}\n"
        f"Commodity: {commodity} ([green]HALAL[/green])\n"
        f"Equipment: {equipment}\n"
        f"Rate: ${rate:,.2f} ({miles} mi = ${rate/miles:.2f}/mi)",
        title="Bismillah",
    ))

    agent = DispatchAgent(repository=repo)
    matches = agent.find_matches(load, limit=10)

    if not matches:
        console.print("\n[yellow]No matching carriers found. Try investigating more leads.[/yellow]")
        return

    # Show matches
    table = Table(title=f"Carrier Matches ({len(matches)} found)")
    table.add_column("Rank", width=4)
    table.add_column("Carrier", width=25)
    table.add_column("MC#", width=10)
    table.add_column("State", width=5)
    table.add_column("Score", width=6)
    table.add_column("Commission", width=10)
    table.add_column("Match Reasons", width=25)

    for i, match in enumerate(matches, 1):
        score_color = "green" if match.match_score >= 0.5 else "yellow" if match.match_score >= 0.3 else "red"
        reasons = " | ".join(match.match_reasons[:2])

        table.add_row(
            f"#{i}",
            match.carrier_name[:25],
            match.carrier_mc[:10],
            match.carrier_state,
            f"[{score_color}]{match.match_score:.2f}[/{score_color}]",
            f"${match.estimated_commission:,.2f}",
            reasons[:25],
        )

    console.print(table)

    # Best match details
    best = matches[0]
    console.print(Panel.fit(
        f"[bold]Best Match: {best.carrier_name}[/bold]\n\n"
        f"MC#: {best.carrier_mc}\n"
        f"Location: {best.carrier_state}\n"
        f"Equipment: {', '.join(best.carrier_equipment)}\n"
        f"Match Score: [green]{best.match_score:.0%}[/green]\n\n"
        f"[bold]Commission (7%):[/bold] ${best.estimated_commission:,.2f}\n"
        f"[bold]Charity (5%):[/bold] ${best.charity_contribution:,.2f}",
        title="Recommended Carrier",
    ))


# =============================================================================
# CSV Import Commands
# =============================================================================

@app.command()
def import_csv(
    filepath: str = typer.Argument(..., help="Path to FMCSA CSV file"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Maximum leads to import"),
    chunk_size: int = typer.Option(1000, "--chunk-size", help="Rows per chunk for memory efficiency"),
    no_save: bool = typer.Option(False, "--no-save", help="Don't save to database (preview only)"),
):
    """
    Import leads from an FMCSA CSV file.

    Handles large files (279MB+) efficiently by processing in chunks.
    Automatically detects column mappings using fuzzy matching.
    Only imports rows that have an email address.

    Examples:
        alburaq import-csv fmcsa_data.csv --limit 100
        alburaq import-csv carriers.csv --limit 500 --chunk-size 2000
    """
    from pathlib import Path
    from ..hunters import CSVHunter

    filepath_obj = Path(filepath)
    if not filepath_obj.exists():
        console.print(f"[red]Error: File not found: {filepath}[/red]")
        raise typer.Exit(1)

    # Show file info
    file_size_mb = filepath_obj.stat().st_size / (1024 * 1024)
    console.print(Panel.fit(
        f"[bold green]CSV Import[/bold green]\n"
        f"File: {filepath_obj.name}\n"
        f"Size: {file_size_mb:.1f} MB",
        title="Bismillah",
    ))

    # Initialize hunter with database connections
    repo = get_repository() if not no_save else None
    vector_store = get_vector_store() if not no_save else None
    hunter = CSVHunter(repository=repo, vector_store=vector_store)

    # Preview columns first
    console.print("\n[cyan]Detecting columns...[/cyan]")
    try:
        preview = hunter.preview_csv(filepath, rows=3)
        console.print(f"[green]Found {preview['total_columns']} columns[/green]")

        # Show mapping
        table = Table(title="Detected Column Mappings")
        table.add_column("Field", style="cyan")
        table.add_column("CSV Column", style="green")

        for field, col in preview["mapping"].items():
            table.add_row(field, col)

        console.print(table)

        if preview["unmapped"]:
            console.print(f"[yellow]Unmapped fields: {', '.join(preview['unmapped'][:5])}...[/yellow]")

    except Exception as e:
        console.print(f"[red]Error reading CSV: {e}[/red]")
        raise typer.Exit(1)

    # Confirm import
    console.print(f"\n[cyan]Importing leads (limit: {limit or 'unlimited'})...[/cyan]")

    # Progress tracking
    last_update = [0]

    def progress_callback(processed: int, found: int):
        if processed - last_update[0] >= 1000:
            console.print(f"  Processed: {processed:,} rows | Found: {found:,} leads", end="\r")
            last_update[0] = processed

    # Run import
    try:
        result = hunter.import_csv(
            filepath=filepath,
            limit=limit,
            chunk_size=chunk_size,
            require_email=True,
            save_to_db=not no_save,
            progress_callback=progress_callback,
        )
    except Exception as e:
        console.print(f"\n[red]Import error: {e}[/red]")
        raise typer.Exit(1)

    # Show results
    console.print("\n")  # Clear progress line

    table = Table(title="Import Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Rows Processed", f"{result.total_processed:,}")
    table.add_row("Leads Found", f"[bold green]{result.total_found:,}[/bold green]")
    table.add_row("Duplicates Skipped", f"{getattr(result, 'total_duplicates', 0):,}")
    table.add_row("Errors", str(len(result.errors)))
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")

    # Count qualified
    qualified = sum(1 for lead in result.leads if lead.is_qualified)
    table.add_row("Qualified Leads", f"[bold cyan]{qualified:,}[/bold cyan]")

    console.print(table)

    if result.errors:
        console.print(f"\n[yellow]First 3 errors:[/yellow]")
        for err in result.errors[:3]:
            console.print(f"  - {err}")

    if result.total_found > 0:
        console.print(f"\n[green]Successfully imported {result.total_found:,} leads![/green]")

        # Show sample
        if result.leads:
            console.print("\n[cyan]Sample leads:[/cyan]")
            sample_table = Table()
            sample_table.add_column("Company", width=25)
            sample_table.add_column("MC#", width=10)
            sample_table.add_column("Email", width=25)
            sample_table.add_column("State", width=5)
            sample_table.add_column("Score", width=6)

            for lead in result.leads[:5]:
                sample_table.add_row(
                    lead.company_name[:25],
                    lead.authority.mc_number[:10],
                    (lead.contact.email or "")[:25],
                    lead.fleet.home_base_state or "?",
                    f"{lead.lead_score:.2f}",
                )
            console.print(sample_table)
    else:
        console.print("\n[yellow]No leads with email addresses found.[/yellow]")


@app.command()
def preview_csv(
    filepath: str = typer.Argument(..., help="Path to CSV file"),
    rows: int = typer.Option(5, "--rows", "-r", help="Number of rows to preview"),
):
    """
    Preview a CSV file and show detected column mappings.

    Use this to verify the CSV structure before importing.
    """
    from pathlib import Path
    from ..hunters import CSVHunter

    filepath_obj = Path(filepath)
    if not filepath_obj.exists():
        console.print(f"[red]Error: File not found: {filepath}[/red]")
        raise typer.Exit(1)

    hunter = CSVHunter()

    try:
        preview = hunter.preview_csv(filepath, rows=rows)
    except Exception as e:
        console.print(f"[red]Error reading CSV: {e}[/red]")
        raise typer.Exit(1)

    # Show columns
    console.print(Panel.fit(
        f"[bold]CSV Preview[/bold]\n"
        f"File: {filepath_obj.name}\n"
        f"Columns: {preview['total_columns']}",
        title="Preview",
    ))

    # Show all columns
    console.print("\n[cyan]All columns:[/cyan]")
    for i, col in enumerate(preview["columns"]):
        console.print(f"  {i+1}. {col}")

    # Show mapping
    console.print("\n[cyan]Detected mappings:[/cyan]")
    table = Table()
    table.add_column("Field", style="cyan")
    table.add_column("CSV Column", style="green")

    for field, col in preview["mapping"].items():
        table.add_row(field, col)

    console.print(table)

    # Show sample data
    console.print(f"\n[cyan]Sample data ({rows} rows):[/cyan]")
    if preview["sample_rows"]:
        # Show key columns only
        key_cols = ["mc_number", "legal_name", "email", "phone", "state"]
        mapped_cols = [preview["mapping"].get(k) for k in key_cols if preview["mapping"].get(k)]

        if mapped_cols:
            sample_table = Table()
            for col in mapped_cols[:5]:
                sample_table.add_column(col[:15], width=20)

            for row in preview["sample_rows"]:
                values = [str(row.get(col, ""))[:20] for col in mapped_cols[:5]]
                sample_table.add_row(*values)

            console.print(sample_table)


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
