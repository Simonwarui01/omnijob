from core.crawlers.ai_client import client, DEPLOYMENT
import httpx
import hashlib
import logging
import time
import random
from django.utils import timezone
from core.models import Company, Job, CrawlLog

logger = logging.getLogger(__name__)

# Verified working Lever slugs
# Add more as discovered via testing
LEVER_SLUGS = [
    'appen',  # 40 jobs — translation evaluation, speech annotation
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}


def make_fingerprint(company_name, job_title):
    title_lower = job_title.lower()
    if any(w in title_lower for w in ['transcri', 'caption', 'subtitl']):
        job_category = 'transcription'
    elif any(w in title_lower for w in ['annot', 'label', 'tag']):
        job_category = 'annotation'
    elif any(w in title_lower for w in ['translat', 'localiz']):
        job_category = 'translation'
    elif any(w in title_lower for w in ['voice', 'audio', 'speech', 'record']):
        job_category = 'voice'
    elif any(w in title_lower for w in ['moderat', 'trust', 'safety']):
        job_category = 'moderation'
    elif any(w in title_lower for w in ['rater', 'evaluat', 'assessor', 'analyst']):
        job_category = 'rating'
    elif any(w in title_lower for w in ['ai train', 'rlhf', 'prompt']):
        job_category = 'ai_training'
    else:
        job_category = job_title[:30].lower().strip()
    raw = f"lever:{company_name}:{job_category}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()


def crawl_lever_slug(slug):
    """
    Crawls a specific company on Lever ATS by slug.
    Uses Claude API batch classifier for intelligent filtering.
    Only keeps jobs where the work requires English speakers.
    """
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    jobs_created = 0

    try:
        response = httpx.get(url, headers=HEADERS, timeout=15)
        time.sleep(random.uniform(1, 2))

        if response.status_code != 200:
            return 0

        jobs_list = response.json()
        if not isinstance(jobs_list, list) or not jobs_list:
            return 0

        company_name = slug.replace('-', ' ').title()
        careers_url = f"https://jobs.lever.co/{slug}"

        # Pre-filter — hard reject obvious non-task roles only
        # Keep filter LOOSE — Claude does the real filtering
        potentially_relevant = []
        for job_data in jobs_list:
            title = job_data.get('text', '')
            full_text = f"{title} {job_data.get('categories', {}).get('location', '')}".lower()
            obvious_rejects = [
                'account executive', 'account manager',
                'software engineer', 'backend', 'frontend',
                'devops', 'infrastructure', 'security engineer',
                'ceo', 'cto', 'cfo', 'chief ', 'vice president',
                'director of', 'head of engineering',
                'accounting manager', 'accounting clerk',
                'community manager', 'growth marketing',
                'forward deployed', 'sales ', 'business development',
            ]
            if any(r in full_text for r in obvious_rejects):
                continue
            potentially_relevant.append(job_data)

        if not potentially_relevant:
            return 0

        # Create company record
        company, created = Company.objects.get_or_create(
            website=careers_url,
            defaults={
                'name': company_name,
                'careers_url': careers_url,
                'discovered_via': 'Lever ATS seed list',
                'trust_score': 70,
                'last_checked': timezone.now(),
                'last_active': timezone.now(),
            }
        )

        if created:
            print(f"    ✅ New Lever company: {company_name}")

        # Batch classify ALL jobs in ONE Claude API call — fast and cheap
        try:
            from core.crawlers.classifier import client
            import json

            titles_list = [
                f"{i+1}. {j.get('text', '')} | {j.get('categories', {}).get('location', '')}"
                for i, j in enumerate(potentially_relevant)
            ]

            prompt = f"""Classify these job postings. We ONLY want jobs where the work itself requires ENGLISH speakers.

Company: {company_name}

Jobs (number | title | location):
{chr(10).join(titles_list)}

STRICT RULES:
1. relevant=true ONLY if the work requires English language ability
2. relevant=false if the job requires ANY non-English language
   (Arabic, French, German, Japanese, Korean, Chinese, Russian,
   Armenian, Greek, Hebrew, Tamil, Welsh, Lingala, Lao, Bulgarian,
   Bosnian, Catalan, Estonian, Icelandic, Irish, Kazakh, Khmer,
   Latvian, Lithuanian, Malay, Maltese, Persian, Slovak, Slovenian,
   Azerbaijani, Burmese, or any other non-English language)
3. relevant=false for professional career roles
4. Task-based work we want: transcription OF English audio,
   English text annotation, English content moderation,
   English voice recording, English search evaluation,
   English quality rating, general AI training with no specific language

Examples:
- "Transcription Specialist [Armenian]" → relevant=false (needs Armenian)
- "Machine Translation Korean to English" → relevant=false (needs Korean)
- "Lingala Speakers AI Translation" → relevant=false (needs Lingala)
- "Social Media Evaluator Russian-Poland" → relevant=false (needs Russian)
- "Voice Recording Project Simple English Sentences" → relevant=true
- "Social Media Video Evaluator United States" → relevant=true
- "AI Training Specialist" → relevant=true (no specific language)
- "Search Ads Evaluator" → relevant=true if English implied

Return ONLY a JSON array:
[
  {{"num": 1, "relevant": true, "job_type": "transcription|annotation|ai_training|translation|voice|content_moderation|qa|other", "geo_tier": 0-5, "work_language": "en", "posting_language": "en"}}
]"""

            message = client.chat.completions.create(
                model=DEPLOYMENT,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.choices[0].message.content.strip()
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()

            classifications = json.loads(response_text)

        except Exception as e:
            print(f"    Batch classify error: {e}")
            return 0

        # Save only relevant English-work jobs
        for item in classifications:
            if not item.get('relevant', False):
                continue

            idx = item.get('num', 1) - 1
            if idx < 0 or idx >= len(potentially_relevant):
                continue

            job_data = potentially_relevant[idx]
            title = job_data.get('text', '')
            categories = job_data.get('categories', {})
            location = categories.get('location', '')
            job_url = job_data.get('hostedUrl', '')

            geo_tier = item.get('geo_tier', 0)
            if geo_tier == 5:
                continue

            fingerprint = make_fingerprint(company_name, title)
            if Job.objects.filter(fingerprint=fingerprint).exists():
                continue

            Job.objects.create(
                company=company,
                title=title,
                description=f"{title} {location}"[:500],
                apply_url=job_url,
                posting_language=item.get('posting_language', 'en'),
                work_language=item.get('work_language', 'en'),
                job_type=item.get('job_type', 'other'),
                vacancy_state='active',
                geo_tier=geo_tier,
                onboarding_level=2,
                citizenship_flag=False,
                citizenship_note='',
                physical_required=False,
                fingerprint=fingerprint,
                is_new=True,
                last_confirmed=timezone.now(),
            )
            jobs_created += 1
            print(f"      💼 {title[:65]}")

        CrawlLog.objects.create(
            url=url,
            company=company,
            status='success',
            http_code=200,
            protection_level=1,
            jobs_found=jobs_created,
        )

    except Exception as e:
        print(f"    Lever error for {slug}: {e}")
        CrawlLog.objects.create(
            url=f"https://api.lever.co/v0/postings/{slug}?mode=json",
            status='error',
            jobs_found=0,
            error_message=str(e)[:500],
        )

    return jobs_created


def run_lever_crawl():
    """
    Crawls all verified Lever company slugs.
    """
    print("\n🔗 Lever ATS Crawler starting...")
    total = 0
    companies = 0

    for slug in LEVER_SLUGS:
        print(f"  Checking {slug}...")
        jobs = crawl_lever_slug(slug)
        if jobs > 0:
            total += jobs
            companies += 1
        time.sleep(random.uniform(1.5, 3))

    print(f"\n✅ Lever crawl complete. {total} jobs from {companies} companies.")
    return total


def discover_lever_slugs(test_slugs):
    """
    Tests a list of potential Lever slugs and returns valid ones.
    Use this to expand the LEVER_SLUGS list.
    """
    valid = []
    for slug in test_slugs:
        try:
            r = httpx.get(
                f'https://api.lever.co/v0/postings/{slug}?mode=json',
                headers=HEADERS, timeout=6
            )
            if r.status_code == 200:
                jobs = r.json()
                if isinstance(jobs, list) and len(jobs) > 0:
                    valid.append(slug)
                    print(f'✅ {slug}: {len(jobs)} jobs')
            time.sleep(0.3)
        except Exception:
            pass
    return valid