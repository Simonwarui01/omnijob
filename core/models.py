from django.db import models


class Company(models.Model):
    """Every company the system discovers"""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('blocked', 'Blocked'),
    ]

    name = models.CharField(max_length=255)
    website = models.URLField(max_length=500, unique=True)
    careers_url = models.URLField(max_length=500, blank=True)
    country_code = models.CharField(max_length=10, blank=True)
    country_name = models.CharField(max_length=100, blank=True)
    discovered_via = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    trust_score = models.IntegerField(default=50)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    last_active = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['-first_seen']

    def __str__(self):
        return f"{self.name} ({self.country_name or self.country_code or 'Unknown'})"


class Job(models.Model):
    """Every job opportunity discovered"""

    # Vacancy states
    VACANCY_ACTIVE = 'active'
    VACANCY_GHOST = 'ghost_pipeline'
    VACANCY_CLOSED = 'closed'
    VACANCY_NO_PAGE = 'no_page'
    VACANCY_UNKNOWN = 'unknown'

    VACANCY_STATE_CHOICES = [
        (VACANCY_ACTIVE, 'Active — real vacancy'),
        (VACANCY_GHOST, 'Ghost pipeline — no real vacancy'),
        (VACANCY_CLOSED, 'Closed — not hiring'),
        (VACANCY_NO_PAGE, 'No careers page yet'),
        (VACANCY_UNKNOWN, 'Unknown'),
    ]

    # Geography tiers
    GEO_UNKNOWN = 0
    GEO_WORLDWIDE = 1
    GEO_AFRICA = 2
    GEO_LEGAL_FLAG = 3
    GEO_REGION = 4
    GEO_PHYSICAL = 5

    GEO_TIER_CHOICES = [
        (GEO_UNKNOWN, 'Unknown / not specified'),
        (GEO_WORLDWIDE, 'Worldwide — no restriction'),
        (GEO_AFRICA, 'Africa / Kenya explicitly included'),
        (GEO_LEGAL_FLAG, 'Legal/citizenship flag — remote work'),
        (GEO_REGION, 'Region restricted — investigate'),
        (GEO_PHYSICAL, 'Physical presence required — skip'),
    ]

    # Onboarding levels
    ONBOARD_TEST = 1
    ONBOARD_ASYNC = 2
    ONBOARD_VIDEO = 3
    ONBOARD_DOCUMENT = 4

    ONBOARD_CHOICES = [
        (ONBOARD_TEST, 'Level 1 — Test only, auto-onboard'),
        (ONBOARD_ASYNC, 'Level 2 — Async form + review'),
        (ONBOARD_VIDEO, 'Level 3 — Live video/phone interview'),
        (ONBOARD_DOCUMENT, 'Level 4 — Document heavy'),
    ]

    # Job types
    JOB_TYPE_CHOICES = [
        ('transcription', 'Transcription'),
        ('annotation', 'Data Annotation'),
        ('ai_training', 'AI Training'),
        ('translation', 'Translation'),
        ('voice', 'Voice Recording'),
        ('content_moderation', 'Content Moderation'),
        ('qa', 'Quality Assurance'),
        ('emerging', 'Emerging Category'),
        ('other', 'Other'),
    ]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='jobs'
    )
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    apply_url = models.URLField(max_length=500, blank=True)

    # Language intelligence — always two separate fields
    posting_language = models.CharField(
        max_length=10, default='en',
        help_text='Language the job post is written in e.g. de, fr, fi'
    )
    work_language = models.CharField(
        max_length=100, default='en',
        help_text='Language the actual work requires e.g. en, fr, es'
    )

    # Classification
    job_type = models.CharField(
        max_length=50, choices=JOB_TYPE_CHOICES, default='other'
    )
    vacancy_state = models.CharField(
        max_length=20, choices=VACANCY_STATE_CHOICES, default=VACANCY_UNKNOWN
    )
    geo_tier = models.IntegerField(
        choices=GEO_TIER_CHOICES, default=GEO_UNKNOWN
    )
    onboarding_level = models.IntegerField(
        choices=ONBOARD_CHOICES, null=True, blank=True
    )

    # Citizenship flag — completely separate from physical requirement
    citizenship_flag = models.BooleanField(default=False)
    citizenship_note = models.CharField(max_length=500, blank=True)
    physical_required = models.BooleanField(default=False)

    # Deduplication
    fingerprint = models.CharField(max_length=64, unique=True)

    # Timestamps
    first_seen = models.DateTimeField(auto_now_add=True)
    last_confirmed = models.DateTimeField(null=True, blank=True)
    is_new = models.BooleanField(default=True)

    is_viewed = models.BooleanField(default=False)
    is_queued = models.BooleanField(default=False)

    class Meta:
        ordering = ['-first_seen']

    def __str__(self):
        return f"{self.title} — {self.company.name}"


class JobStateHistory(models.Model):
    """Full history of every vacancy state change per company"""

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='state_history'
    )
    previous_state = models.CharField(max_length=20, blank=True)
    new_state = models.CharField(max_length=20)
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Job state histories'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.company.name}: {self.previous_state} → {self.new_state}"


class Taxonomy(models.Model):
    """Living self-evolving job category map"""

    STATUS_CHOICES = [
        ('established', 'Established'),
        ('emerging', 'Emerging'),
        ('hypothesis', 'Hypothesis'),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='hypothesis'
    )
    confidence_score = models.IntegerField(
        default=50,
        help_text='0-100 confidence this is a real growing category'
    )
    job_count = models.IntegerField(default=0)
    weekly_growth = models.FloatField(
        default=0.0,
        help_text='Week over week growth percentage'
    )
    first_detected = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Taxonomy'
        ordering = ['-job_count']

    def __str__(self):
        return f"{self.name} ({self.status})"


class SearchSeed(models.Model):
    """Search queries the system fires automatically"""

    query = models.CharField(max_length=500)
    language = models.CharField(
        max_length=10, default='en',
        help_text='Language of the query e.g. de, fr, en'
    )
    country_code = models.CharField(max_length=10, blank=True)
    category = models.CharField(max_length=100, blank=True)
    last_run = models.DateTimeField(null=True, blank=True)
    results_found = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-results_found']

    def __str__(self):
        return f"[{self.language}] {self.query}"


class CrawlLog(models.Model):
    """Log of every crawl attempt — success or failure"""

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('blocked', 'Blocked'),
        ('error', 'Error'),
        ('captcha', 'CAPTCHA'),
        ('empty', 'Empty'),
    ]

    url = models.URLField(max_length=500)
    company = models.ForeignKey(
        Company, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='crawl_logs'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    http_code = models.IntegerField(null=True, blank=True)
    protection_level = models.IntegerField(
        null=True, blank=True,
        help_text='1=none, 2=basic, 3=JS, 4=Cloudflare, 5=Enterprise'
    )
    jobs_found = models.IntegerField(default=0)
    crawled_at = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-crawled_at']

    def __str__(self):
        return f"{self.status.upper()} — {self.url} ({self.crawled_at:%Y-%m-%d %H:%M})"


class DiscoveredSource(models.Model):
    """
    Every URL the system discovers that could contain jobs.
    Built dynamically — never hardcoded.
    Includes company careers pages, job boards, ATS pages.
    New sources are added automatically as the system searches.
    """

    SOURCE_TYPE_CHOICES = [
        ('company_careers', 'Company Careers Page'),
        ('job_board', 'Job Board'),
        ('ats_page', 'ATS Platform Page'),
        ('social', 'Social / Community'),
        ('unknown', 'Unknown'),
    ]

    url = models.URLField(max_length=1000, unique=True)
    name = models.CharField(max_length=255, blank=True)
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default='unknown'
    )
    country_code = models.CharField(max_length=10, blank=True)
    country_name = models.CharField(max_length=100, blank=True)
    posting_language = models.CharField(
        max_length=10, default='en',
        help_text='Language this source posts jobs in'
    )
    work_language = models.CharField(
        max_length=10, blank=True,
        help_text='Language the work requires if known'
    )
    discovered_via = models.CharField(max_length=255, blank=True)
    discovered_query = models.TextField(
        blank=True,
        help_text='The search query that found this source'
    )

    # Crawl scheduling
    is_active = models.BooleanField(default=True)
    last_crawled = models.DateTimeField(null=True, blank=True)
    crawl_frequency_hours = models.IntegerField(
        default=24,
        help_text='How often to re-crawl in hours'
    )
    consecutive_failures = models.IntegerField(default=0)
    protection_level = models.IntegerField(
        default=1,
        help_text='1=none, 2=basic, 3=JS, 4=Cloudflare'
    )

    # Quality signals
    jobs_found_total = models.IntegerField(default=0)
    last_job_found = models.DateTimeField(null=True, blank=True)
    trust_score = models.IntegerField(default=50)

    first_discovered = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-jobs_found_total', '-first_discovered']
        verbose_name = 'Discovered Source'
        verbose_name_plural = 'Discovered Sources'

    def __str__(self):
        return f"{self.name or self.url} [{self.country_code}] ({self.source_type})"


class JobApplication(models.Model):
    STATUS_CHOICES = [
        ('saved', '📌 Saved for Later'),
        ('applied', '✅ Applied'),
        ('pending_test', '📝 Test Pending'),
        ('test_passed', '🎯 Test Passed'),
        ('approved', '✅ Account Approved'),
        ('active_worker', '🟢 Active — Getting Work'),
        ('no_work', '⏳ Approved — No Work Yet'),
        ('follow_up', '📅 Follow Up Later'),
        ('waitlisted', '⏸️ Waitlisted'),
        ('interview', '🎙️ Interview Scheduled'),
        ('rejected', '❌ Rejected'),
        ('withdrawn', '↩️ Withdrawn'),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='saved')
    email_used = models.EmailField(blank=True, null=True)
    notes = models.TextField(blank=True, default='')
    applied_at = models.DateTimeField(null=True, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    platform_username = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.job.title} — {self.status} ({self.email_used})'

class Notification(models.Model):
    TYPE_CHOICES = [
        ('new_job', '💼 New Job'),
        ('new_company', '🏢 New Company'),
        ('ghost_to_active', '🔥 Ghost → Active'),
        ('new_query', '🔍 New Search Query'),
    ]
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL)
    job = models.ForeignKey(Job, null=True, blank=True, on_delete=models.SET_NULL)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.notification_type}: {self.title}'

class DynamicQuery(models.Model):
    lang = models.CharField(max_length=10, default='en')
    query = models.CharField(max_length=500)
    source = models.CharField(max_length=200, blank=True)
    times_run = models.IntegerField(default=0)
    jobs_found_total = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_run = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-jobs_found_total']
        unique_together = ['lang', 'query']

    def __str__(self):
        return f'[{self.lang}] {self.query[:60]}'