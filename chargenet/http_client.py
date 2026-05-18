from __future__ import annotations

import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USER_AGENT = "ChargeNetEuropePortfolioAudit/0.1 (public-data decision-support prototype)"


class FetchError(RuntimeError):
    """Raised when a public data request cannot be completed."""


RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}


def fetch_text(url: str, *, timeout: int = 60, retries: int = 3, delay_seconds: float = 1.5) -> str:
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
            return raw.decode("utf-8-sig")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in RETRYABLE_HTTP_STATUS and attempt < retries:
                retry_after = exc.headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after and retry_after.isdigit() else delay_seconds * (attempt + 1)
                time.sleep(wait_seconds)
                continue
            raise FetchError(f"HTTP {exc.code} for {url}: {body[:500]}") from exc
        except (URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(delay_seconds * (attempt + 1))

    raise FetchError(f"Failed to fetch {url}: {last_error}") from last_error
