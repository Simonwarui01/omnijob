from django.utils import timezone
from datetime import timedelta
from core.models import Job, Company, JobStateHistory, Taxonomy, CrawlLog


def generate_weekly_report():
    """
    Generates a weekly intelligence report summarizing:
    - New companies discovered
    - New jobs found
    - State transitions (ghost→active are most important)
    - Top job categories
    - Crawler health
    - Recommendations
    """
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    print("\n📊 Generating Weekly Intelligence Report...\n")

    # ── New companies this week ──
    new_companies = Company.objects.filter(first_seen__gte=week_ago)
    
    # ── New jobs this week ──
    new_jobs = Job.objects.filter(first_seen__gte=week_ago).select_related('company')
    
    # ── Active jobs (real vacancies) ──
    active_jobs = Job.objects.filter(
        vacancy_state='active',
        first_seen__gte=week_ago
    ).select_related('company')
    
    # ── Worldwide jobs (best for Kenya) ──
    worldwide_jobs = Job.objects.filter(
        vacancy_state='active',
        geo_tier=1,
    ).select_related('company')

    # ── State transitions this week ──
    transitions = JobStateHistory.objects.filter(
        changed_at__gte=week_ago
    ).select_related('company').order_by('-changed_at')

    urgent_transitions = transitions.filter(
        new_state='active',
        previous_state='ghost_pipeline'
    )

    # ── Ghost→Active transitions (most valuable) ──
    # ── Job type breakdown ──
    from django.db.models import Count
    job_types = Job.objects.filter(
        first_seen__gte=week_ago
    ).values('job_type').annotate(count=Count('id')).order_by('-count')

    # ── Crawler health ──
    total_crawls = CrawlLog.objects.filter(crawled_at__gte=week_ago).count()
    successful_crawls = CrawlLog.objects.filter(
        crawled_at__gte=week_ago, status='success'
    ).count()
    blocked_crawls = CrawlLog.objects.filter(
        crawled_at__gte=week_ago, status='blocked'
    ).count()

    success_rate = round(
        (successful_crawls / total_crawls * 100) if total_crawls > 0 else 0
    )

    # ── Non-English posting language breakdown ──
    non_english = Job.objects.filter(
        first_seen__gte=week_ago
    ).exclude(posting_language='en').values(
        'posting_language'
    ).annotate(count=Count('id')).order_by('-count')

    # ── Build report ──
    report = []
    report.append("=" * 60)
    report.append("OMNIJOB WEEKLY INTELLIGENCE REPORT")
    report.append(f"Week of {week_ago.strftime('%B %d')} — {now.strftime('%B %d, %Y')}")
    report.append("=" * 60)

    report.append(f"\n📊 SUMMARY")
    report.append(f"  New companies discovered: {new_companies.count()}")
    report.append(f"  New jobs found:           {new_jobs.count()}")
    report.append(f"  Active vacancies:         {active_jobs.count()}")
    report.append(f"  Worldwide (no restriction): {worldwide_jobs.count()}")

    if urgent_transitions.exists():
        report.append(f"\n🔥 URGENT — GHOST→ACTIVE TRANSITIONS")
        report.append(f"  These companies were ghost pipelines and just opened real positions:")
        for t in urgent_transitions:
            report.append(f"  → {t.company.name} ({t.changed_at.strftime('%b %d %H:%M')})")
            jobs = Job.objects.filter(
                company=t.company,
                vacancy_state='active'
            )
            for j in jobs[:3]:
                report.append(f"    💼 {j.title}")
                if j.apply_url:
                    report.append(f"       Apply: {j.apply_url}")

    if new_companies.exists():
        report.append(f"\n🏢 NEW COMPANIES DISCOVERED ({new_companies.count()})")
        for company in new_companies[:10]:
            active = company.jobs.filter(vacancy_state='active').count()
            report.append(
                f"  {company.name} [{company.country_name or 'Unknown'}] "
                f"— {active} active jobs"
            )
            report.append(f"    {company.careers_url or company.website}")

    if active_jobs.exists():
        report.append(f"\n💼 TOP ACTIVE JOBS THIS WEEK")
        # Prioritize worldwide jobs first
        priority_jobs = active_jobs.order_by('geo_tier', '-first_seen')[:15]
        for job in priority_jobs:
            geo_label = {
                0: '❓ Unknown',
                1: '🌍 Worldwide',
                2: '🌍 Africa OK',
                3: '⚠️ Legal flag',
                4: '🔍 Investigate',
            }.get(job.geo_tier, '❓')

            onboard_label = {
                1: '⚡ Test only',
                2: '📝 Async',
                3: '📹 Video',
                4: '📄 Docs',
            }.get(job.onboarding_level, '—')

            report.append(
                f"  [{geo_label}] [{onboard_label}] "
                f"{job.title[:50]} — {job.company.name}"
            )
            if job.apply_url:
                report.append(f"    {job.apply_url}")

    if job_types:
        report.append(f"\n📈 JOB TYPE BREAKDOWN")
        for jt in job_types:
            report.append(f"  {jt['job_type']:20} {jt['count']} jobs")

    if non_english:
        report.append(f"\n🌍 NON-ENGLISH POSTINGS FOUND")
        report.append(f"  (Jobs posted in other languages but requiring English work)")
        lang_names = {
            'de': 'German', 'fr': 'French', 'nl': 'Dutch',
            'sv': 'Swedish', 'no': 'Norwegian', 'fi': 'Finnish',
            'ja': 'Japanese', 'ko': 'Korean', 'pl': 'Polish',
            'ar': 'Arabic',
        }
        for item in non_english:
            lang = lang_names.get(item['posting_language'], item['posting_language'])
            report.append(f"  {lang}: {item['count']} jobs")

    if transitions.exists():
        report.append(f"\n🔄 ALL STATE TRANSITIONS THIS WEEK")
        for t in transitions[:10]:
            emoji = '🔥' if t.new_state == 'active' else '📋'
            report.append(
                f"  {emoji} {t.company.name}: "
                f"{t.previous_state} → {t.new_state} "
                f"({t.changed_at.strftime('%b %d')})"
            )

    report.append(f"\n📡 CRAWLER HEALTH")
    report.append(f"  Total crawls:    {total_crawls}")
    report.append(f"  Successful:      {successful_crawls} ({success_rate}%)")
    report.append(f"  Blocked:         {blocked_crawls}")

    # Taxonomy summary
    established = Taxonomy.objects.filter(status='established').count()
    emerging = Taxonomy.objects.filter(status='emerging').count()
    hypothesis = Taxonomy.objects.filter(status='hypothesis').count()

    report.append(f"\n🧠 LIVING TAXONOMY STATUS")
    report.append(f"  Established categories: {established}")
    report.append(f"  Emerging categories:    {emerging}")
    report.append(f"  Hypothesis:             {hypothesis}")

    report.append(f"\n  Total jobs in database: {Job.objects.count()}")
    report.append(f"  Total companies:        {Company.objects.count()}")

    report.append("\n" + "=" * 60)

    report_text = "\n".join(report)
    print(report_text)
    return report_text