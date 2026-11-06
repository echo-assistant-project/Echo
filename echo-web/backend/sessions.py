from collections import deque
from dataclasses import dataclass, field
import secrets
import threading
import time


@dataclass
class Session:
    site: str
    origin: str
    engine: object
    expires: float
    busy: object = field(default_factory=threading.Lock)


class Sessions:
    def __init__(self, ttl=1800, maximum=100, clock=time.monotonic):
        self.ttl, self.maximum, self.clock = ttl, maximum, clock
        self.items = {}
        self.lock = threading.Lock()
        self.requests = {}

    def rate_allowed(self, address):
        with self.lock:
            now = self.clock()
            self.requests = {ip: times for ip, times in self.requests.items() if times and now - times[-1] < 60}
            if address not in self.requests and len(self.requests) >= 1000:
                return False
            times = self.requests.setdefault(address, deque())
            while times and now - times[0] >= 60:
                times.popleft()
            if len(times) >= 30:
                return False
            times.append(now)
            return True

    def create(self, site, origin, factory):
        with self.lock:
            now = self.clock()
            self.items = {token: session for token, session in self.items.items()
                          if session.expires > now or session.busy.locked()}
            if len(self.items) >= self.maximum:
                raise OverflowError('Session capacity reached. Try later.')
            token = secrets.token_urlsafe(32)
            self.items[token] = Session(site, origin, factory(), now + self.ttl)
            return token

    def get(self, token, site, origin):
        with self.lock:
            session = self.items.get(token)
            if session is None or session.site != site or session.origin != origin or session.expires <= self.clock():
                raise PermissionError('The conversation session is invalid or expired.')
            session.expires = self.clock() + self.ttl
            return session

    def acquire(self, token, site, origin):
        with self.lock:
            session = self.items.get(token)
            if session is None or session.site != site or session.origin != origin or session.expires <= self.clock():
                raise PermissionError('The conversation session is invalid or expired.')
            if not session.busy.acquire(blocking=False):
                raise BlockingIOError('A reply is already in progress.')
            session.expires = self.clock() + self.ttl
            return session

    def delete(self, token, session):
        with self.lock:
            if self.items.get(token) is session:
                del self.items[token]
