from django.shortcuts import render
from django.db.models import Count, Q
from .models import Company, Job, JobStateHistory, Taxonomy, CrawlLog, DiscoveredSource
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from core.models import JobApplication
import json

def dashboard(request):
    from core.models import Notification
    
    # Mark notifications as read when dashboard is visited
    unread = Notification.objects.filter(is_read=False)
    unread_count = unread.count()
    
    context = {
        'total_companies': Company.objects.count(),
        'total_jobs': Job.objects.count(),
        'active_jobs': Job.objects.filter(vacancy_state='active').count(),
        'ghost_jobs': Job.objects.filter(vacancy_state='ghost_pipeline').count(),
        'new_jobs': Job.objects.filter(is_new=True).count(),
        'worldwide_jobs': Job.objects.filter(geo_tier=1).count(),
        'recent_jobs': Job.objects.select_related('company').order_by('-first_seen')[:10],
        'recent_companies': Company.objects.order_by('-first_seen')[:5],
        'recent_transitions': JobStateHistory.objects.select_related('company').order_by('-changed_at')[:5],
        'crawl_success': CrawlLog.objects.filter(status='success').count(),
        'crawl_blocked': CrawlLog.objects.filter(status='blocked').count(),
        'unread_notifications': unread_count,
        'notifications': Notification.objects.filter(is_read=False)[:10],
    }
    
    # Mark all as read after showing
    unread.update(is_read=True)
    
    return render(request, 'dashboard/home.html', context)


def companies(request):
    qs = Company.objects.all()
    search = request.GET.get('q')
    status = request.GET.get('status')
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(country_name__icontains=search))
    if status:
        qs = qs.filter(status=status)
    return render(request, 'dashboard/companies.html', {'companies': qs, 'search': search, 'status': status})


def jobs(request):
    qs = Job.objects.select_related('company').all()
    search = request.GET.get('q')
    job_type = request.GET.get('type')
    state = request.GET.get('state')
    geo = request.GET.get('geo')
    work_lang = request.GET.get('work_lang')
    posting_lang = request.GET.get('posting_lang')
    onboarding = request.GET.get('onboarding')
    citizenship = request.GET.get('citizenship')

    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(company__name__icontains=search))
    if job_type:
        qs = qs.filter(job_type=job_type)
    if state:
        qs = qs.filter(vacancy_state=state)
    if geo:
        qs = qs.filter(geo_tier=geo)
    if work_lang:
        qs = qs.filter(work_language__icontains=work_lang)
    if posting_lang:
        qs = qs.filter(posting_language=posting_lang)
    if onboarding:
        qs = qs.filter(onboarding_level=onboarding)
    if citizenship:
        qs = qs.filter(citizenship_flag=True)

    hidden_gems = request.GET.get('hidden_gems')
    if hidden_gems:
        # Exclude saturated well-known platforms
        saturated = [
            'rev', 'gotranscript', 'scribie', 'transcribeme', 'happyscribe',
            'appen', 'telus', 'welocalize', 'lionbridge', 'outlier',
            'dataannotation', 'castingwords', 'speechify', 'crowdsurf',
            'daily transcription', 'speakwrite', 'remotasks', 'prolific',
            'microworkers', 'clickworker', 'amazon mechanical', 'mturk',
        ]
        for s in saturated:
            qs = qs.exclude(company__name__icontains=s)
        # Only show non-English posted jobs (European/Asian companies)
        qs = qs.exclude(posting_language='en')

    # Convert to list and mark verified URLs
    TRUSTED_DOMAINS = [
        'lever.co', 'greenhouse.io', 'job-boards.greenhouse.io',
        'jobs.lever.co', 'boards.greenhouse.io',
    ]
    jobs_list = list(qs.order_by('-first_seen'))
    for job in jobs_list:
        job.is_verified_url = any(d in job.apply_url for d in TRUSTED_DOMAINS)

    return render(request, 'dashboard/jobs.html', {
        'jobs': jobs_list,
        'search': search,
        'job_type': job_type,
        'state': state,
        'geo': geo,
        'work_lang': work_lang,
        'posting_lang': posting_lang,
        'onboarding': onboarding,
        'citizenship': citizenship,
        'hidden_gems': hidden_gems,
    })


def taxonomy(request):
    established = Taxonomy.objects.filter(status='established')
    emerging = Taxonomy.objects.filter(status='emerging')
    hypothesis = Taxonomy.objects.filter(status='hypothesis')
    return render(request, 'dashboard/taxonomy.html', {
        'established': established,
        'emerging': emerging,
        'hypothesis': hypothesis,
    })


def crawl_logs(request):
    logs = CrawlLog.objects.select_related('company').order_by('-crawled_at')[:100]
    return render(request, 'dashboard/crawl_logs.html', {'logs': logs})

def sources(request):
    qs = DiscoveredSource.objects.all()
    search = request.GET.get('q')
    source_type = request.GET.get('type')
    country = request.GET.get('country')
    lang = request.GET.get('lang')

    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(url__icontains=search))
    if source_type:
        qs = qs.filter(source_type=source_type)
    if country:
        qs = qs.filter(country_code=country)
    if lang:
        qs = qs.filter(posting_language=lang)

    return render(request, 'dashboard/sources.html', {
        'sources': qs,
        'search': search,
        'source_type': source_type,
        'country': country,
        'lang': lang,
        'total': qs.count(),
    })

@csrf_exempt
@require_POST
def track_application(request, job_id):
    """Save or update application status for a job."""
    try:
        data = json.loads(request.body)
        job = Job.objects.get(id=job_id)

        application, created = JobApplication.objects.get_or_create(
            job=job,
            email_used=data.get('email', ''),
        )
        application.status = data.get('status', 'applied')
        application.notes = data.get('notes', '')
        if data.get('status') == 'applied':
            from django.utils import timezone
            application.applied_at = timezone.now()
        application.save()

        return JsonResponse({
            'success': True,
            'status': application.status,
            'email': application.email_used,
            'id': application.id,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
def get_applications(request, job_id):
    """Get all applications for a job."""
    try:
        apps = JobApplication.objects.filter(job_id=job_id)
        return JsonResponse({
            'applications': [
                {
                    'id': a.id,
                    'status': a.status,
                    'email': a.email_used,
                    'notes': a.notes,
                    'applied_at': a.applied_at.isoformat() if a.applied_at else None,
                }
                for a in apps
            ]
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def my_applications(request):
    from core.models import JobApplication
    
    status_filter = request.GET.get('status')
    email_filter = request.GET.get('email')
    
    qs = JobApplication.objects.select_related('job', 'job__company').order_by('-updated_at')
    
    if status_filter:
        qs = qs.filter(status=status_filter)
    if email_filter:
        qs = qs.filter(email_used=email_filter)
    
    # Get all unique emails used
    emails = JobApplication.objects.values_list('email_used', flat=True).distinct()
    
    # Group by status for counts
    from django.db.models import Count
    status_counts = JobApplication.objects.values('status').annotate(count=Count('id'))
    counts = {s['status']: s['count'] for s in status_counts}
    
    return render(request, 'dashboard/my_applications.html', {
        'applications': qs,
        'status_filter': status_filter,
        'email_filter': email_filter,
        'emails': emails,
        'counts': counts,
        'total': qs.count(),
    })


def notifications(request):
    from core.models import Notification
    all_notifs = Notification.objects.all()[:50]
    return render(request, 'dashboard/notifications.html', {'notifications': all_notifs})

def get_unread_count():
    from core.models import Notification
    return Notification.objects.filter(is_read=False).count()


@csrf_exempt
@require_POST
def mark_viewed(request, job_id):
    try:
        Job.objects.filter(id=job_id).update(is_viewed=True)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST  
def toggle_queue(request, job_id):
    try:
        job = Job.objects.get(id=job_id)
        job.is_queued = not job.is_queued
        job.save()
        return JsonResponse({'success': True, 'is_queued': job.is_queued})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def apply_queue(request):
    queued = Job.objects.filter(is_queued=True).select_related('company').order_by('-first_seen')
    
    TRUSTED_DOMAINS = ['lever.co', 'greenhouse.io', 'job-boards.greenhouse.io']
    jobs_list = list(queued)
    for job in jobs_list:
        job.is_verified_url = any(d in job.apply_url for d in TRUSTED_DOMAINS)
    
    return render(request, 'dashboard/apply_queue.html', {
        'jobs': jobs_list,
        'total': queued.count(),
    })