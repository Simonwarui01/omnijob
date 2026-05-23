import logging
from django.utils import timezone
from core.models import DynamicQuery, Job, Notification

logger = logging.getLogger(__name__)


def expand_queries_from_new_jobs():
    """
    Looks at recently discovered jobs and generates new search queries
    based on what was found. Makes the system self-learning.
    """
    from core.crawlers.classifier import client
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

    prompt = f"""You are helping expand a job discovery system that finds remote freelance work for English speakers.

Recently discovered jobs:
{chr(10).join(job_list)}

Based on these discoveries, suggest 10 NEW search queries we should add to find MORE similar opportunities we might be missing.

Focus on:
1. New job types or variations we haven't searched for
2. Different languages or regions where similar work exists
3. Specific niches within categories (e.g. "medical transcription" vs just "transcription")
4. Companies or platforms similar to what we found

Return ONLY a JSON array of new queries:
[
  {{"lang": "en", "query": "search query here", "reason": "why this will find new opportunities"}},
  {{"lang": "de", "query": "suchanfrage hier", "reason": "warum das neue Möglichkeiten findet"}}
]

Make queries specific and likely to find REAL hiring pages, not articles.
Return ONLY valid JSON."""

    try:
        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1000,
            messages=[{'role': 'user', 'content': prompt}]
        )

        response_text = message.content[0].text.strip()
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