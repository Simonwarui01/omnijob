from django.core.management.base import BaseCommand
from core.crawlers.greenhouse import crawl_greenhouse_slug, run_full_discovery


GREENHOUSE_SLUGS = [
    'scaleai', 'snorkelai', 'labelbox', 'prolific', 'remotasks',
    'hive', 'anthropic', 'openai', 'cohere', 'adept', 'characterai',
    'runway', 'huggingface', 'mistral', 'perplexity', 'replicate',
    'roboflow', 'v7labs', 'superannotate', 'dataloop', 'encord',
    'imerit', 'sama', 'cloudfactory', 'cogito', 'defined',
    'surge', 'tasq', 'dataannotation', 'outlier',
    '3playmedia', 'verbit', 'otter', 'assemblyai', 'deepgram',
    'speechify', 'descript', 'trint', 'sonix', 'cielo24',
    'testlio', 'heygen', 'synthesia',
    'smartling', 'lokalise', 'crowdin', 'phrase', 'transifex',
    'welocalize', 'transperfect', 'lionbridge', 'languageline',
    'translated', 'unbabel', 'lilt', 'smartcat', 'rws',
    'straker', 'keywords', 'moravia', 'acolad',
    'taskus', 'concentrix', 'teleperformance', 'foundever',
    'alorica', 'teletech', 'conduent', 'accenture', 'webhelp',
    'transcom', 'sutherland', 'ibex', 'startek', 'capita',
    'elevenlabs', 'murf', 'resemble', 'adobe', 'nuance',
    'usertesting', 'userinterviews', 'respondent', 'dscout',
    'lookback', 'maze', 'hotjar', 'fullstory',
    'utest', 'applause', 'rainforest-qa',
    'invisible', 'stabilityai', 'togetherai', 'xai', 'duolingo',
    'deepmind', 'toloka',
]

LEVER_SLUGS = [
    'appen', 'hive', 'superannotate', 'defined-ai',
    'surge-hq', 'outlier-ai', 'telusinternational',
    'welocalize', 'unbabel', 'taskus', 'concentrix',
    'usertesting', 'respondent', 'deepgram', 'elevenlabs',
    'synthesia', 'heygen', 'descript', 'verbit', 'smartling',
    'lokalise', 'phrase', 'lilt', 'translated', 'testlio',
    'applause', 'anthropic', 'cohere', 'huggingface',
    'mistral', 'aleph-alpha', 'stability-ai', 'runway',
    'perplexity-ai', 'invisible', 'scale-ai',
]


class Command(BaseCommand):
    help = 'Run OmniJob full discovery engine'

    def add_arguments(self, parser):
        parser.add_argument('--greenhouse-only', action='store_true')
        parser.add_argument('--lever-only', action='store_true')
        parser.add_argument('--discover', action='store_true',
                            help='Test and crawl ALL slugs in database')
        parser.add_argument('--web-discovery', action='store_true',
                            help='Search web in 15+ languages for task-based English work')
        parser.add_argument('--social-only', action='store_true')
        parser.add_argument('--trust-only', action='store_true')
        parser.add_argument('--taxonomy-only', action='store_true')
        parser.add_argument('--ghost-only', action='store_true')
        parser.add_argument('--schedule-check', action='store_true')
        parser.add_argument('--report', action='store_true')

    def handle(self, *args, **kwargs):

        if kwargs.get('web_discovery'):
            self.stdout.write('🌐 Running web discovery in 15+ languages...\n')
            from core.crawlers.web_crawler import run_web_discovery
            total = run_web_discovery()
            self.stdout.write(f'\n✅ Done. {total} new jobs found.\n')

        elif kwargs.get('discover'):
            self.stdout.write(
                f'🔍 Testing {len(GREENHOUSE_SLUGS)} Greenhouse + '
                f'{len(LEVER_SLUGS)} Lever slugs...\n\n'
            )
            self._run_discover()

        elif kwargs.get('greenhouse_only'):
            self.stdout.write('🚀 Running Greenhouse crawl...\n')
            total = 0
            found = 0
            for slug in GREENHOUSE_SLUGS:
                self.stdout.write(f'  {slug}...\n')
                jobs = crawl_greenhouse_slug(slug)
                if jobs > 0:
                    total += jobs
                    found += 1
                    self.stdout.write(f'    💼 {jobs} jobs\n')
            self.stdout.write(f'\n✅ {total} jobs from {found} companies.\n')

        elif kwargs.get('lever_only'):
            self.stdout.write('🚀 Running Lever crawl...\n')
            from core.crawlers.lever import crawl_lever_slug
            total = 0
            found = 0
            for slug in LEVER_SLUGS:
                self.stdout.write(f'  {slug}...\n')
                jobs = crawl_lever_slug(slug)
                if jobs > 0:
                    total += jobs
                    found += 1
                    self.stdout.write(f'    💼 {jobs} jobs\n')
            self.stdout.write(f'\n✅ {total} jobs from {found} companies.\n')

        elif kwargs.get('social_only'):
            self.stdout.write('🚀 Running social discovery...\n')
            from core.crawlers.reddit import run_social_discovery
            total = run_social_discovery()
            self.stdout.write(f'\n✅ {total} new sources.\n')

        elif kwargs.get('trust_only'):
            self.stdout.write('🚀 Updating trust scores...\n')
            from core.crawlers.trust import update_company_trust_scores
            total = update_company_trust_scores()
            self.stdout.write(f'\n✅ {total} companies updated.\n')

        elif kwargs.get('taxonomy_only'):
            self.stdout.write('🚀 Updating taxonomy...\n')
            from core.crawlers.taxonomy import update_taxonomy
            total = update_taxonomy()
            self.stdout.write(f'\n✅ {total} categories updated.\n')

        elif kwargs.get('ghost_only'):
            self.stdout.write('🚀 Running ghost detection...\n')
            from core.crawlers.ghost_detector import run_ghost_detection
            ghosts = run_ghost_detection()
            self.stdout.write(f'\n✅ {ghosts} ghost pipelines detected.\n')

        elif kwargs.get('schedule_check'):
            self.stdout.write('🔄 Priority crawl...\n')
            self._run_priority_crawl()

        elif kwargs.get('report'):
            self.stdout.write('📊 Generating report...\n')
            from core.crawlers.report import generate_weekly_report
            generate_weekly_report()

        else:
            self.stdout.write('🚀 OmniJob full engine...\n')
            jobs = run_full_discovery()
            self.stdout.write(f'\n✅ {jobs} new jobs.\n')

    def _run_discover(self):
        import httpx
        import time

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        total_jobs = 0
        valid_count = 0

        self.stdout.write('📡 GREENHOUSE ATS\n')
        self.stdout.write('─' * 50 + '\n')

        for slug in GREENHOUSE_SLUGS:
            try:
                r = httpx.get(
                    f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs',
                    headers=headers, timeout=6
                )
                if r.status_code == 200:
                    all_jobs = r.json().get('jobs', [])
                    if all_jobs:
                        valid_count += 1
                        self.stdout.write(
                            f'  ✅ {slug}: {len(all_jobs)} total — crawling...\n'
                        )
                        new_jobs = crawl_greenhouse_slug(slug)
                        if new_jobs > 0:
                            total_jobs += new_jobs
                            self.stdout.write(f'    💼 {new_jobs} new jobs saved\n')
                time.sleep(0.4)
            except Exception:
                pass

        self.stdout.write(f'\n  Greenhouse: {valid_count} valid companies\n\n')

        self.stdout.write('📡 LEVER ATS\n')
        self.stdout.write('─' * 50 + '\n')

        lever_valid = 0
        for slug in LEVER_SLUGS:
            try:
                r = httpx.get(
                    f'https://api.lever.co/v0/postings/{slug}?mode=json',
                    headers=headers, timeout=6
                )
                if r.status_code == 200:
                    all_jobs = r.json()
                    if isinstance(all_jobs, list) and all_jobs:
                        lever_valid += 1
                        self.stdout.write(
                            f'  ✅ {slug}: {len(all_jobs)} total — crawling...\n'
                        )
                        from core.crawlers.lever import crawl_lever_slug
                        new_jobs = crawl_lever_slug(slug)
                        if new_jobs > 0:
                            total_jobs += new_jobs
                            self.stdout.write(f'    💼 {new_jobs} new jobs saved\n')
                time.sleep(0.4)
            except Exception:
                pass

        self.stdout.write(f'\n  Lever: {lever_valid} valid companies\n\n')
        self.stdout.write('=' * 50 + '\n')
        self.stdout.write(f'🎯 TOTAL NEW JOBS: {total_jobs}\n')

        from core.models import Job, Company
        self.stdout.write(
            f'   Database: {Job.objects.count()} jobs, '
            f'{Company.objects.count()} companies\n'
        )

    def _run_priority_crawl(self):
        from django.utils import timezone
        from datetime import timedelta
        from core.models import Company
        from core.crawlers.greenhouse import get_crawl_priority

        now = timezone.now()
        total_jobs = 0
        checked = 0
        companies = Company.objects.filter(status='active')

        for company in companies:
            priority_hours = get_crawl_priority(company)
            last = company.last_checked or company.first_seen
            due_time = last + timedelta(hours=priority_hours)

            if now >= due_time:
                self.stdout.write(f'  [{priority_hours}h] {company.name}...\n')
                careers_url = company.careers_url or ''
                if 'boards.greenhouse.io' in careers_url:
                    slug = careers_url.replace(
                        'https://boards.greenhouse.io/', ''
                    ).strip('/')
                    if slug:
                        jobs = crawl_greenhouse_slug(slug)
                        total_jobs += jobs
                        if jobs > 0:
                            self.stdout.write(f'    💼 {jobs} new jobs\n')
                checked += 1

        self.stdout.write(
            f'\n✅ {checked} companies checked, {total_jobs} new jobs.\n'
        )