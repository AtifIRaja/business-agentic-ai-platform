"""
Al-Buraq Tunnel Manager

Creates a public internet tunnel using ngrok to expose the local API server.
Perfect for sharing your API with OpenAI Agent Builder, external integrations,
or quick demos without deploying to a cloud provider.

REQUIREMENTS:
- ngrok account (free tier available at https://ngrok.com)
- pyngrok installed: pip install pyngrok
- ngrok authtoken configured: ngrok config add-authtoken YOUR_TOKEN

USAGE:
    alburaq share
    # or
    python -m al_buraq.tunnel
"""

import sys
import time
import threading
from typing import Optional

from pyngrok import ngrok, conf
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live


console = Console()


class TunnelManager:
    """Manages ngrok tunnel for Al-Buraq API"""

    def __init__(self, port: int = 8000, region: str = "us"):
        """
        Initialize tunnel manager.

        Args:
            port: Local port to tunnel (default: 8000)
            region: ngrok region (us, eu, ap, au, sa, jp, in)
        """
        self.port = port
        self.region = region
        self.tunnel = None
        self.public_url = None
        self.running = False

    def start(self, authtoken: Optional[str] = None) -> str:
        """
        Start ngrok tunnel.

        Args:
            authtoken: Optional ngrok authtoken (if not already configured)

        Returns:
            Public URL of the tunnel

        Raises:
            Exception: If tunnel fails to start
        """
        try:
            # Set authtoken if provided
            if authtoken:
                ngrok.set_auth_token(authtoken)

            # Configure ngrok
            conf.get_default().region = self.region

            # Start tunnel
            console.print("[cyan]Starting ngrok tunnel...[/cyan]")
            self.tunnel = ngrok.connect(self.port, bind_tls=True)
            self.public_url = self.tunnel.public_url
            self.running = True

            return self.public_url

        except Exception as e:
            error_msg = str(e)

            # Check for common errors
            if "authtoken" in error_msg.lower() or "authentication" in error_msg.lower():
                console.print("\n[red]ERROR: ngrok authtoken not configured![/red]\n")
                console.print("[yellow]To fix this:[/yellow]")
                console.print("1. Sign up at https://ngrok.com (free)")
                console.print("2. Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken")
                console.print("3. Configure it: ngrok config add-authtoken YOUR_TOKEN")
                console.print("4. Or pass it: alburaq share --authtoken YOUR_TOKEN\n")
                raise Exception("ngrok authtoken required")

            elif "already in use" in error_msg.lower():
                console.print(f"\n[red]ERROR: Port {self.port} is already in use![/red]\n")
                console.print("[yellow]Solutions:[/yellow]")
                console.print(f"1. Stop the process using port {self.port}")
                console.print("2. Use a different port: alburaq share --port 8001\n")
                raise Exception(f"Port {self.port} already in use")

            else:
                console.print(f"\n[red]ERROR: Failed to start tunnel: {error_msg}[/red]\n")
                raise

    def stop(self):
        """Stop ngrok tunnel"""
        if self.tunnel:
            try:
                ngrok.disconnect(self.tunnel.public_url)
                self.running = False
                console.print("[yellow]Tunnel stopped.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error stopping tunnel: {e}[/red]")

    def get_urls(self) -> dict:
        """Get all relevant URLs for the tunnel"""
        if not self.public_url:
            return {}

        base_url = self.public_url.replace("http://", "https://")  # Ensure HTTPS

        return {
            "base": base_url,
            "docs": f"{base_url}/docs",
            "redoc": f"{base_url}/redoc",
            "openapi": f"{base_url}/openapi.json",
            "health": f"{base_url}/health",
            "hunt": f"{base_url}/v1/agent/hunt",
            "verify": f"{base_url}/v1/agent/verify",
            "dispatch": f"{base_url}/v1/agent/dispatch",
            "leads": f"{base_url}/v1/leads/verified",
            "stats": f"{base_url}/v1/stats",
        }

    def display_info(self):
        """Display tunnel information in a nice format"""
        if not self.public_url:
            console.print("[red]No tunnel active[/red]")
            return

        urls = self.get_urls()

        # Main panel
        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]Tunnel Active![/bold green]\n\n"
            f"[bold]Public URL:[/bold] [cyan]{urls['base']}[/cyan]\n"
            f"[bold]OpenAPI Schema:[/bold] [cyan]{urls['openapi']}[/cyan]\n\n"
            f"[dim]Your local API is now accessible from anywhere on the internet.[/dim]",
            title="Al-Buraq Internet Tunnel",
            border_style="green",
        ))

        # Endpoints table
        table = Table(title="Public Endpoints", show_header=True)
        table.add_column("Purpose", style="cyan", width=20)
        table.add_column("URL", style="white", width=60)

        table.add_row("Swagger UI", urls['docs'])
        table.add_row("ReDoc", urls['redoc'])
        table.add_row("OpenAPI Schema", urls['openapi'])
        table.add_row("Health Check", urls['health'])
        table.add_row("Hunt Agent", urls['hunt'])
        table.add_row("Verify Agent", urls['verify'])
        table.add_row("Dispatch Agent", urls['dispatch'])
        table.add_row("Verified Leads", urls['leads'])
        table.add_row("Statistics", urls['stats'])

        console.print(table)

        # Instructions
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print(f"1. Test it: [white]{urls['health']}[/white]")
        console.print(f"2. View docs: [white]{urls['docs']}[/white]")
        console.print(f"3. For OpenAI Agent Builder: Copy [white]{urls['openapi']}[/white]")
        console.print(f"4. Share with team: [white]{urls['base']}[/white]\n")

        console.print("[yellow]Press Ctrl+C to stop the tunnel[/yellow]\n")

    def monitor(self):
        """Monitor tunnel status and keep it alive"""
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping tunnel...[/yellow]")
            self.stop()


def start_tunnel(
    port: int = 8000,
    region: str = "us",
    authtoken: Optional[str] = None,
    display: bool = True
) -> TunnelManager:
    """
    Start an ngrok tunnel and return the manager.

    Args:
        port: Local port to tunnel
        region: ngrok region
        authtoken: Optional ngrok authtoken
        display: Whether to display tunnel info

    Returns:
        TunnelManager instance

    Raises:
        Exception: If tunnel fails to start
    """
    manager = TunnelManager(port=port, region=region)

    try:
        public_url = manager.start(authtoken=authtoken)

        if display:
            manager.display_info()

        return manager

    except Exception as e:
        console.print(f"[red]Failed to start tunnel: {e}[/red]")
        raise


def main():
    """
    Main entry point for direct execution.

    Usage:
        python -m al_buraq.tunnel
    """
    console.print(Panel.fit(
        "[bold green]Al-Buraq Tunnel Manager[/bold green]\n"
        "Creating public internet tunnel...",
        title="Bismillah",
    ))

    try:
        manager = start_tunnel(port=8000, display=True)
        manager.monitor()

    except KeyboardInterrupt:
        console.print("\n[yellow]Tunnel stopped by user[/yellow]")
        sys.exit(0)

    except Exception as e:
        console.print(f"\n[red]Tunnel error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
