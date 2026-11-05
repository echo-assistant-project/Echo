"""Import the existing headless ECHO engine, never the desktop orchestrator."""
import re
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[2] / 'desktop' / 'EchoDesktop'
sys.path.insert(0, str(ENGINE_ROOT))
from echo_desktop.backend import Backend, SYSTEM_PROMPT
from echo_desktop.llm import ChatClient, LlmError


def conversation(client, model_url, model_key, model):
    if model == 'auto':
        raise ValueError('Choose a specific model or auto:reliable to avoid parallel provider races.')
    prompt = (SYSTEM_PROMPT + '\nYou are the website assistant for ' + client['branding']['name'] + '. '
              'Business-specific facts must come from this client’s approved reference passages. '
              'Never assume prices, policies, availability or contact details. '
              'You cannot access visitor devices, private files, other clients, or external tools.')
    return Backend(ChatClient(model_url, model_key, model=model), system_prompt=prompt)


def references(client, query):
    words = set(re.findall(r'\w+', query.lower()))
    ranked = []
    for passage in client['knowledge']:
        terms = set(re.findall(r'\w+', (passage['title'] + ' ' + passage['text']).lower()))
        score = len(words & terms)
        if score:
            ranked.append((score, passage))
    ranked.sort(key=lambda item: item[0], reverse=True)
    hits = [passage for _, passage in ranked[:3]]
    context = '\n\n'.join(f"[{p['id']}] {p['title']}\n{p['text']}" for p in hits)
    return context or 'No matching approved business information is available.', [
        {'id': p['id'], 'title': p['title']} for p in hits]
