"""Cliente HTTP educado: respeta robots.txt, espera entre pedidos y reintenta."""
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = "FiguraTodoBot/1.0 (comparador de precios de figuras; +https://github.com/kildren94/figuratodo)"
DELAY = float(__import__("os").environ.get("FIGURATODO_DELAY", "1.0"))          # segundos entre pedidos a una misma tienda
TIMEOUT = 20


class Client:
    def __init__(self, base_url: str, delay: float = DELAY, deadline: float = None):
        self.base = base_url.rstrip("/")
        self.delay = delay
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-CL,es;q=0.9"})
        self._last = 0.0
        self.robots = urllib.robotparser.RobotFileParser()
        try:
            r = self.s.get(self.base + "/robots.txt", timeout=TIMEOUT)
            self.robots.parse(r.text.splitlines() if r.ok else [])
        except requests.RequestException:
            self.robots.parse([])
        self.requests = 0
        self.deadline = deadline          # time.time() a partir del cual no se hacen más pedidos
        self.consecutive_fail = 0         # si la tienda deja de responder, se corta
        self.errors = {}        # motivo -> cantidad, para diagnosticar tiendas que fallan
        self.last_headers = {}

    def _err(self, why):
        self.errors[why] = self.errors.get(why, 0) + 1

    def out_of_time(self) -> bool:
        return (self.deadline is not None and time.time() > self.deadline) or self.consecutive_fail >= 15

    def allowed(self, url: str) -> bool:
        return self.robots.can_fetch(USER_AGENT, url)

    def get(self, path_or_url: str, *, params=None, expect_json=False, retries=2):
        url = path_or_url if path_or_url.startswith("http") else urljoin(self.base + "/", path_or_url.lstrip("/"))
        if self.out_of_time():
            self._err("tiempo agotado" if self.consecutive_fail < 15 else "la tienda dejó de responder")
            return None
        if not self.allowed(url):
            self._err("bloqueado por robots.txt")
            return None
        for attempt in range(retries + 1):
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            self.requests += 1
            try:
                r = self.s.get(url, params=params, timeout=TIMEOUT)
            except requests.RequestException as e:
                if attempt < retries:
                    time.sleep(3 * (attempt + 1))
                    continue
                self._err(type(e).__name__)
                self.consecutive_fail += 1
                return None
            if r.status_code in (429, 503) and attempt < retries:
                time.sleep(10 * (attempt + 1))
                continue
            if not r.ok:
                self._err(f"HTTP {r.status_code}")
                if r.status_code >= 500 or r.status_code in (403, 429):
                    self.consecutive_fail += 1
                return None
            self.consecutive_fail = 0
            self.last_headers = r.headers
            if expect_json:
                try:
                    return r.json()
                except ValueError:
                    self._err("respuesta no es JSON")
                    return None
            return r
        return None

    @property
    def host(self):
        return urlparse(self.base).netloc
