import httpx
import logging
import time
import random
from bs4 import BeautifulSoup
from django.utils import timezone
from core.models import Company, Job, JobStateHistory

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Signals on the RESULT page after clicking apply
# that indicate this is a ghost pipeline
GHOST_RESULT_SIGNALS = [
    # English
    'no positions available',
    'currently fully staffed',
    'no openings at this time',
    'no current openings',
    'not currently hiring',
    'we will keep your cv on file',
    'we will keep your resume on file',
    'we\'ll be in touch when',
    'notify you when a position',
    'notify you when something opens',
    'no vacancies at this time',
    'no job openings',
    'check back later',
    'future opportunities',
    'talent pool',
    'talent community',
    'expression of interest',
    'register your interest',
    'stay in touch',
    # German
    'keine stellen verfügbar',
    'keine offenen stellen',
    'derzeit keine stellen',
    'wir melden uns',
    'talentpool',
    # French
    'pas de postes disponibles',
    'aucun poste disponible',
    'nous vous contacterons',
    'vivier de talents',
    # Dutch
    'geen vacatures',
    'momenteel geen vacatures',
    'we houden je op de hoogte',
    # Swedish
    'inga lediga tjänster',
    'vi återkommer',
    # Norwegian
    'ingen ledige stillinger',
    'vi tar kontakt',
]

# Signals that confirm a REAL vacancy after clicking apply
REAL_VACANCY_SIGNALS = [
    'apply now', 'submit application', 'submit your application',
    'apply for this position', 'apply for this job',
    'upload your cv', 'upload your resume',
    'attach your cv', 'attach your resume',
    'your name', 'your email', 'first name', 'last name',
    'cover letter', 'application form',
    'jetzt bewerben', 'bewerbung einreichen',
    'postuler maintenant', 'envoyer ma candidature',
    'solliciteer nu', 'stuur je sollicitatie',
]


def check_application_result(apply_url):
    """
    Visits the apply URL and reads what happens.
    This is the key insight — check the RESULT page, not just the button.
    A ghost pipeline reveals itself on the result page.
    
    Returns: 'active', 'ghost', 'unknown'
    """
    if not apply_url:
        return 'unknown'

    try:
        response = httpx.get(
            apply_url,
            headers=HEADERS,
            timeout=20,
            follow_redirects=True,
        )
        time.sleep(random.uniform(1, 2))

        if response.status_code != 200:
            return 'unknown'

        text = response.text.lower()

        # Check for ghost signals first
        if any(sig in text for sig in GHOST_RESULT_SIGNALS):
            return 'ghost'

        # Check for real vacancy signals
        if any(sig in text for sig in REAL_VACANCY_SIGNALS):
            return 'active'

        return 'unknown'

    except Exception as e:
        logger.error(f'Ghost detection error for {apply_url}: {e}')
        return 'unknown'


def run_ghost_detection():
    """
    Checks all jobs marked as 'active' to verify they are genuine.
    Detects ghost pipelines by reading the application result page.
    Records state transitions when status changes.
    """
    print("\n👻 Ghost Pipeline Detection starting...")
    checked = 0
    ghosts_found = 0
    confirmed_active = 0

    # Check jobs marked active that have an apply URL
    active_jobs = Job.objects.filter(
        vacancy_state='active'
    ).exclude(apply_url='').select_related('company')[:50]

    print(f"  Checking {active_jobs.count()} active jobs...")

    for job in active_jobs:
        print(f"  Checking: {job.title[:50]} ({job.company.name})")

        result = check_application_result(job.apply_url)
        checked += 1

        if result == 'ghost' and job.vacancy_state != 'ghost_pipeline':
            # State transition: active → ghost_pipeline
            old_state = job.vacancy_state
            job.vacancy_state = 'ghost_pipeline'
            job.save()

            JobStateHistory.objects.create(
                company=job.company,
                previous_state=old_state,
                new_state='ghost_pipeline',
                notes=f'Ghost pipeline detected by deep application check: {job.title}',
            )
            ghosts_found += 1
            print(f"    👻 GHOST PIPELINE: {job.title[:50]}")

        elif result == 'active':
            confirmed_active += 1
            print(f"    ✅ Confirmed active: {job.title[:50]}")

        time.sleep(random.uniform(1, 3))

    print(f"\n  ✅ Ghost detection complete")
    print(f"     Jobs checked:      {checked}")
    print(f"     Ghosts found:      {ghosts_found}")
    print(f"     Confirmed active:  {confirmed_active}")

    return ghosts_found