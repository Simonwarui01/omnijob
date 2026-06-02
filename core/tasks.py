from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def run_greenhouse_crawl():
    """
    Runs every 6 hours.
    Uses DuckDuckGo to dynamically discover NEW companies
    then crawls them. No hardcoded lists.
    """
    logger.info('Starting dynamic Greenhouse discovery...')
    try:
        from core.crawlers.greenhouse import run_full_discovery
        total = run_full_discovery()
        logger.info(f'Dynamic discovery complete. {total} new jobs.')
        return total
    except Exception as e:
        logger.error(f'Dynamic discovery failed: {e}')
        return 0


@shared_task
def run_full_discovery_task():
    """
    Runs every 24 hours.
    Full discovery — search engines, ATS, domain scan.
    """
    logger.info('Starting full discovery task...')
    try:
        from core.crawlers.greenhouse import run_full_discovery
        total = run_full_discovery()
        logger.info(f'Full discovery complete. {total} new jobs found.')
        return total
    except Exception as e:
        logger.error(f'Full discovery task failed: {e}')
        return 0


@shared_task
def run_state_transitions():
    """
    Runs every 3 hours.
    Checks all known companies for vacancy state changes.
    Ghost→Active triggers urgent alert.
    """
    logger.info('Starting state transition check...')
    try:
        from core.crawlers.greenhouse import check_state_transitions
        transitions = check_state_transitions()
        logger.info(f'State transition check complete. {transitions} transitions found.')
        return transitions
    except Exception as e:
        logger.error(f'State transition task failed: {e}')
        return 0


@shared_task
def run_lever_crawl():
    """
    Runs every 12 hours.
    Crawls all verified Lever ATS company slugs.
    """
    logger.info('Starting Lever crawl task...')
    try:
        from core.crawlers.lever import run_lever_crawl
        total = run_lever_crawl()
        logger.info(f'Lever crawl complete. {total} new jobs found.')
        return total
    except Exception as e:
        logger.error(f'Lever crawl task failed: {e}')
        return 0

@shared_task
def run_social_discovery():
    """
    Runs every 12 hours.
    Scans Reddit and Hacker News for new platforms and opportunities.
    """
    logger.info('Starting social discovery task...')
    try:
        from core.crawlers.reddit import run_social_discovery
        sources = run_social_discovery()
        logger.info(f'Social discovery complete. {sources} new sources found.')
        return sources
    except Exception as e:
        logger.error(f'Social discovery task failed: {e}')
        return 0

@shared_task
def run_trust_scoring():
    """
    Runs every 24 hours.
    Updates trust scores for all companies.
    """
    logger.info('Starting trust score update...')
    try:
        from core.crawlers.trust import update_company_trust_scores
        updated = update_company_trust_scores()
        logger.info(f'Trust scoring complete. {updated} companies updated.')
        return updated
    except Exception as e:
        logger.error(f'Trust scoring task failed: {e}')
        return 0


@shared_task
def run_taxonomy_update():
    """
    Runs every 12 hours.
    Updates the living taxonomy based on discovered jobs.
    """
    logger.info('Starting taxonomy update...')
    try:
        from core.crawlers.taxonomy import update_taxonomy
        updated = update_taxonomy()
        logger.info(f'Taxonomy update complete. {updated} categories updated.')
        return updated
    except Exception as e:
        logger.error(f'Taxonomy update failed: {e}')
        return 0

@shared_task
def run_ghost_detection():
    """
    Runs every 12 hours.
    Deep-checks active jobs for ghost pipeline detection.
    """
    logger.info('Starting ghost detection task...')
    try:
        from core.crawlers.ghost_detector import run_ghost_detection
        ghosts = run_ghost_detection()
        logger.info(f'Ghost detection complete. {ghosts} ghosts found.')
        return ghosts
    except Exception as e:
        logger.error(f'Ghost detection task failed: {e}')
        return 0

@shared_task
def run_weekly_report():
    """
    Runs every Monday at 8am Nairobi time.
    Generates weekly intelligence report.
    """
    logger.info('Generating weekly intelligence report...')
    try:
        from core.crawlers.report import generate_weekly_report
        report = generate_weekly_report()
        logger.info('Weekly report generated.')
        return report
    except Exception as e:
        logger.error(f'Weekly report failed: {e}')
        return ''

@shared_task
def run_web_discovery():
    """
    Runs every 6 hours.
    Searches the web in 15+ languages for task-based English work.
    Uses Claude to read any webpage in any language.
    """
    logger.info('Starting web discovery...')
    try:
        from core.crawlers.web_crawler import run_web_discovery
        total = run_web_discovery()
        logger.info(f'Web discovery complete. {total} new jobs.')
        return total
    except Exception as e:
        logger.error(f'Web discovery failed: {e}')
        return 0

@shared_task
def run_single_search_query():
    """
    Runs ONE search query from our list.
    Called every 15 minutes by Celery beat.
    Rotates through all queries — never triggers rate limiting.
    96 queries per day across 15 languages.
    """
    import json
    from django.core.cache import cache
    from core.crawlers.web_crawler import SEARCH_QUERIES, search_duckduckgo
    from core.crawlers.greenhouse import crawl_greenhouse_slug
    from core.crawlers.lever import crawl_lever_slug
    from urllib.parse import urlparse, unquote

    # Track which query to run next using cache
    from core.crawlers.web_crawler import SEARCH_QUERIES as STATIC_QUERIES
    from core.models import DynamicQuery

    # Combine static + dynamic queries
    dynamic = list(DynamicQuery.objects.filter(is_active=True).values_list('lang', 'query'))
    ALL_QUERIES = STATIC_QUERIES + dynamic

    query_index = cache.get('search_query_index', 0)

    if query_index >= len(ALL_QUERIES):
        query_index = 0

    lang, query = ALL_QUERIES[query_index]

    # Country rotation — same query searched from different countries
    REGIONS = [
        'wt-wt',  # Worldwide (default)
        'de-de',  # Germany
        'fr-fr',  # France
        'nl-nl',  # Netherlands
        'jp-jp',  # Japan
        'ko-kr',  # Korea
        'sv-se',  # Sweden
        'no-no',  # Norway
        'fi-fi',  # Finland
        'da-dk',  # Denmark
        'pl-pl',  # Poland
        'it-it',  # Italy
        'es-es',  # Spain
        'pt-pt',  # Portugal
        'pt-br',  # Brazil
        'zh-cn',  # China
        'ar-xa',  # Arabic
        'en-gb',  # UK
        'en-au',  # Australia
        'en-in',  # India
        'en-us',  # USA
        'fr-be',  # Belgium
        'de-ch',  # Switzerland
        'de-at',  # Austria
    ]

    # Get current region index for this query
    region_key = f'region_index_{query_index}'
    region_index = cache.get(region_key, 0)
    if region_index >= len(REGIONS):
        region_index = 0
        # All regions exhausted for this query — move to next query
        cache.set('search_query_index', query_index + 1, timeout=86400 * 7)
    else:
        cache.set(region_key, region_index + 1, timeout=86400 * 30)

    region = REGIONS[region_index]
    logger.info(f'Query {query_index+1}/{len(ALL_QUERIES)} region {region_index+1}/{len(REGIONS)}: [{lang}] {query[:40]} [{region}]')

    # Check if this query+region combination already searched
    import hashlib
    combo_key = f'searched:{hashlib.md5(f"{query}:{region}".encode()).hexdigest()}'
    if cache.get(combo_key):
        logger.info(f'Already searched this combination — skipping')
        return 0
    cache.set(combo_key, True, timeout=86400 * 7)

    # Run the search with region — process 3 URLs concurrently
    urls = search_duckduckgo(query, lang, max_results=10, region=region)
    
    # Also run next 2 queries in same task execution to go faster
    next_queries = []
    for i in range(1, 3):
        next_idx = (query_index + i) % len(ALL_QUERIES)
        next_lang, next_query = ALL_QUERIES[next_idx]
        next_combo_key = f'searched:{hashlib.md5(f"{next_query}:{region}".encode()).hexdigest()}'
        if not cache.get(next_combo_key):
            cache.set(next_combo_key, True, timeout=86400 * 7)
            extra_urls = search_duckduckgo(next_query, next_lang, max_results=10, region=region)
            urls.extend(extra_urls)
            logger.info(f'Also running: [{next_lang}] {next_query[:40]}')

    # Deduplicate URLs
    urls = list(dict.fromkeys(urls))

    total_jobs = 0
    for url in urls:
        # Greenhouse slug
        if 'boards.greenhouse.io' in url:
            parts = url.replace('https://boards.greenhouse.io/', '').replace('https://www.boards.greenhouse.io/', '').split('/')
            if parts and parts[0] and len(parts[0]) > 1:
                jobs = crawl_greenhouse_slug(parts[0])
                total_jobs += jobs
            continue
        
        # Lever slug
        if 'jobs.lever.co' in url:
            parts = url.replace('https://jobs.lever.co/', '').split('/')
            if parts and parts[0] and len(parts[0]) > 1:
                jobs = crawl_lever_slug(parts[0])
                total_jobs += jobs
            continue
        
        # Any other website — use Claude web crawler
        from core.crawlers.web_crawler import crawl_website
        jobs = crawl_website(url, lang)
        total_jobs += jobs
    
    logger.info(f'Query complete. {len(urls)} URLs found, {total_jobs} new jobs.')
    return total_jobs

@shared_task
def run_company_recheck():
    """Re-checks all known companies for new openings every 6 hours."""
    logger.info('Starting company recheck...')
    try:
        from core.crawlers.company_monitor import recheck_all_companies
        total = recheck_all_companies()
        logger.info(f'Company recheck complete. {total} new jobs.')
        return total
    except Exception as e:
        logger.error(f'Company recheck failed: {e}')
        return 0


@shared_task
def run_query_expansion():
    """Expands search queries based on recent discoveries every 24 hours."""
    logger.info('Starting query expansion...')
    try:
        from core.crawlers.query_expander import expand_queries_from_new_jobs
        total = expand_queries_from_new_jobs()
        logger.info(f'Query expansion complete. {total} new queries added.')
        return total
    except Exception as e:
        logger.error(f'Query expansion failed: {e}')
        return 0