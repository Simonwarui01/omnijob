from django.contrib import admin
from .models import Company, Job, JobStateHistory, Taxonomy, SearchSeed, CrawlLog
from .models import DiscoveredSource


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'country_name', 'status', 'trust_score', 'first_seen', 'last_checked']
    list_filter = ['status', 'country_code']
    search_fields = ['name', 'website', 'country_name']
    ordering = ['-first_seen']


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'job_type', 'vacancy_state', 'geo_tier', 'posting_language', 'work_language', 'is_new', 'first_seen']
    list_filter = ['job_type', 'vacancy_state', 'geo_tier', 'is_new', 'citizenship_flag']
    search_fields = ['title', 'company__name']
    ordering = ['-first_seen']


@admin.register(JobStateHistory)
class JobStateHistoryAdmin(admin.ModelAdmin):
    list_display = ['company', 'previous_state', 'new_state', 'changed_at']
    ordering = ['-changed_at']


@admin.register(Taxonomy)
class TaxonomyAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'confidence_score', 'job_count', 'weekly_growth', 'first_detected']
    list_filter = ['status']
    search_fields = ['name']


@admin.register(SearchSeed)
class SearchSeedAdmin(admin.ModelAdmin):
    list_display = ['query', 'language', 'country_code', 'category', 'results_found', 'last_run', 'is_active']
    list_filter = ['language', 'is_active']
    search_fields = ['query']


@admin.register(CrawlLog)
class CrawlLogAdmin(admin.ModelAdmin):
    list_display = ['url', 'company', 'status', 'http_code', 'protection_level', 'jobs_found', 'crawled_at']
    list_filter = ['status', 'protection_level']
    ordering = ['-crawled_at']


@admin.register(DiscoveredSource)
class DiscoveredSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'country_name', 'posting_language', 'work_language', 'jobs_found_total', 'last_crawled', 'is_active']
    list_filter = ['source_type', 'country_code', 'posting_language', 'is_active']
    search_fields = ['name', 'url', 'country_name']