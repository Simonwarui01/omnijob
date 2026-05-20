import httpx
import logging
import time
import random
from django.utils import timezone
from datetime import timedelta
from bs4 import BeautifulSoup
from core.models import Company, Job, Notification

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def recheck_company(company):
    """
    Re-visits a known company's careers page.
    Looks for new job openings using Claude.
    Creates notifications for new findings.
    """
    if not company.careers_url:
        return 0

    jobs_found = 0
    try:
        r = httpx.get(
            company.careers_url,
            headers=HEADERS,
            timeout=20,
            follow_redirects=True,
        )
        time.sleep(random.uniform(1, 2))

        if r.status_code != 200:
            return 0

        soup = BeautifulSoup(r.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer']):
            tag.decompose()
        page_text = soup.get_text(separator=' ', strip=True)

        if len(page_text) < 200:
            return 0

        # Use Claude to extract jobs
        from core.crawlers.web_crawler import extract_jobs_with_claude
        import hashlib
        from urllib.parse import urlparse

        jobs = extract_jobs_with_claude(company.careers_url, page_text)

        domain = urlparse(company.careers_url).netloc

        for job_data in jobs:
            if not job_data.get('is_relevant', False):
                continue
            work_lang = job_data.get('work_language', 'en')
            if work_lang not in ['en', 'unknown', '']:
                continue

            title = job_data.get('title', '')
            if not title or len(title) < 3:
                continue

            job_type = job_data.get('job_type', 'other')
            fingerprint = hashlib.sha256(
                f"web:{domain}:{job_type}".lower().encode()
            ).hexdigest()

            if Job.objects.filter(fingerprint=fingerprint).exists():
                continue

            # New job found at known company
            job = Job.objects.create(
                company=company,
                title=title,
                description=job_data.get('description', '')[:500],
                apply_url=job_data.get('apply_url', company.careers_url),
                posting_language=job_data.get('posting_language', 'en'),
                work_language='en',
                job_type=job_type,
                vacancy_state='active',
                geo_tier=job_data.get('geo_tier', 0),
                onboarding_level=2,
                citizenship_flag=False,
                citizenship_note='',
                physical_required=False,
                fingerprint=fingerprint,
                is_new=True,
                last_confirmed=timezone.now(),
            )
            jobs_found += 1

            # Create notification
            Notification.objects.create(
                notification_type='new_job',
                title=f'New opening at {company.name}',
                message=f'{title} — {company.name} is now hiring. Apply: {job_data.get("apply_url", company.careers_url)}',
                company=company,
                job=job,
            )
            print(f'    🔔 New job at {company.name}: {title}')

        company.last_checked = timezone.now()
        company.save()

    except Exception as e:
        logger.error(f'Company recheck error for {company.name}: {e}')

    return jobs_found


def recheck_all_companies():
    """
    Re-checks all known companies for new openings.
    Prioritizes companies not checked recently.
    Runs every 6 hours via Celery.
    """
    print('\n🔄 Re-checking known companies for new openings...')

    # Check companies not visited in last 24 hours
    cutoff = timezone.now() - timedelta(hours=24)
    companies = Company.objects.filter(
        careers_url__isnull=False,
    ).exclude(
        careers_url=''
    ).filter(
        last_checked__lt=cutoff
    ).order_by('last_checked')[:50]

    print(f'  Companies to check: {companies.count()}')
    total_jobs = 0

    for company in companies:
        print(f'  Checking {company.name}...')
        jobs = recheck_company(company)
        if jobs > 0:
            total_jobs += jobs
            print(f'    💼 {jobs} new jobs found!')
        time.sleep(random.uniform(2, 4))

    print(f'\n✅ Company recheck complete. {total_jobs} new jobs found.')
    return total_jobs