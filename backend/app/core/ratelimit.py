"""Attempt limits on the two routes where guessing is the attack."""
from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings


class AttemptLimiter:
    """A sliding window of recent failures per key."""

    def __init__(self, *, limit: int, window_seconds: float, max_keys: int = 4096):
        self._limit = max(1, limit)
        self._window = float(window_seconds)
        self._max_keys = max_keys
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def limit(self) -> int:
        return self._limit

    def retry_after(self, key: str) -> int | None:
        """Seconds until `key` may try again, or None if it may try now."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                return None
            self._expire(hits, now)
            if not hits:
                del self._hits[key]
                return None
            if len(hits) < self._limit:
                return None
            return max(1, int(self._window - (now - hits[0])) + 1)

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = deque()
                self._hits[key] = hits
            self._expire(hits, now)
            hits.append(now)
            self._hits.move_to_end(key)
            self._evict(now)

    def clear(self, key: str) -> None:
        """Forget a key's failures."""
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def tracked_keys(self) -> int:
        with self._lock:
            return len(self._hits)

    def _expire(self, hits: deque[float], now: float) -> None:
        cutoff = now - self._window
        while hits and hits[0] <= cutoff:
            hits.popleft()

    def _evict(self, now: float) -> None:
        """Keep the map bounded."""
        if len(self._hits) <= self._max_keys:
            return
        for key in list(self._hits):
            hits = self._hits[key]
            self._expire(hits, now)
            if not hits:
                del self._hits[key]
        while len(self._hits) > self._max_keys:
            self._hits.popitem(last=False)


login_by_address = AttemptLimiter(
    limit=settings.LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_WINDOW_SECONDS,
)
login_by_account = AttemptLimiter(
    limit=settings.LOGIN_MAX_ATTEMPTS * 2,
    window_seconds=settings.LOGIN_WINDOW_SECONDS * 3,
)
registration_by_address = AttemptLimiter(
    limit=settings.REGISTER_MAX_ATTEMPTS,
    window_seconds=settings.REGISTER_WINDOW_SECONDS,
)

reset_request_by_address = AttemptLimiter(
    limit=settings.REGISTER_MAX_ATTEMPTS,
    window_seconds=settings.REGISTER_WINDOW_SECONDS,
)
reset_lookup_by_address = AttemptLimiter(
    limit=settings.REGISTER_MAX_ATTEMPTS * 4,
    window_seconds=settings.REGISTER_WINDOW_SECONDS,
)
reset_answers_by_address = AttemptLimiter(
    limit=settings.LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_WINDOW_SECONDS,
)
reset_redeem_by_address = AttemptLimiter(
    limit=settings.LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_WINDOW_SECONDS,
)
reset_status_by_address = AttemptLimiter(limit=400, window_seconds=900)
password_change_by_account = AttemptLimiter(
    limit=settings.LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_WINDOW_SECONDS,
)

# Derived, not listed by hand: a limiter left out leaks counters between tests.
_ALL = tuple(v for v in list(globals().values()) if isinstance(v, AttemptLimiter))


def reset_all() -> None:
    """Forget every counter."""
    for limiter in _ALL:
        limiter.reset()


def client_address(request: Request) -> str:
    """The address to hold responsible for this request."""
    hops = max(0, settings.TRUSTED_PROXY_HOPS)
    if hops:
        # From the right: each proxy appends the peer it saw, so the left end is
        # whatever the caller typed.
        chain = [part.strip() for part
                 in request.headers.get("x-forwarded-for", "").split(",")
                 if part.strip()]
        if len(chain) >= hops:
            return chain[-hops]
    # Not always the socket: uvicorn's --proxy-headers overwrites this from the
    # header first, which is why 0 behind a proxy is forgeable rather than merely coarse.
    return request.client.host if request.client else "unknown"


def _account_key(email: str) -> str:
    return (email or "").strip().lower()


def _refuse(seconds: int) -> None:
    """One message for every limit, on purpose."""
    minutes = max(1, round(seconds / 60))
    wait = f"{seconds} seconds" if seconds < 90 else f"{minutes} minutes"
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many sign-in attempts. Please wait about {wait} and try again.",
        headers={"Retry-After": str(seconds)},
    )


def guard_login(request: Request, email: str) -> None:
    """Refuse a login attempt that is over either limit."""
    address = client_address(request)
    for limiter, key in ((login_by_address, address),
                         (login_by_account, _account_key(email))):
        seconds = limiter.retry_after(key)
        if seconds is not None:
            _refuse(seconds)


def note_login_failure(request: Request, email: str) -> None:
    login_by_address.record_failure(client_address(request))
    login_by_account.record_failure(_account_key(email))


def note_login_success(request: Request, email: str) -> None:
    """Clear both counters, which is what keeps this from locking out real people."""
    login_by_address.clear(client_address(request))
    login_by_account.clear(_account_key(email))


def guard_registration(request: Request) -> None:
    seconds = registration_by_address.retry_after(client_address(request))
    if seconds is not None:
        minutes = max(1, round(seconds / 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=("Too many accounts created from this address. Please wait about "
                    f"{minutes} minutes and try again."),
            headers={"Retry-After": str(seconds)},
        )


def note_registration(request: Request) -> None:
    """Counted on success, not on failure — the row is what is being rationed."""
    registration_by_address.record_failure(client_address(request))


def guard_reset_request(request: Request) -> None:
    """Before creating a queue entry — on `/answers` and `/appeal`, not on `/forgot`."""
    seconds = reset_request_by_address.retry_after(client_address(request))
    if seconds is not None:
        _refuse_generic(seconds, "reset requests")


def note_reset_request(request: Request) -> None:
    reset_request_by_address.record_failure(client_address(request))


def guard_reset_lookup(request: Request) -> None:
    """Before reading back which questions an address has."""
    seconds = reset_lookup_by_address.retry_after(client_address(request))
    if seconds is not None:
        _refuse_generic(seconds, "reset requests")


def note_reset_lookup(request: Request) -> None:
    reset_lookup_by_address.record_failure(client_address(request))


def guard_reset_answers(request: Request) -> None:
    """The one endpoint in this flow where guessing is realistic arithmetic."""
    seconds = reset_answers_by_address.retry_after(client_address(request))
    if seconds is not None:
        _refuse_generic(seconds, "attempts")


def note_reset_answer_attempt(request: Request) -> None:
    """Counted on every attempt, right or wrong."""
    reset_answers_by_address.record_failure(client_address(request))


def guard_reset_status(request: Request) -> None:
    seconds = reset_status_by_address.retry_after(client_address(request))
    if seconds is not None:
        _refuse_generic(seconds, "status checks")


def note_reset_status(request: Request) -> None:
    reset_status_by_address.record_failure(client_address(request))


def guard_reset_redeem(request: Request) -> None:
    seconds = reset_redeem_by_address.retry_after(client_address(request))
    if seconds is not None:
        _refuse_generic(seconds, "attempts")


def note_reset_failure(request: Request) -> None:
    reset_redeem_by_address.record_failure(client_address(request))


def note_reset_success(request: Request) -> None:
    reset_redeem_by_address.clear(client_address(request))


def guard_password_change(user_id: int) -> None:
    """Keyed on the account, not the address — the caller is already identified."""
    seconds = password_change_by_account.retry_after(str(user_id))
    if seconds is not None:
        _refuse_generic(seconds, "attempts")


def note_password_change_failure(user_id: int) -> None:
    password_change_by_account.record_failure(str(user_id))


def note_password_change_success(user_id: int) -> None:
    password_change_by_account.clear(str(user_id))


def _refuse_generic(seconds: int, noun: str) -> None:
    """`_refuse` with a different noun, and the same discipline about saying nothing."""
    minutes = max(1, round(seconds / 60))
    wait = f"{seconds} seconds" if seconds < 90 else f"{minutes} minutes"
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many {noun}. Please wait about {wait} and try again.",
        headers={"Retry-After": str(seconds)},
    )
