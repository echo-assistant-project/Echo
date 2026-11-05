import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('An allowed origin must contain only an http(s) scheme, host and optional port.')
    port = parsed.port
    host = parsed.hostname.lower()
    if ':' in host:
        host = '[' + host + ']'
    suffix = f':{port}' if port and port != (443 if parsed.scheme == 'https' else 80) else ''
    return f'{parsed.scheme}://{host}{suffix}'


def load_clients(path):
    raw = Path(path).read_bytes()
    if len(raw) > 256 * 1024:
        raise ValueError('Client configuration exceeds 256 KB.')
    data = json.loads(raw)
    if not isinstance(data, list) or not 1 <= len(data) <= 100:
        raise ValueError('Configure between 1 and 100 clients.')
    clients = {}
    for item in data:
        site = item['site_id']
        if not isinstance(site, str) or not re.fullmatch(r'[a-z][a-z0-9-]{1,62}', site) or site in clients:
            raise ValueError('Client site IDs must be unique lowercase identifiers.')
        branding = item['branding']
        if not isinstance(branding.get('name'), str) or not 1 <= len(branding['name']) <= 60:
            raise ValueError('A client name is required.')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', branding.get('accent', '')):
            raise ValueError('Brand accent must be a six-digit hex color.')
        if not isinstance(branding.get('greeting'), str) or not 1 <= len(branding['greeting']) <= 400:
            raise ValueError('A short greeting is required.')
        allowed = item['allowed_origins']
        if not isinstance(allowed, list) or not allowed or len(allowed) > 20:
            raise ValueError('Configure explicit allowed origins.')
        capabilities = item['enabled_capabilities']
        if not isinstance(capabilities, list) or any(c != 'chat' for c in capabilities):
            raise ValueError('Only text chat is supported by this web engine.')
        knowledge = item.get('knowledge', [])
        if not isinstance(knowledge, list) or len(knowledge) > 100:
            raise ValueError('Approved knowledge must contain at most 100 passages.')
        ids = set()
        for passage in knowledge:
            if (not isinstance(passage.get('id'), str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', passage['id'])
                    or passage['id'] in ids or not isinstance(passage.get('text'), str)
                    or not 1 <= len(passage['text']) <= 4000 or not isinstance(passage.get('title'), str)
                    or not 1 <= len(passage['title']) <= 120):
                raise ValueError('Approved passages need unique IDs, titles and bounded text.')
            ids.add(passage['id'])
        clients[site] = {**item, 'knowledge': knowledge, 'allowed_origins': tuple(origin(value) for value in allowed)}
    return clients
