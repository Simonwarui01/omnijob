from core.crawlers.ai_client import client, DEPLOYMENT
import logging
from django.utils.text import slugify
from django.db.models import Count
from core.models import Job, Taxonomy

logger = logging.getLogger(__name__)


def update_taxonomy():
    """
    Updates the living taxonomy based on jobs in the database.
    Promotes categories from hypothesis → emerging → established
    based on job volume and growth.
    """
    print("🧠 Updating living taxonomy...")

    # Count jobs per type
    job_counts = Job.objects.values('job_type').annotate(
        count=Count('id')
    ).order_by('-count')

    # Thresholds for promotion
    ESTABLISHED_THRESHOLD = 20
    EMERGING_THRESHOLD = 5
    HYPOTHESIS_THRESHOLD = 1

    updated = 0
    promoted = 0

    for entry in job_counts:
        job_type = entry['job_type']
        count = entry['count']

        if job_type == 'other':
            continue

        # Human-readable names
        name_map = {
            'transcription': 'Transcription',
            'annotation': 'Data Annotation',
            'ai_training': 'AI Training',
            'translation': 'Translation',
            'voice': 'Voice Recording',
            'content_moderation': 'Content Moderation',
            'qa': 'Quality Assurance',
            'emerging': 'Emerging Categories',
        }

        desc_map = {
            'transcription': 'Converting audio/video to text. Includes general, legal, medical, and specialized transcription.',
            'annotation': 'Labeling data for machine learning. Includes image, text, audio, and video annotation.',
            'ai_training': 'Training AI models through RLHF, prompt evaluation, model testing, and feedback tasks.',
            'translation': 'Converting content between languages. Includes translation, localization, and MTPE.',
            'voice': 'Recording voice samples, narration, and audio content for AI and media production.',
            'content_moderation': 'Reviewing and moderating user-generated content for platforms and applications.',
            'qa': 'Quality rating, search evaluation, and general quality assurance tasks.',
            'emerging': 'New job categories emerging from AI and technology developments.',
        }

        # Determine status based on count
        if count >= ESTABLISHED_THRESHOLD:
            new_status = 'established'
            confidence = min(95, 70 + count)
        elif count >= EMERGING_THRESHOLD:
            new_status = 'emerging'
            confidence = min(75, 50 + count * 5)
        else:
            new_status = 'hypothesis'
            confidence = min(50, 30 + count * 10)

        name = name_map.get(job_type, job_type.replace('_', ' ').title())
        slug = slugify(name)

        taxonomy, created = Taxonomy.objects.get_or_create(
            slug=slug,
            defaults={
                'name': name,
                'description': desc_map.get(job_type, ''),
                'status': new_status,
                'confidence_score': confidence,
                'job_count': count,
            }
        )

        if not created:
            old_status = taxonomy.status
            taxonomy.job_count = count
            taxonomy.confidence_score = confidence

            # Only promote, never demote
            status_rank = {'hypothesis': 1, 'emerging': 2, 'established': 3}
            if status_rank.get(new_status, 0) > status_rank.get(old_status, 0):
                taxonomy.status = new_status
                promoted += 1
                print(f"  📈 PROMOTED: {name} → {new_status} ({count} jobs)")

            taxonomy.save()
            updated += 1
        else:
            print(f"  ✅ New category: {name} ({new_status}, {count} jobs)")
            updated += 1

    # Also check for completely new job patterns using AI
    detect_emerging_patterns()

    print(f"\n  ✅ Taxonomy updated: {updated} categories, {promoted} promotions")
    print(f"  📊 Current taxonomy:")
    for t in Taxonomy.objects.order_by('-job_count'):
        print(f"     [{t.status}] {t.name}: {t.job_count} jobs ({t.confidence_score}% confidence)")

    return updated


def detect_emerging_patterns():
    """
    Uses Claude API to detect entirely new job categories
    from recent job titles that don't fit existing types.
    """
    try:
        from core.crawlers.classifier import client

        # Get recent 'other' type jobs — these are unclassified
        other_jobs = Job.objects.filter(
            job_type='other'
        ).order_by('-first_seen')[:20]

        if not other_jobs.exists():
            return

        titles = [j.title for j in other_jobs]

        prompt = f"""Analyze these unclassified remote job titles and identify if any represent 
a genuinely new category of task-based remote work that doesn't fit these existing categories:
transcription, annotation, ai_training, translation, voice, content_moderation, qa

Job titles:
{chr(10).join(f'- {t}' for t in titles)}

If you see a new genuine task-based category, return JSON:
{{"new_category": true, "name": "Category Name", "description": "What workers do", "confidence": 0-100}}

If no new category found:
{{"new_category": false}}

Return ONLY valid JSON."""

        message = client.chat.completions.create(
            model=DEPLOYMENT,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        import json
        result = json.loads(message.choices[0].message.content.strip())

        if result.get('new_category') and result.get('confidence', 0) > 60:
            name = result['name']
            slug = slugify(name)
            taxonomy, created = Taxonomy.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'description': result.get('description', ''),
                    'status': 'hypothesis',
                    'confidence_score': result['confidence'],
                    'job_count': other_jobs.count(),
                }
            )
            if created:
                print(f"  🆕 NEW CATEGORY DETECTED: {name} (confidence: {result['confidence']}%)")

    except Exception as e:
        logger.error(f'Emerging pattern detection error: {e}')