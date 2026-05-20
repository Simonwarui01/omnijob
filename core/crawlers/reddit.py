import httpx
import hashlib
import logging
import time
import random
import re
from bs4 import BeautifulSoup
from django.utils import timezone
from core.models import CrawlLog, DiscoveredSource

logger = logging.getLogger(__name__)

SUBREDDITS = [
    'WorkOnline',
    'beermoney',
    'slavelabour',
    'HITsWorthTurkingFor',
    'remotework',
    'freelance',
    'mturk',
    'RateBeer',
]

OPPORTUNITY_KEYWORDS = [
    'transcription', 'transcribe', 'transcriptionist',
    'annotation', 'annotate', 'data labeling', 'data label',
    'ai training', 'ai trainer', 'rlhf', 'llm evaluation',
    'content moderation', 'content review',
    'voice recording', 'voice actor', 'voice over',
    'captioning', 'subtitling', 'subtitle',
    'quality rater', 'search evaluation', 'search rater',
    'data collection', 'data entry',
    'remotasks', 'appen', 'scale ai', 'prolific',
    'clickworker', 'microworkers', 'picoworkers',
    'new site', 'new platform', 'just found', 'anyone tried',
    'paying', 'getting paid', 'earn', 'make money online',
    'work from home', 'remote job', 'freelance work',
    'legit', 'legitimate', 'paying out',
]

SKIP_URLS = [
    'reddit.com', 'imgur.com', 'youtube.com', 'youtu.be',
    'twitter.com', 'facebook.com', 'google.com',
    'bit.ly', 'tinyurl.com', 't.co', 'ow.ly',
    'instagram.com', 'tiktok.com', 'discord.gg',
    '.pdf', '.jpg', '.png', '.gif', '.mp4',
    'amazon.com', 'ebay.com', 'etsy.com',
]

SKIP_JOB_TYPES = [
    'software engineer', 'developer', 'architect',
    'security engineer', 'devops', 'machine learning engineer',
    'data scientist', 'product manager', 'designer',
]


def is_relevant_post(title, text=''):
    content = (title + ' ' + text).lower()
    if any(kw in content for kw in ['scam', 'fake', 'fraud', 'crypto', 'bitcoin', 'nft', 'mlm']):
        return False
    return any(kw in content for kw in OPPORTUNITY_KEYWORDS)


def is_valid_job_url(url):
    url_lower = url.lower()
    if any(skip in url_lower for skip in SKIP_URLS):
        return False
    if not url.startswith('http'):
        return False
    if len(url) > 500:
        return False
    # Must look like a careers/jobs page or known platform
    career_signals = [
        'career', 'job', 'work', 'hire', 'hiring', 'apply',
        'greenhouse.io', 'lever.co', 'workable.com',
        'bamboohr', 'recruitee', 'breezy',
        'remotasks', 'appen', 'prolific', 'scale',
        'annotate', 'label', 'transcri',
    ]
    return any(sig in url_lower for sig in career_signals)


def crawl_subreddit(subreddit, limit=50):
    """
    Crawls Reddit subreddit new posts via public JSON API.
    No API key needed. Respects rate limits.
    """
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}&sort=new"
    headers = {
        'User-Agent': 'Mozilla/5.0 (research bot for job discovery)',
        'Accept': 'application/json',
    }

    new_sources = 0
    relevant_posts = 0

    try:
        response = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
        time.sleep(random.uniform(2, 4))

        if response.status_code == 429:
            print(f"    r/{subreddit}: rate limited — skipping")
            return 0, 0

        if response.status_code != 200:
            return 0, 0

        data = response.json()
        posts = data.get('data', {}).get('children', [])

        for post in posts:
            d = post.get('data', {})
            title = d.get('title', '')
            text = d.get('selftext', '')
            post_url = d.get('url', '')
            score = d.get('score', 0)

            if not is_relevant_post(title, text):
                continue

            relevant_posts += 1
            print(f"      📌 [{subreddit}] {title[:65]}")

            # Check if the post URL itself is a job/platform URL
            if post_url and is_valid_job_url(post_url):
                source, created = DiscoveredSource.objects.get_or_create(
                    url=post_url[:1000],
                    defaults={
                        'name': title[:255],
                        'source_type': 'unknown',
                        'posting_language': 'en',
                        'discovered_via': f'Reddit r/{subreddit}',
                        'discovered_query': title[:500],
                        'trust_score': min(40 + score, 75),
                    }
                )
                if created:
                    new_sources += 1
                    print(f"        🔗 Saved: {post_url[:60]}")

            # Extract URLs from post text
            urls_in_text = re.findall(r'https?://[^\s\)\]\"]+', text)
            for found_url in urls_in_text:
                found_url = found_url.strip('.,)')
                if is_valid_job_url(found_url):
                    source, created = DiscoveredSource.objects.get_or_create(
                        url=found_url[:1000],
                        defaults={
                            'name': found_url[:255],
                            'source_type': 'unknown',
                            'posting_language': 'en',
                            'discovered_via': f'Reddit r/{subreddit} — post text',
                            'discovered_query': title[:500],
                            'trust_score': 50,
                        }
                    )
                    if created:
                        new_sources += 1

        CrawlLog.objects.create(
            url=url,
            status='success',
            http_code=200,
            protection_level=2,
            jobs_found=new_sources,
        )

    except Exception as e:
        print(f"    r/{subreddit} error: {e}")

    return relevant_posts, new_sources


def crawl_hackernews_jobs():
    """
    Crawls current Hacker News 'Who is Hiring' thread.
    Gets the LATEST monthly thread, not old ones.
    Filters for task-based work only.
    """
    print("  📰 Scanning Hacker News 'Who is Hiring' (current month)...")
    new_sources = 0

    task_keywords = [
        'transcri', 'annot', 'label', 'moderat',
        'voice record', 'caption', 'subtitle',
        'quality rater', 'data collect',
        'content review', 'trust and safety',
        'freelance', 'contractor', 'part.time',
    ]

    skip_keywords = [
        'software engineer', 'developer', 'architect',
        'devops', 'security engineer', 'data scientist',
        'machine learning', 'product manager', 'designer',
        'full.time', 'full time employee', 'w2', 'salary',
    ]

    try:
        # Get ONLY the most recent "Who is Hiring" thread
        search_url = "https://hn.algolia.com/api/v1/search?query=Ask+HN+Who+is+Hiring&tags=story&hitsPerPage=1&restrictSearchableAttributes=title"
        response = httpx.get(search_url, timeout=15)
        time.sleep(1)

        if response.status_code != 200:
            return 0

        hits = response.json().get('hits', [])
        if not hits:
            return 0

        # Only use the single most recent thread
        story_id = hits[0].get('objectID')
        story_title = hits[0].get('title', '')
        print(f"    Using thread: {story_title}")

        # Get comments
        comments_url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&hitsPerPage=200"
        c_response = httpx.get(comments_url, timeout=15)
        time.sleep(1)

        if c_response.status_code != 200:
            return 0

        comments = c_response.json().get('hits', [])
        print(f"    Checking {len(comments)} comments...")

        for comment in comments:
            text = comment.get('comment_text', '')
            if not text:
                continue

            text_lower = text.lower()

            # Must have task-based keyword
            if not any(kw in text_lower for kw in task_keywords):
                continue

            # Skip professional roles
            if any(kw in text_lower for kw in skip_keywords):
                continue

            # Extract URLs
            soup = BeautifulSoup(text, 'html.parser')
            links = soup.find_all('a', href=True)

            for link in links:
                href = link['href']
                if not href.startswith('http'):
                    continue
                if any(skip in href.lower() for skip in [
                    'ycombinator', 'github.com', 'twitter.com',
                    'youtube.com', 'linkedin.com', 'bit.ly',
                    'tinyurl', '.pdf',
                ]):
                    continue

                source, created = DiscoveredSource.objects.get_or_create(
                    url=href[:1000],
                    defaults={
                        'name': href[:255],
                        'source_type': 'company_careers',
                        'posting_language': 'en',
                        'discovered_via': f'HN: {story_title[:100]}',
                        'trust_score': 65,
                    }
                )
                if created:
                    new_sources += 1
                    print(f"    ✅ HN source: {href[:70]}")

    except Exception as e:
        print(f"    HN error: {e}")

    print(f"    {new_sources} new relevant sources from HN")
    return new_sources


def run_social_discovery():
    """Main entry point."""
    print("\n📡 Social Signal Discovery\n")
    total_posts = 0
    total_sources = 0

    print("  Scanning Reddit...")
    for subreddit in SUBREDDITS:
        print(f"    r/{subreddit}...")
        posts, sources = crawl_subreddit(subreddit)
        total_posts += posts
        total_sources += sources
        time.sleep(random.uniform(1, 2))

    print()
    hn_sources = crawl_hackernews_jobs()
    total_sources += hn_sources

    print(f"\n  ✅ Social discovery complete")
    print(f"     Relevant posts: {total_posts}")
    print(f"     New sources: {total_sources}")

    return total_sources