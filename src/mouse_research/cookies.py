"""Cookie management for authenticated newspaper site access.

Uses Playwright storage_state() for save/load — NOT launch_persistent_context()
which has a known bug (GitHub #36139) where session cookies don't persist.
"""
from pathlib import Path

from rich.console import Console

from mouse_research.config import get_config

COOKIE_DIR = Path.home() / ".mouse-research" / "cookies"

# Domain to login URL mapping
LOGIN_URLS = {
    "newspapers.com": "https://www.newspapers.com/signin/?next_url=/?",
    "lancasteronline.com": "https://lancasteronline.com/users/login/",
    "ydr.com": "https://www.ydr.com/",
    "eveningsun.com": "https://www.eveningsun.com/",
}


def cookie_path(domain: str) -> Path:
    """Return the cookie storage path for a domain."""
    return COOKIE_DIR / f"{domain}.json"


def interactive_login(domain: str, console: Console | None = None) -> bool:
    """Open a visible browser for manual login and save cookies.

    Opens a non-headless Chromium window at the domain's login page.
    Waits for the user to complete login manually.
    On success, saves cookies via storage_state() and closes the browser.

    Returns True if cookies were saved, False on error.
    """
    if console is None:
        console = Console()

    login_url = LOGIN_URLS.get(domain)
    if not login_url:
        login_url = f"https://www.{domain}/"
        console.print(f"[yellow]No known login URL for {domain} — opening {login_url}[/yellow]")

    COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    config = get_config()

    console.print(f"Opening browser for [bold]{domain}[/bold] login...")
    console.print("[dim]Log in manually, then press Enter here when done.[/dim]")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",
        )
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")

        # Wait for user to complete login
        input("\nPress Enter after logging in...")

        # Save cookies via storage_state
        save_path = str(cookie_path(domain))
        context.storage_state(path=save_path)
        console.print(f"[green]Cookies saved to {save_path}[/green]")

        browser.close()

    return True


def load_cookies(domain: str) -> str | None:
    """Return the cookie file path if it exists, None otherwise.

    The returned path is passed to browser.new_context(storage_state=path).
    Must be passed at context creation time — cannot be injected later.
    """
    path = cookie_path(domain)
    if path.exists():
        return str(path)
    return None


def check_auth(domain: str, console: Console | None = None) -> bool:
    """Pre-flight auth check: load cookies and verify they're still valid.

    Opens a headless browser, loads saved cookies, navigates to the domain,
    and checks if we're redirected to a login page.

    Returns True if authenticated, False if cookies are expired/missing.
    """
    if console is None:
        console = Console()

    storage = load_cookies(domain)
    if storage is None:
        console.print(f"[yellow]No cookies found for {domain}. Run: mouse-research login {domain}[/yellow]")
        return False

    config = get_config()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=storage)
        page = context.new_page()

        try:
            # Navigate to a page that requires auth
            check_url = f"https://www.{domain}/"
            page.goto(check_url, wait_until="domcontentloaded", timeout=15000)

            # Check if we landed on a login/sign-in page
            current_url = page.url.lower()
            if "sign-in" in current_url or "login" in current_url or "signin" in current_url:
                console.print(f"[yellow]Session expired for {domain}. Run: mouse-research login {domain}[/yellow]")
                browser.close()
                return False

            # Refresh cookies on successful authenticated load
            context.storage_state(path=storage)
            browser.close()
            return True

        except Exception as e:
            console.print(f"[yellow]Auth check failed for {domain}: {e}[/yellow]")
            browser.close()
            return False
