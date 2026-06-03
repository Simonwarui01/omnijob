"""
AI Seed Crawler — uses GPT to generate company NAMES then finds their real URLs.
Tracks seen companies to avoid repeating. Gets more specific over time.
"""
import json
import logging
import hashlib
import httpx
import time
import random
from urllib.parse import unquote, urlparse
from django.core.cache import cache

logger = logging.getLogger(__name__)

NAME_PROMPTS = [
    "List 50 real companies that hire remote freelance transcriptionists worldwide. Focus on SMALL and UNKNOWN companies. Return only company names as JSON array of strings.",
    "List 50 real AI data annotation companies that hire remote freelancers worldwide. Include small startups nobody knows. Return only company names as JSON array.",
    "List 50 medical transcription companies that hire remote freelancers. Include small clinics and medical documentation services. Return only names as JSON array.",
    "List 50 legal transcription companies that hire remote freelancers worldwide. Include small law firm services. Return only names as JSON array.",
    "List 50 transcription companies in Europe (UK Germany France Netherlands Spain Italy Poland Sweden) that hire remote workers. Return only names as JSON array.",
    "List 50 transcription companies in Asia Pacific (Japan Korea Australia India Singapore) that hire remote workers. Return only names as JSON array.",
    "List 50 podcast video and media transcription companies that hire remote freelancers. Include small ones. Return only names as JSON array.",
    "List 50 AI training data companies in Europe that hire remote annotators. Include small startups. Return only names as JSON array.",
    "List 50 AI training data companies in Asia that hire remote annotators. Include small startups. Return only names as JSON array.",
    "List 50 computer vision image and video annotation companies that hire remote freelancers. Include small ones. Return only names as JSON array.",
    "List 50 NLP text and speech annotation companies that hire remote linguistic annotators. Include small ones. Return only names as JSON array.",
    "List 50 French-language transcription and annotation companies in France Canada Belgium Switzerland. Return only names as JSON array.",
    "List 50 Latin American transcription and annotation companies that hire remote workers for English or French content. Return only names as JSON array.",
    "List 50 African transcription and data annotation companies or companies hiring in Africa. Return only names as JSON array.",
    "List 50 crowdsourcing and microtask platforms that pay remote workers for transcription or annotation. Include obscure ones. Return only names as JSON array.",
]


def get_already_known_companies():
    """Get list of companies already in our DB."""
    from core.models import Company
    return list(Company.objects.values_list("name", flat=True)[:100])


def get_company_names_from_ai(prompt_index=0):
    """Ask GPT for company names — exclude ones we already know."""
    from core.crawlers.ai_client import client, DEPLOYMENT

    known = get_already_known_companies()
    known_str = ", ".join(known[:50]) if known else "none yet"

    base_prompt = NAME_PROMPTS[prompt_index % len(NAME_PROMPTS)]
    full_prompt = f"""{base_prompt}

IMPORTANT: We already know these companies, DO NOT include them: {known_str}

Return ONLY a JSON array of company name strings, no other text."""

    try:
        response = client.chat.completions.create(
            model=DEPLOYMENT,
            max_tokens=2000,
            messages=[{"role": "user", "content": full_prompt}]
        )
        text = response.choices[0].message.content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        names = json.loads(text)
        if isinstance(names, list):
            # Filter out already known companies
            known_lower = {k.lower() for k in known}
            names = [n.strip() for n in names
                     if isinstance(n, str) and len(n) > 2
                     and n.lower() not in known_lower]
            logger.info(f"AI returned {len(names)} NEW company names")
            return names
        return []
    except Exception as e:
        logger.error(f"AI name generation error: {e}")
        return []


def find_company_careers_url(company_name):
    """Find company careers URL via DuckDuckGo using same proxy as web_crawler."""
    from bs4 import BeautifulSoup
    from core.crawlers.web_crawler import get_proxy

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    cache_key = f"company_searched:{hashlib.md5(company_name.lower().encode()).hexdigest()}"
    if cache.get(cache_key):
        return None
    cache.set(cache_key, True, timeout=86400 * 7)

    query = company_name + " careers jobs freelance transcription annotation apply"

    try:
        proxy = get_proxy()
        r = httpx.get(
            f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}",
            headers=HEADERS,
            proxy=proxy.get('https://') if proxy else None,
            timeout=20,
            follow_redirects=True,
        )
        time.sleep(random.uniform(1, 2))

        if r.status_code not in [200, 202]:
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.find_all("a", class_="result__url")

        if not links:
            return None

        BAD = ["indeed", "glassdoor", "linkedin", "monster", "ziprecruiter",
               "flexjobs", "remotive", "remoteleaf", "earnbeyondborders",
               "nichepursuits", "theworkathomewoman", "reddit", "quora",
               "wikipedia", "youtube", "facebook", "twitter", "instagram",
               "upwork", "fiverr", "freelancer.com", "remote.co/blog",
               "workathomesmart", "thebalancemoney", "moneypantry"]

        from urllib.parse import unquote, urlparse
        for link in links[:5]:
            raw = link.get("href", "")
            if "uddg=" in raw:
                url = unquote(raw.split("uddg=")[1].split("&")[0])
            elif raw.startswith("http"):
                url = raw
            else:
                continue
            if not url.startswith("http"):
                continue
            domain = urlparse(url).netloc.lower()
            if any(b in domain for b in BAD):
                continue
            return url

    except Exception as e:
        logger.debug(f"Search error for {company_name}: {e}")

    return None


def run_ai_seed_discovery():
    """Main entry: get names from AI, find real URLs, crawl them."""
    from core.crawlers.web_crawler import crawl_website, is_valid_apply_url

    idx = cache.get("ai_seed_prompt_index", 0)
    next_idx = (idx + 1) % len(NAME_PROMPTS)
    cache.set("ai_seed_prompt_index", next_idx, timeout=86400 * 30)

    logger.info(f"AI seed discovery prompt {idx}/{len(NAME_PROMPTS)}")
    names = get_company_names_from_ai(idx)

    total_jobs = 0
    found_urls = 0

    for name in names:
        url = find_company_careers_url(name)
        if not url:
            continue

        found_urls += 1

        url_hash = hashlib.md5(url.encode()).hexdigest()
        if cache.get(f"crawled_url:{url_hash}"):
            continue

        if not is_valid_apply_url(url):
            continue

        logger.info(f"Crawling {name}: {url}")
        jobs = crawl_website(url, "en")
        total_jobs += jobs

        if jobs > 0:
            print(f"  {name}: {jobs} jobs")

    logger.info(f"AI seed: {len(names)} new names, {found_urls} URLs, {total_jobs} jobs")
    return total_jobs
