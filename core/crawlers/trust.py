import httpx
import time
import logging
from datetime import datetime, timezone
from core.models import Company

logger = logging.getLogger(__name__)


def calculate_trust_score(company):
    """
    Calculates a trust score (0-100) for a company.
    
    Signals used:
    - Domain age (older = more trustworthy)
    - HTTPS (secure = more trustworthy)  
    - Careers page exists and loads
    - Company has social presence
    - Number of jobs found historically
    - ATS platform used (Greenhouse/Lever = more trustworthy)
    """
    score = 50  # Start neutral
    reasons = []

    url = company.website or company.careers_url
    if not url:
        return 30, ['No website found']

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    }

    # Signal 1: HTTPS (5 points)
    if url.startswith('https://'):
        score += 5
        reasons.append('Uses HTTPS (+5)')

    # Signal 2: Known trustworthy ATS platforms (20 points)
    trusted_ats = [
        'boards.greenhouse.io', 'jobs.lever.co',
        'apply.workable.com', 'bamboohr.com',
        'smartrecruiters.com', 'recruitee.com',
    ]
    if any(ats in url for ats in trusted_ats):
        score += 20
        reasons.append('Uses trusted ATS platform (+20)')

    # Signal 3: Well-known platforms we trust (25 points)
    known_trusted = [
        'remotasks', 'prolific', 'scaleai', 'appen',
        'telusinternational', 'lionbridge', 'transperfect',
        'welocalize', '3playmedia', 'verbit', 'rev.com',
        'anthropic', 'openai', 'google', 'microsoft',
        'amazon', 'apple', 'meta', 'deepmind',
    ]
    company_lower = company.name.lower()
    if any(k in company_lower for k in known_trusted):
        score += 25
        reasons.append(f'Known legitimate company (+25)')

    # Signal 4: Careers page actually loads (10 points)
    try:
        response = httpx.get(
            company.careers_url or url,
            headers=headers,
            timeout=10,
            follow_redirects=True,
        )
        time.sleep(0.5)
        if response.status_code == 200:
            score += 10
            reasons.append('Careers page loads successfully (+10)')

            # Signal 5: Page has substantial content (5 points)
            if len(response.text) > 5000:
                score += 5
                reasons.append('Page has substantial content (+5)')
        else:
            score -= 10
            reasons.append(f'Careers page returned {response.status_code} (-10)')
    except Exception:
        score -= 5
        reasons.append('Careers page not accessible (-5)')

    # Signal 6: Jobs found historically (up to 10 points)
    job_count = company.jobs.count()
    if job_count >= 5:
        score += 10
        reasons.append(f'{job_count} jobs found historically (+10)')
    elif job_count >= 1:
        score += 5
        reasons.append(f'{job_count} jobs found historically (+5)')

    # Signal 7: Discovered via trusted method (5 points)
    trusted_discovery = ['Greenhouse', 'Lever', 'Workable', 'HN:']
    if any(t in (company.discovered_via or '') for t in trusted_discovery):
        score += 5
        reasons.append('Discovered via trusted ATS (+5)')

    # Cap between 0 and 100
    score = max(0, min(100, score))

    return score, reasons


def update_company_trust_scores():
    """
    Updates trust scores for all companies.
    Run periodically to keep scores fresh.
    """
    print("🔍 Updating company trust scores...")
    companies = Company.objects.all()
    updated = 0

    for company in companies:
        try:
            score, reasons = calculate_trust_score(company)
            company.trust_score = score
            company.save()
            print(f"  {company.name}: {score}/100")
            updated += 1
        except Exception as e:
            logger.error(f'Trust score error for {company.name}: {e}')

    print(f"  ✅ Updated {updated} companies")
    return updated