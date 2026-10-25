"""Public-web research, with explicit provenance and transparent failure states.

BRAVE_SEARCH_API_KEY is optional. Without a key, no live claims are made.
The source excerpts are search-result snippets, not authenticated full job postings.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape


def clean(s, maxlen=1200):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', str(s or '')))).strip()[:maxlen]


def research(role, company='', job_description=''):
    role = clean(role, 160)
    company = clean(company, 160)
    jd = clean(job_description, 20000)
    result = {
        'role': role, 'company': company,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'status': 'not_configured', 'sources': [],
        'research_excerpt': '', 'job_description_provided': bool(jd),
        'note': 'Live web research requires BRAVE_SEARCH_API_KEY on your backend. Add an actual job posting for a stronger assessment.'
    }
    key = os.getenv('BRAVE_SEARCH_API_KEY', '').strip()
    if not key:
        return result
    if not company:
        result['status'] = 'needs_company'
        result['note'] = 'Enter a company to research its published role expectations.'
        return result
    queries = [
        f'"{company}" "{role}" jobs responsibilities requirements careers',
        f'"{company}" careers "{role}" skills hiring'
    ]
    sources = []
    seen = set()
    had_error = False
    for query in queries:
        params = urllib.parse.urlencode({'q': query, 'count': 6, 'search_lang': 'en', 'safesearch': 'moderate'})
        url = 'https://api.search.brave.com/res/v1/web/search?' + params
        req = urllib.request.Request(url, headers={'Accept': 'application/json', 'X-Subscription-Token': key})
        try:
            with urllib.request.urlopen(req, timeout=9) as resp:
                data = json.load(resp)
            for item in data.get('web', {}).get('results', []):
                link = item.get('url', '')
                if not link.startswith('https://') or link in seen:
                    continue
                seen.add(link)
                text = clean(item.get('description', ''))
                title = clean(item.get('title', ''), 250)
                if not title or len(text) < 25:
                    continue
                sources.append({'title': title, 'url': link, 'excerpt': text[:550],
                                'kind': 'public search snippet — not a verified job posting'})
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, OSError):
            had_error = True
    sources = sources[:8]
    result['sources'] = sources
    result['research_excerpt'] = '\n'.join(s['title'] + ': ' + s['excerpt'] for s in sources)[:4500]
    if sources:
        result['status'] = 'sources_found'
        result['note'] = 'Research uses public search excerpts, not verified full postings. Open the links to check role relevance, dates, and requirements. This is a provisional fit estimate.'
    else:
        result['status'] = 'search_unavailable' if had_error else 'no_sources'
        result['note'] = 'Live research failed or found no usable sources. No company-specific requirements were invented.'
    return result
