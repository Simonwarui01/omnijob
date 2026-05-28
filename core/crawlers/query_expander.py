import logging
from django.utils import timezone
from core.models import DynamicQuery, Job, Notification

logger = logging.getLogger(__name__)


def expand_queries_from_new_jobs():
    """
    Looks at recently discovered jobs and generates new search queries
    based on what was found. Makes the system self-learning.
    """
    from core.crawlers.ai_client import client, DEPLOYMENT
    import json

    # Get jobs found in last 24 hours
    from datetime import timedelta
    recent_jobs = Job.objects.filter(
        first_seen__gte=timezone.now() - timedelta(days=30)
    ).select_related('company')

    if not recent_jobs.exists():
        return 0

    # Build context for Claude
    job_list = []
    for job in recent_jobs[:30]:
        job_list.append(f"- {job.title} at {job.company.name} [{job.posting_language}→{job.work_language}]")

    prompt = f"""You are helping expand a job discovery system that finds companies hiring remote freelance transcribers and AI data annotators worldwide.

Recently discovered jobs:
{chr(10).join(job_list)}

Based on these discoveries, suggest 20 NEW search queries to find MORE unknown companies hiring transcribers or AI annotators.

STRICT RULES:
1. ONLY suggest queries for transcription jobs OR AI data annotation/labeling jobs
2. NO surveys, tutoring, virtual assistants, copywriting, or other job types
3. Target UNKNOWN companies — not famous ones like Appen or Rev
4. Queries must be in different languages (en, fr, de, nl, ja, ko, zh, es, pt, it, sv, pl, ar)
5. Focus on niche transcription (medical, legal, podcast, court, academic) and niche annotation (autonomous vehicles, healthcare AI, NLP, computer vision)
6. Queries should find DIRECT employer pages, not job boards or aggregators

Return ONLY a JSON array:
[
  {{"lang": "en", "query": "exact search query here", "reason": "why this finds unknown companies"}},
  {{"lang": "fr", "query": "requête ici", "reason": "pourquoi cela trouve de nouvelles entreprises"}}
]

Return ONLY valid JSON, no other text."""

    try:
        message = client.chat.completions.create(
            model=DEPLOYMENT,
            max_tokens=2000,
            messages=[{'role': 'user', 'content': prompt}]
        )

        response_text = message.choices[0].message.content.strip()
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()

        new_queries = json.loads(response_text)
        added = 0

        for q in new_queries:
            lang = q.get('lang', 'en')
            query = q.get('query', '')
            reason = q.get('reason', '')

            if not query or len(query) < 5:
                continue

            _, created = DynamicQuery.objects.get_or_create(
                lang=lang,
                query=query,
                defaults={
                    'source': f'Auto-generated: {reason[:200]}',
                    'is_active': True,
                }
            )
            if created:
                added += 1
                print(f'  🔍 New query added [{lang}]: {query[:60]}')

                # Notify dashboard
                Notification.objects.create(
                    notification_type='new_query',
                    title=f'New search query added',
                    message=f'[{lang}] {query} — Reason: {reason}',
                )

        print(f'  Added {added} new queries to the rotation')
        return added

    except Exception as e:
        logger.error(f'Query expansion error: {e}')
        return 0