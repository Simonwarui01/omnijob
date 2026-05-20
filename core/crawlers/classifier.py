import anthropic
import json
import logging
import os

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))


def classify_job(title, description='', company_name='', source_url=''):
    """
    Uses Claude API to intelligently classify a job posting.
    Much smarter than keyword matching — understands context,
    reads between the lines, handles any language.
    
    Returns a dict with all classification fields.
    """

    prompt = f"""You are an expert at classifying remote freelance job opportunities.

Analyze this job posting and return a JSON classification.

Job Title: {title}
Company: {company_name}
Description/Location: {description}
Source URL: {source_url}

Rules:
1. We ONLY want task-based remote work that a motivated person without a professional degree can do
2. We DO NOT want professional career jobs (software engineer, doctor, lawyer, accountant, etc.)
3. posting_language = language this job post is written in (ISO 639-1 code)
4. work_language = language the actual WORK requires (not the posting language)
5. geo_tier: 0=unknown, 1=worldwide no restriction, 2=Africa/Kenya friendly, 3=citizenship flag but remote, 4=region restricted, 5=physical presence required
6. onboarding_level: 1=test only auto-approve, 2=async form/email, 3=video/phone interview, 4=document heavy
7. is_relevant: true ONLY for task-based work (transcription, annotation, AI training, translation, voice recording, captioning, content moderation, quality rating, data collection, etc.)
8. physical_required: true only if job literally cannot be done remotely

Return ONLY valid JSON, no other text:
{{
  "is_relevant": true/false,
  "job_type": "transcription|annotation|ai_training|translation|voice|content_moderation|qa|other",
  "posting_language": "en",
  "work_language": "en",
  "geo_tier": 0,
  "onboarding_level": 2,
  "citizenship_flag": false,
  "citizenship_note": "",
  "physical_required": false,
  "confidence": 0-100,
  "reason": "brief explanation"
}}"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text.strip()

        # Clean up response if needed
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()

        result = json.loads(response_text)
        return result

    except json.JSONDecodeError as e:
        logger.error(f'Claude API JSON parse error: {e}')
        return None
    except Exception as e:
        logger.error(f'Claude API error: {e}')
        return None


def classify_batch(jobs_data):
    """
    Classifies multiple jobs efficiently.
    Falls back to keyword matching if API fails.
    
    jobs_data: list of dicts with title, description, company_name, source_url
    Returns: list of classification results
    """
    results = []
    for job in jobs_data:
        result = classify_job(
            title=job.get('title', ''),
            description=job.get('description', ''),
            company_name=job.get('company_name', ''),
            source_url=job.get('source_url', ''),
        )
        results.append(result)
    return results


def is_relevant_ai(title, description='', company_name=''):
    """
    Quick relevance check using Claude.
    Used as a smarter replacement for keyword-based is_relevant().
    Falls back to True (include) if API fails to avoid missing jobs.
    """
    result = classify_job(title, description, company_name)
    if result is None:
        return True  # Fail open — don't miss jobs due to API error
    return result.get('is_relevant', True)