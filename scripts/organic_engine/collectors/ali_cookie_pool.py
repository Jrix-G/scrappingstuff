"""Pool de sessions AliExpress — cookie x5sec via Playwright, requêtes via curl_cffi.

Architecture :
  1. Playwright headless (Chromium ARM64) obtient un cookie x5sec valide (~30min)
     en chargeant la homepage AliExpress (exécution du challenge JS Alibaba WAF).
  2. curl_cffi réutilise ce cookie pour des dizaines de requêtes sans relancer le navigateur.
  3. Pool de N sessions (1 par IP WireGuard) → rotation automatique.

Valabilité x5sec :
  - IP résidentielle/4G  : ~2-4h
  - IP datacenter (OVH)  : ~15-25min
  → Sur les 14 IPs WireGuard datacenter, renouveler toutes les 20min.
    Avec 8 req/IP/heure conservateur = 14 × 8 = 112 req/h soit ~2 700 req/jour.

Prérequis :
  pip install playwright curl_cffi
  playwright install chromium
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    from playwright.async_api import async_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False

try:
    from curl_cffi import requests as creq
    _HAS_CURL = True
except ImportError:
    _HAS_CURL = False

# Script injecté avant chaque page — passe les vérifications bot basiques d'Alibaba
_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
    const ctx = this.getContext('2d');
    if (ctx) {
        const d = ctx.getImageData(0, 0, this.width, this.height);
        for (let i = 0; i < d.data.length; i += 100) d.data[i] ^= 1;
        ctx.putImageData(d, 0, 0);
    }
    return origToDataURL.apply(this, arguments);
};
"""

_PUNISH_MARKERS = (
    "_____tmd_____/punish",
    '"action":"captcha"',
    "x5secdata",
    "slidecaptcha",
    "aecaptcha",
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


@dataclass
class _AliSession:
    vpn_interface: Optional[str] = None   # ex: "wg0" — None = IP locale
    cookies: dict = field(default_factory=dict)
    expires_at: float = 0.0

    def is_valid(self) -> bool:
        return time.time() < self.expires_at and bool(self.cookies.get("x5sec"))

    async def refresh(self) -> None:
        """Lance Playwright pour obtenir un x5sec frais depuis la homepage AliExpress."""
        if not _HAS_PLAYWRIGHT:
            return
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",       # indispensable sur Pi (peu de /dev/shm)
                    "--disable-blink-features=AutomationControlled",
                    "--disable-webgl",               # réduit l'empreinte headless
                ],
            )
            ctx = await browser.new_context(
                user_agent=_UA,
                viewport={"width": 1366, "height": 768},
                locale="en-US",
            )
            await ctx.add_init_script(_STEALTH_SCRIPT)
            page = await ctx.new_page()
            try:
                # Charge la homepage — le challenge JS x5sec s'exécute ici
                await page.goto(
                    "https://www.aliexpress.com/",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                await asyncio.sleep(2.5)  # laisse le challenge se terminer
                raw = await ctx.cookies()
                self.cookies = {c["name"]: c["value"] for c in raw}
            finally:
                await browser.close()

        if "x5sec" in self.cookies:
            # Durée conservatrice : 20min pour datacenter, 2h pour résidentiel
            ttl = 1200 if self.vpn_interface else 7200
            self.expires_at = time.time() + ttl
        else:
            self.expires_at = time.time() + 300  # retry dans 5min

    def _curl_session(self) -> "creq.Session":
        s = creq.Session(impersonate="chrome131")
        s.headers.update({
            "accept-language": "en-US,en;q=0.9",
            "referer": "https://www.aliexpress.com/",
            "user-agent": _UA,
        })
        for k, v in self.cookies.items():
            s.cookies.set(k, v, domain=".aliexpress.com")
        return s

    def fetch(self, url: str) -> tuple[bool, str]:
        """Retourne (blocked, html). Vérifier is_valid() avant d'appeler."""
        if not _HAS_CURL:
            return True, ""
        s = self._curl_session()
        try:
            r = s.get(url, timeout=25)
            blocked = any(m in r.text for m in _PUNISH_MARKERS) or len(r.text) < 5_000
            if blocked:
                self.expires_at = 0.0  # force le refresh au prochain appel
            return blocked, r.text
        except Exception:
            return True, ""


class AliCookiePool:
    """Pool multi-sessions AliExpress avec renouvellement automatique.

    Usage :
        pool = AliCookiePool(n_sessions=3)   # 3 sessions sur l'IP locale
        blocked, html = await pool.fetch("https://www.aliexpress.com/af/phone-holder.html")
    """

    def __init__(
        self,
        n_sessions: int = 1,
        vpn_interfaces: list[str] | None = None,
    ):
        if vpn_interfaces:
            self._sessions = [_AliSession(vpn_interface=iface) for iface in vpn_interfaces]
        else:
            self._sessions = [_AliSession() for _ in range(n_sessions)]

    async def _ensure(self, s: _AliSession) -> None:
        if not s.is_valid():
            await s.refresh()

    async def fetch(self, url: str) -> tuple[bool, str]:
        """Essaie toutes les sessions dans l'ordre, refresh si nécessaire."""
        for s in self._sessions:
            await self._ensure(s)
            if not s.is_valid():
                continue  # refresh a échoué (playwright absent / bloqué)
            blocked, html = s.fetch(url)
            if not blocked:
                return False, html
        return True, ""


# ── Point d'entrée de test ────────────────────────────────────────────────────

async def _test():
    import urllib.parse
    pool = AliCookiePool(n_sessions=1)
    keywords = ["ceiling fan", "yoga mat"]
    for kw in keywords:
        url = "https://www.aliexpress.com/af/" + urllib.parse.quote(kw) + ".html"
        blocked, html = await pool.fetch(url)
        if not blocked:
            import re
            sales = re.findall(r'tradeDesc"?\s*:\s*"([^"]*?)"', html)
            print(f"  {kw}: {len(sales)} compteurs — ex: {sales[:2]}")
        else:
            print(f"  {kw}: bloqué")


if __name__ == "__main__":
    asyncio.run(_test())
