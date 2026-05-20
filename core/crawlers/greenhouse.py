import httpx
import hashlib
import logging
import time
import random
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from django.utils import timezone
from core.models import Company, Job, CrawlLog, DiscoveredSource, JobStateHistory

logger = logging.getLogger(__name__)

# ─── KEYWORD INTELLIGENCE ─────────────────────────────────────────────────────

RELEVANT_KEYWORDS = [
    # English
    'transcription', 'transcriptionist', 'transcriber',
    'annotation', 'annotator', 'data labeling', 'data labelling',
    'image labeling', 'text labeling', 'audio labeling',
    'ai training', 'rlhf', 'llm evaluation', 'prompt evaluation',
    'model evaluation', 'ai evaluation', 'data collection',
    'content moderation', 'moderator', 'trust and safety',
    'translation', 'translator', 'localization',
    'voice recording', 'voice actor', 'voice talent', 'voice over',
    'captioning', 'subtitling', 'subtitle', 'closed caption',
    'microtask', 'micro task', 'search evaluation',
    'search quality', 'quality rater', 'quality evaluator',
    'data entry', 'survey taker', 'usability tester',
    'ai trainer', 'ai training specialist', 'study participant',
    'participant', 'fluency', 'language fluency', 'language trainer',
    'image annotation', 'video annotation', 'data quality',
    'linguist', 'linguistic', 'language specialist',
    'language expert', 'native speaker', 'bilingual',
    'proofreader', 'proofreading', 'copy editor',
    'closed captioning', 'live captioning',
    'data labeler', 'data tagger', 'content reviewer',
    'search rater', 'map analyst', 'internet assessor',
    'online juror', 'telemedicine', 'remote evaluator',
    # German
    'transkription', 'transkribent', 'datenannotation',
    'sprachaufnahme', 'qualitätsbewertung', 'datenbeschriftung',
    'freiberuflich', 'heimarbeit', 'übersetzung', 'dolmetscher',
    # French
    'transcripteur', 'annotateur', 'modération de contenu',
    'évaluation', 'collecte de données', 'télétravail',
    'traduction', 'sous-titrage',
    # Dutch
    'transcriptie', 'annotatie', 'gegevensverzameling',
    'thuiswerk', 'ondertiteling', 'vertaling',
    # Swedish
    'transkribering', 'annotering', 'datainsamling',
    'distansarbete', 'textning', 'översättning',
    # Norwegian
    'transkripsjon', 'annotering', 'datainnsamling',
    'hjemmekontor', 'teksting', 'oversettelse',
    # Finnish
    'transkriptio', 'annotointi', 'tiedonkeruu',
    'etätyö', 'tekstitys', 'käännöstyö',
    # Japanese
    '文字起こし', 'アノテーション', 'データ収集',
    'リモートワーク', '翻訳', '字幕',
    # Korean
    '전사', '어노테이션', '데이터 수집',
    '재택근무', '번역', '자막',
    # Polish
    'transkrypcja', 'adnotacja', 'zbieranie danych',
    'praca zdalna', 'tłumaczenie',
    # Czech
    'přepis', 'anotace', 'sběr dat', 'práce z domova',
    # Arabic
    'نسخ', 'تعليق توضيحي', 'جمع البيانات', 'عمل عن بعد',
]

EXCLUDE_KEYWORDS = [
    'software engineer', 'senior engineer', 'staff engineer',
    'developer', 'ceo', 'cto', 'cfo', 'vp of', 'vice president',
    'director of', 'head of', 'chief ', 'accountant', 'lawyer',
    'attorney', 'doctor', 'physician', 'nurse', 'architect',
    'data scientist', 'machine learning engineer', 'devops',
    'product manager', 'sales manager', 'marketing manager',
    'hr manager', 'recruiter', 'finance manager', 'legal counsel',
    'investment', 'business development', 'security engineer',
    'infrastructure', 'backend engineer', 'frontend engineer',
    'full stack', 'fullstack', 'ios engineer', 'android engineer',
    'ai training - lawyers', 'ai training - accountants',
    'ai training - research scientist', 'ai training - machine learning',
    'medical doctors', 'registered nurses', 'audiologists',
    'psychologists', 'clinicians', 'physicians',
    'application security', 'engineering manager',
    'data science manager', 'head of', 'solutions engineer',
]

# ─── DYNAMIC SEARCH QUERIES ───────────────────────────────────────────────────
# These generate search results that discover BOTH:
# 1. Company careers pages directly
# 2. Job boards in those countries
# Nothing is hardcoded — search finds everything dynamically

SEARCH_QUERIES = [
    # English — find companies and boards
    ('en', 'site:greenhouse.io OR site:lever.co transcription remote worldwide'),
    ('en', 'site:greenhouse.io OR site:lever.co annotation remote worldwide'),
    ('en', 'site:workable.com transcription OR annotation remote worldwide'),
    ('en', '"we are hiring" transcription remote worldwide apply'),
    ('en', '"work from home" transcription annotation "worldwide" apply now'),
    ('en', 'careers transcription annotator "remote" "worldwide" freelance'),
    ('en', '"join our team" transcription annotation remote worldwide'),
    ('en', 'hiring freelance transcriptionist worldwide remote apply'),
    ('en', 'data annotation jobs remote worldwide no experience'),
    ('en', 'AI training data collection remote worldwide freelance apply'),
    ('en', 'quality rater search evaluation remote worldwide apply'),
    ('en', 'content moderation remote worldwide freelance apply'),
    ('en', 'voice recording remote freelance worldwide apply'),
    ('en', 'subtitle captioning remote worldwide freelance'),
    # German — finds German companies AND German job boards
    ('de', 'Transkription freiberuflich weltweit Heimarbeit bewerben'),
    ('de', 'Englisch Transkription Stelle weltweit freiberuflich bewerben'),
    ('de', 'Datenannotation Remote Heimarbeit weltweit bewerben'),
    ('de', 'KI Training Daten freiberuflich weltweit bewerben'),
    ('de', 'Sprachaufnahme Jobs Fernarbeit freiberuflich weltweit'),
    ('de', 'Qualitätsbewertung Englisch freiberuflich weltweit bewerben'),
    ('de', '"wir suchen" Transkription freiberuflich weltweit'),
    ('de', 'Übersetzung Englisch freiberuflich weltweit Heimarbeit'),
    ('de', 'Untertitelung freiberuflich weltweit Remote bewerben'),
    # French — finds French companies AND French job boards
    ('fr', 'transcription anglais freelance monde entier postuler'),
    ('fr', 'annotation données télétravail monde entier freelance'),
    ('fr', 'modération contenu emploi remote monde entier postuler'),
    ('fr', 'évaluation IA freelance monde entier postuler'),
    ('fr', '"nous recrutons" transcription freelance monde entier'),
    ('fr', 'traduction anglais freelance monde entier postuler'),
    ('fr', 'sous-titrage freelance monde entier télétravail'),
    # Dutch — finds Dutch companies AND Dutch job boards
    ('nl', 'engelse transcriptie freelance wereldwijd solliciteren'),
    ('nl', 'data annotatie thuiswerk wereldwijd freelance solliciteren'),
    ('nl', '"wij zoeken" transcriptie freelance wereldwijd'),
    ('nl', 'ondertiteling freelance wereldwijd thuiswerk solliciteren'),
    ('nl', 'vertaling engels freelance wereldwijd thuiswerk'),
    # Swedish
    ('sv', 'engelsk transkribering distansarbete världen freelance'),
    ('sv', 'dataannotering distansjobb världen ansökan'),
    ('sv', '"vi söker" transkribering distansarbete världen'),
    ('sv', 'textning freelance världen distansarbete ansökan'),
    # Norwegian
    ('no', 'engelsk transkripsjon hjemmekontor verden freelance'),
    ('no', 'dataannotering fjernarbeid verden søknad'),
    ('no', '"vi søker" transkripsjon hjemmekontor verden'),
    # Finnish
    ('fi', 'englannin transkriptio etätyö maailmanlaajuinen freelance'),
    ('fi', 'data-annotointi kotityö maailmanlaajuinen hakemus'),
    ('fi', '"etsimme" transkriptio etätyö maailmanlaajuinen'),
    # Japanese
    ('ja', '英語 文字起こし リモートワーク 世界中 フリーランス 応募'),
    ('ja', 'データアノテーション 在宅勤務 世界中 フリーランス 応募'),
    ('ja', '採用 文字起こし リモート 世界中'),
    # Korean
    ('ko', '영어 전사 재택근무 전세계 프리랜서 지원'),
    ('ko', '데이터 어노테이션 재택근무 전세계 지원'),
    ('ko', '채용 전사 원격근무 전세계'),
    # Polish
    ('pl', 'transkrypcja angielski freelance cały świat praca zdalna'),
    ('pl', 'adnotacja danych praca zdalna cały świat freelance'),
    # Arabic
    ('ar', 'نسخ إنجليزي عن بعد عالمي مستقل تقديم'),
    ('ar', 'تعليق توضيحي بيانات عمل عن بعد عالمي'),
]

# ─── COUNTRY DETECTION ────────────────────────────────────────────────────────

COUNTRY_DOMAINS = {
    '.de': ('DE', 'Germany', 'de'),
    '.nl': ('NL', 'Netherlands', 'nl'),
    '.se': ('SE', 'Sweden', 'sv'),
    '.no': ('NO', 'Norway', 'no'),
    '.fi': ('FI', 'Finland', 'fi'),
    '.fr': ('FR', 'France', 'fr'),
    '.be': ('BE', 'Belgium', 'fr'),
    '.at': ('AT', 'Austria', 'de'),
    '.ch': ('CH', 'Switzerland', 'de'),
    '.pl': ('PL', 'Poland', 'pl'),
    '.cz': ('CZ', 'Czech Republic', 'cs'),
    '.jp': ('JP', 'Japan', 'ja'),
    '.kr': ('KR', 'South Korea', 'ko'),
    '.sa': ('SA', 'Saudi Arabia', 'ar'),
    '.ae': ('AE', 'UAE', 'ar'),
    '.lu': ('LU', 'Luxembourg', 'fr'),
    '.dk': ('DK', 'Denmark', 'da'),
    '.es': ('ES', 'Spain', 'es'),
    '.it': ('IT', 'Italy', 'it'),
    '.pt': ('PT', 'Portugal', 'pt'),
    '.uk': ('UK', 'United Kingdom', 'en'),
    '.ie': ('IE', 'Ireland', 'en'),
    '.ca': ('CA', 'Canada', 'en'),
    '.au': ('AU', 'Australia', 'en'),
    '.nz': ('NZ', 'New Zealand', 'en'),
    '.in': ('IN', 'India', 'en'),
    '.ng': ('NG', 'Nigeria', 'en'),
    '.za': ('ZA', 'South Africa', 'en'),
    '.ke': ('KE', 'Kenya', 'en'),
    '.gh': ('GH', 'Ghana', 'en'),
    '.br': ('BR', 'Brazil', 'pt'),
    '.mx': ('MX', 'Mexico', 'es'),
}


def detect_country_from_url(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    for tld, (code, name, lang) in COUNTRY_DOMAINS.items():
        if domain.endswith(tld):
            return code, name, lang
    return 'US', 'United States', 'en'


def is_job_board(url):
    job_board_signals = [
        'jobs.', 'job.', 'career', 'work.', 'employ',
        'vacancy', 'vacature', 'stellenangebote', 'emploi',
        'jobbsafari', 'stepstone', 'finn.no', 'jobindex',
        'duunitori', 'saramin', 'werkzoeken', 'cadremploi',
        'indeed', 'glassdoor', 'monster', 'linkedin',
        'arbeitsagentur', 'xing.com/jobs',
    ]
    url_lower = url.lower()
    return any(signal in url_lower for signal in job_board_signals)


def is_ats_page(url):
    ats_signals = [
        'greenhouse.io', 'lever.co', 'workable.com',
        'bamboohr.com', 'recruitee.com', 'breezy.hr',
        'freshteam.com', 'smartrecruiters.com',
        'jobvite.com', 'icims.com', 'taleo.net',
    ]
    return any(signal in url.lower() for signal in ats_signals)


def classify_source_type(url):
    if is_ats_page(url):
        return 'ats_page'
    if is_job_board(url):
        return 'job_board'
    if any(kw in url.lower() for kw in ['career', 'jobs', 'hiring', 'work-with-us', 'join']):
        return 'company_careers'
    return 'unknown'


# ─── HEADERS ──────────────────────────────────────────────────────────────────

LANG_HEADERS = {
    'de': 'de-DE,de;q=0.9,en;q=0.8',
    'fr': 'fr-FR,fr;q=0.9,en;q=0.8',
    'nl': 'nl-NL,nl;q=0.9,en;q=0.8',
    'sv': 'sv-SE,sv;q=0.9,en;q=0.8',
    'no': 'nb-NO,nb;q=0.9,en;q=0.8',
    'fi': 'fi-FI,fi;q=0.9,en;q=0.8',
    'ja': 'ja-JP,ja;q=0.9,en;q=0.8',
    'ko': 'ko-KR,ko;q=0.9,en;q=0.8',
    'pl': 'pl-PL,pl;q=0.9,en;q=0.8',
    'ar': 'ar-SA,ar;q=0.9,en;q=0.8',
    'en': 'en-US,en;q=0.9',
}


def get_headers(lang='en'):
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': LANG_HEADERS.get(lang, LANG_HEADERS['en']),
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'DNT': '1',
    }


def human_delay(min_sec=1.5, max_sec=4.0):
    time.sleep(random.uniform(min_sec, max_sec))


# ─── CLASSIFICATION HELPERS ───────────────────────────────────────────────────

def make_fingerprint(company_name, job_title, source='web'):
    title_lower = job_title.lower()
    if any(w in title_lower for w in ['transcri', 'caption', 'subtitl']):
        job_category = 'transcription'
    elif any(w in title_lower for w in ['annot', 'label', 'tag']):
        job_category = 'annotation'
    elif any(w in title_lower for w in ['translat', 'localiz']):
        job_category = 'translation'
    elif any(w in title_lower for w in ['voice', 'audio', 'speech', 'record']):
        job_category = 'voice'
    elif any(w in title_lower for w in ['moderat', 'trust', 'safety']):
        job_category = 'moderation'
    elif any(w in title_lower for w in ['rater', 'evaluat', 'assessor', 'analyst']):
        job_category = 'rating'
    elif any(w in title_lower for w in ['ai train', 'rlhf', 'prompt']):
        job_category = 'ai_training'
    else:
        job_category = job_title[:30].lower().strip()
    raw = f"{source}:{company_name}:{job_category}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()


def is_relevant(title, description=''):
    """
    Returns True only for genuine task-based remote work
    that a motivated person without a professional degree can do.
    """
    text = (title + ' ' + description).lower()
    title_lower = title.lower()

    # These title patterns are clearly task-based — accept immediately
    clear_accepts = [
        'transcri',           # transcription, transcriptionist, transcriber
        'annot',              # annotation, annotator
        'data label', 'data labeling', 'data labelling',
        'content moderat',    # content moderation
        'quality rater', 'search rater', 'search quality',
        'internet assessor', 'map analyst',
        'voice recording', 'voice actor', 'voice talent',
        'captioning', 'subtitl',
        'data collect',
        'ai training specialist',
        'ai trainer - advanced',  # language-specific trainer
        'data tagger', 'data labeler',
        'image annotation', 'video annotation', 'audio annotation',
        'text annotation', 'text labeling',
        'prompt engineer',    # not software engineering
        'llm evaluation', 'model evaluation', 'ai evaluation',
        'rlhf',
        # Non-English equivalents
        'transkription', 'transkribent',
        'transcriptie', 'annotatie',
        'transkribering', 'annotering',
        'transkripsjon',
        'transkriptio', 'annotointi',
        '文字起こし', 'アノテーション',
        '전사', '어노테이션',
    ]

    # These are professional roles requiring licenses/degrees — reject always
    hard_rejects = [
        'software engineer', 'engineer,', 'engineer -',
        'engineering manager', 'research engineer',
        'data scientist', 'machine learning',
        'data science manager', 'data analyst',
        'product manager', 'product designer',
        'solutions engineer', 'security engineer',
        'backend', 'frontend', 'fullstack', 'full stack',
        'devops', 'mlops', 'infrastructure',
        'ios', 'android', 'mobile engineer',
        'ceo', 'cto', 'cfo', 'vp ', 'vice president',
        'director', 'head of', 'chief ',
        'lawyer', 'attorney', 'legal',
        'accountant', 'finance advisor', 'financial',
        'medical doctor', 'physician', 'nurse', 'doctor',
        'psychologist', 'audiologist', 'clinician',
        'research scientist', 'scientist',
        'recruiter', 'recruitment partner', 'sourcer',
        'marketing manager', 'sales manager',
        'customer success manager',
        'mechanical engineer', 'industrial engineer',
        'computer scientist',
        'hr ', 'people experience',
        'fraud analyst',
        'deal desk', 'fp&a',
        'concierge',
        'html', 'css developer', 'java developer', 'javascript developer',
        'sql developer', 'mathematician', 'graphic design',
        'visual design', 'program manager', 'operations program',
        'project manager', 'operations associate',
        'trainer - hong kong', 'trainer - malaysia', 'trainer - taiwan',
        'trainer - vietnam', 'trainer - singapore', 'trainer - indonesia',
    ]

    # Hard reject first — fastest exit
    if any(r in title_lower for r in hard_rejects):
        return False

    # Clear accept — return immediately
    if any(a in text for a in clear_accepts):
        return True

    # Secondary check — broader task keywords
    # Only accept if BOTH a task keyword AND no professional indicator
    secondary_accepts = [
        'ai trainer', 'ai training',
        'translation', 'translator', 'localization',
        'proofreader', 'proofreading', 'copy editor',
        'data entry', 'data quality',
        'trust and safety',
        'content reviewer', 'content review',
        'remote evaluator',
    ]

    if any(a in text for a in secondary_accepts):
        return True

    return False


def detect_geo_tier(title, description):
    text = (title + ' ' + description).lower()

    # Q1: Physical presence? → Tier 5, hard skip always
    if any(kw in text for kw in [
        'on-site', 'onsite', 'in-office', 'in office',
        'must relocate', 'relocation required',
        'must report to office', 'in-person only',
        'notarized in person', 'vor ort', 'im büro',
    ]):
        return 5

    # Tier 1 — Worldwide, no restriction
    if any(kw in text for kw in [
        'worldwide', 'anywhere', 'all countries',
        'location independent', 'remote worldwide',
        'globally', 'weltweit', 'monde entier',
        'wereldwijd', 'världen', 'verden',
        'maailmanlaajuinen', '世界中', '전세계',
        'cały świat', 'todo el mundo',
    ]):
        return 1

    # Tier 2 — Africa / Kenya explicitly included
    if any(kw in text for kw in [
        'africa', 'kenya', 'nigeria', 'ghana',
        'south africa', 'developing countries',
        'global south', 'lmic', 'sub-saharan',
    ]):
        return 2

    # Tier 3 — Citizenship/legal flag but remote work
    # Physical ≠ Legal. NEVER conflate. Always show with flag.
    if any(kw in text for kw in [
        'must be us citizen', 'right to work',
        'work authorization', 'eligible to work in',
        'visa sponsorship not', 'eu resident',
        'uk resident', 'must have right to',
        'authorized to work',
    ]):
        return 3

    # Tier 4 — Region restricted, investigate
    if any(kw in text for kw in [
        'us only', 'eu only', 'uk only',
        'north america only', 'us residents only',
        'residents of', 'nur deutschland',
        'nur eu', 'seulement france',
    ]):
        return 4

    # Tier 0 — Unknown/not specified
    # No restriction stated = often no restriction enforced
    return 0


def detect_onboarding(description):
    text = description.lower()
    if any(kw in text for kw in [
        'zoom interview', 'skype interview', 'video interview',
        'phone interview', 'phone screen', 'schedule a call',
        'teams meeting', 'videovorstellung', 'entretien vidéo',
    ]):
        return 3
    if any(kw in text for kw in [
        'background check', 'ssn required', 'government id',
        'notarized', 'w-2', 'i-9', 'security clearance',
    ]):
        return 4
    if any(kw in text for kw in [
        'skill test', 'qualification test', 'assessment test',
        'take a test', 'pass a test', 'skills assessment',
        'auto-approved', 'start immediately', 'test bestehen',
        'passer un test',
    ]):
        return 1
    return 2


def detect_citizenship_flag(description):
    text = description.lower()
    flags = [
        'must be us citizen', 'us citizen only',
        'right to work in', 'work authorization',
        'eligible to work in', 'visa sponsorship not available',
        'eu resident required', 'authorized to work',
    ]
    for flag in flags:
        if flag in text:
            return True, flag
    return False, ''


def detect_posting_language(text):
    indicators = {
        'de': ['wir', 'sind', 'suchen', 'kenntnisse', 'erfahrung',
               'freiberuflich', 'stelle', 'bewerben', 'heimarbeit',
               'weltweit', 'übersetzung'],
        'fr': ['nous', 'cherchons', 'vous', 'notre', 'télétravail',
               'emploi', 'postuler', 'monde', 'partout', 'traduction'],
        'nl': ['wij', 'zoeken', 'werken', 'vanuit', 'thuis',
               'wereldwijd', 'solliciteren', 'vacature', 'vertaling'],
        'sv': ['vi', 'söker', 'arbeta', 'hemma', 'distans',
               'världen', 'ansökan', 'jobb', 'översättning'],
        'no': ['vi', 'søker', 'jobbe', 'hjemme', 'verden',
               'fjernarbeid', 'stilling', 'oversettelse'],
        'fi': ['etsimme', 'työ', 'kotona', 'etätyö', 'maailman',
               'hakea', 'tehtävä', 'käännös'],
        'ja': ['文字起こし', 'アノテーション', 'リモート', '在宅',
               '募集', '翻訳', '字幕', '応募'],
        'ko': ['전사', '어노테이션', '재택', '전세계',
               '모집', '번역', '지원', '자막'],
        'pl': ['transkrypcja', 'praca', 'zdalna', 'świat',
               'tłumaczenie', 'adnotacja', 'aplikuj'],
        'ar': ['نسخ', 'عمل', 'بعد', 'عالمي', 'ترجمة', 'تقديم'],
    }
    t = text.lower()
    scores = {lang: sum(1 for w in words if w in t)
              for lang, words in indicators.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else 'en'


def classify_job_type(title, description):
    text = (title + ' ' + description).lower()
    if any(k in text for k in [
        'transcript', 'transkript', 'transcripteur',
        'transkribering', 'transkripsjon', 'transkriptio',
        '文字起こし', '전사', 'transkrypcja',
    ]):
        return 'transcription'
    if any(k in text for k in [
        'translat', 'localiz', 'traducteur', 'übersetz',
        'vertaling', 'översättning', 'oversettelse',
        'käännös', '翻訳', '번역', 'tłumaczenie',
    ]):
        return 'translation'
    if any(k in text for k in [
        'annot', 'label', 'annotateur', 'annotering',
        'annotatie', 'annotointi', 'アノテーション',
        '어노테이션', 'adnotacja',
    ]):
        return 'annotation'
    if any(k in text for k in [
        'ai training', 'rlhf', 'llm', 'prompt eval',
        'model eval', 'ai eval', 'ki training',
    ]):
        return 'ai_training'
    if any(k in text for k in [
        'moderat', 'trust and safety', 'content review',
        'modération', 'moderatie',
    ]):
        return 'content_moderation'
    if any(k in text for k in [
        'voice', 'audio record', 'sprachaufnahme',
        'voice over', 'stemopname', '音声', '음성',
    ]):
        return 'voice'
    if any(k in text for k in [
        'caption', 'subtitle', 'untertitel', 'ondertitel',
        'textning', 'teksting', '字幕', '자막',
    ]):
        return 'qa'
    if any(k in text for k in [
        'quality rater', 'search eval', 'quality eval',
        'qualitätsbewertung',
    ]):
        return 'qa'
    return 'other'

def requires_english_work(title, description=''):
    """
    Returns True only if the work requires English speakers.
    Rejects jobs that require speakers of other specific languages.
    This is our core filter — we want jobs posted in any language
    but where the WORK itself is in English.
    """
    text = (title + ' ' + description).lower()

    # These indicate the work requires a non-English language — reject
    non_english_work = [
        'arabic fluency', 'arabic speaker', 'advanced arabic',
        'native arabic', 'arabic language',
        'dutch fluency', 'dutch speaker', 'advanced dutch',
        'native dutch', 'dutch language',
        'german fluency', 'german speaker', 'advanced german',
        'native german', 'deutschsprachig', 'muttersprachler',
        'french fluency', 'french speaker', 'advanced french',
        'native french', 'francophone',
        'japanese fluency', 'japanese speaker', 'advanced japanese',
        'native japanese',
        'korean fluency', 'korean speaker', 'advanced korean',
        'native korean',
        'mandarin fluency', 'mandarin speaker', 'advanced mandarin',
        'native mandarin', 'chinese fluency',
        'spanish fluency', 'spanish speaker', 'advanced spanish',
        'native spanish', 'hispanohablante',
        'portuguese fluency', 'portuguese speaker',
        'italian fluency', 'italian speaker',
        'urdu fluency', 'urdu speaker', 'advanced urdu',
        'hindi fluency', 'hindi speaker',
        'russian fluency', 'russian speaker',
        'turkish fluency', 'turkish speaker',
        'polish fluency', 'polish speaker',
        'swedish fluency', 'norwegian fluency', 'finnish fluency',
        'advanced swedish', 'advanced norwegian', 'advanced finnish',
    ]

    if any(sig in text for sig in non_english_work):
        return False

    return True


# ─── PHASE 1: SOURCE DISCOVERY ────────────────────────────────────────────────


# ─── PHASE 1: SOURCE DISCOVERY ────────────────────────────────────────────────

def discover_sources_via_duckduckgo(query, lang='en', max_results=15):
    """
    Searches DuckDuckGo in any language.
    Extracts careers URLs and job board URLs.
    Saves everything into DiscoveredSource table.
    Never hardcodes — finds sources dynamically.
    """
    sources_found = 0
    try:
        url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}&kl={lang}-{lang.upper()}"
        response = httpx.get(
            url,
            headers=get_headers(lang),
            timeout=25,
            follow_redirects=True,
        )
        human_delay()

        if response.status_code not in [200, 202]:
            return 0

        soup = BeautifulSoup(response.text, 'html.parser')

        # DuckDuckGo result links
        result_links = soup.find_all('a', class_='result__url')
        result_titles = soup.find_all('a', class_='result__a')

        for i, link in enumerate(result_links[:max_results]):
            from urllib.parse import unquote
            raw_href = link.get('href', '').strip()
            if 'uddg=' in raw_href:
                href = unquote(raw_href.split('uddg=')[1].split('&')[0])
            elif raw_href.startswith('http'):
                href = raw_href
            else:
                continue
            if not href or not href.startswith('http'):
                continue
            # If Greenhouse URL found, extract slug and crawl immediately
            if 'boards.greenhouse.io' in href:
                parts = href.replace('https://boards.greenhouse.io/', '').replace('https://www.boards.greenhouse.io/', '').split('/')
                if parts and parts[0] and len(parts[0]) > 1:
                    jobs = crawl_greenhouse_slug(parts[0])
                    if jobs > 0:
                        print(f"      💼 Greenhouse {parts[0]}: {jobs} jobs")
                continue

            title_text = result_titles[i].get_text(strip=True) if i < len(result_titles) else ''

            # Skip known irrelevant domains
            if any(skip in href.lower() for skip in [
                'facebook.com', 'twitter.com', 'youtube.com',
                'wikipedia.org', 'reddit.com/r/all',
                'amazon.com/product',
            ]):
                continue

            # Detect country from URL
            country_code, country_name, detected_lang = detect_country_from_url(href)
            source_type = classify_source_type(href)

            # Save to DiscoveredSource if not already known
            source, created = DiscoveredSource.objects.get_or_create(
                url=href[:1000],
                defaults={
                    'name': title_text[:255] or href[:255],
                    'source_type': source_type,
                    'country_code': country_code,
                    'country_name': country_name,
                    'posting_language': detected_lang,
                    'discovered_via': 'DuckDuckGo search',
                    'discovered_query': query[:500],
                    'trust_score': 60,
                }
            )

            if created:
                sources_found += 1

    except Exception as e:
        print(f"    DDG error [{lang}] '{query[:40]}...': {e}")

    return sources_found


def crawl_greenhouse_slug(slug):
    """
    Crawls a specific company on Greenhouse by slug.
    Called when DuckDuckGo finds a Greenhouse URL.
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    jobs_created = 0

    try:
        response = httpx.get(url, headers=get_headers('en'), timeout=15)
        human_delay(0.5, 1.5)

        if response.status_code != 200:
            return 0

        data = response.json()
        jobs_list = data.get('jobs', [])

        if not jobs_list:
            return 0

        relevant = [j for j in jobs_list
                    if is_relevant(j.get('title', ''),
                                   j.get('location', {}).get('name', ''))
                    and requires_english_work(j.get('title', ''),
                                              j.get('location', {}).get('name', ''))]
        if not relevant:
            return 0

        company_name = relevant[0].get('company_name', slug.title())
        careers_url = f"https://boards.greenhouse.io/{slug}"

        company, created = Company.objects.get_or_create(
            website=careers_url,
            defaults={
                'name': company_name,
                'careers_url': careers_url,
                'discovered_via': 'Greenhouse via DuckDuckGo',
                'trust_score': 75,
                'last_checked': timezone.now(),
                'last_active': timezone.now(),
            }
        )

        if created:
            print(f"    ✅ New company: {company_name}")

        for job_data in relevant:
            title = job_data.get('title', '')
            location = job_data.get('location', {}).get('name', '')
            job_url = job_data.get('absolute_url', '')

            fingerprint = make_fingerprint(company_name, title, 'greenhouse')
            if Job.objects.filter(fingerprint=fingerprint).exists():
                continue

            # Use Claude API classifier if available, fall back to keywords
            classification = None
            try:
                from core.crawlers.classifier import classify_job
                classification = classify_job(
                    title=title,
                    description=location,
                    company_name=company_name,
                    source_url=job_url,
                )
            except Exception:
                pass

            if classification:
                # AI classification
                if not classification.get('is_relevant', True):
                    continue
                if classification.get('physical_required', False):
                    continue

                geo_tier = classification.get('geo_tier', 0)
                if geo_tier == 5:
                    continue

                Job.objects.create(
                    company=company,
                    title=title,
                    description=location,
                    apply_url=job_url,
                    posting_language=classification.get('posting_language', 'en'),
                    work_language=classification.get('work_language', 'en'),
                    job_type=classification.get('job_type', 'other'),
                    vacancy_state='active',
                    geo_tier=geo_tier,
                    onboarding_level=classification.get('onboarding_level', 2),
                    citizenship_flag=classification.get('citizenship_flag', False),
                    citizenship_note=classification.get('citizenship_note', ''),
                    physical_required=False,
                    fingerprint=fingerprint,
                    is_new=True,
                    last_confirmed=timezone.now(),
                )
                jobs_created += 1

            else:
                # Fallback to keyword matching if API unavailable
                geo_tier = detect_geo_tier(title, location)
                if geo_tier == 5:
                    continue

                citizenship_flag, citizenship_note = detect_citizenship_flag(location)
                posting_lang = detect_posting_language(title + ' ' + location)

                Job.objects.create(
                    company=company,
                    title=title,
                    description=location,
                    apply_url=job_url,
                    posting_language=posting_lang,
                    work_language='en',
                    job_type=classify_job_type(title, location),
                    vacancy_state='active',
                    geo_tier=geo_tier,
                    onboarding_level=detect_onboarding(location),
                    citizenship_flag=citizenship_flag,
                    citizenship_note=citizenship_note,
                    physical_required=False,
                    fingerprint=fingerprint,
                    is_new=True,
                    last_confirmed=timezone.now(),
                )
                jobs_created += 1

        CrawlLog.objects.create(
            url=url,
            company=company,
            status='success',
            http_code=200,
            protection_level=1,
            jobs_found=jobs_created,
        )

    except Exception as e:
        pass

    return jobs_created


def discover_via_greenhouse_api(keyword):
    """
    Finds Greenhouse company slugs via DuckDuckGo,
    then crawls each slug via the per-company API.
    """
    from urllib.parse import unquote
    total_jobs = 0

    try:
        query = f"site:boards.greenhouse.io {keyword} remote"
        url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        response = httpx.get(url, headers=get_headers('en'), timeout=20, follow_redirects=True)
        human_delay()

        if response.status_code not in [200, 202]:
            return 0

        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', class_='result__url')

        slugs_found = set()
        for link in links[:15]:
            raw = link.get('href', '')
            actual = unquote(raw.split('uddg=')[1].split('&')[0]) if 'uddg=' in raw else raw
            if 'boards.greenhouse.io' in actual:
                parts = actual.replace('https://boards.greenhouse.io/', '').replace('https://www.boards.greenhouse.io/', '').split('/')
                if parts and parts[0] and len(parts[0]) > 1:
                    slugs_found.add(parts[0])

        for slug in slugs_found:
            jobs = crawl_greenhouse_slug(slug)
            total_jobs += jobs

    except Exception as e:
        print(f"    Greenhouse discovery error '{keyword}': {e}")

    return total_jobs


def discover_via_lever_api(keyword):
    """
    Finds Lever job pages via DuckDuckGo search.
    Lever has no global keyword API so we discover
    company slugs via search then call per-company endpoint.
    """
    from urllib.parse import unquote
    total_jobs = 0

    try:
        query = f"site:jobs.lever.co {keyword} remote"
        url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        response = httpx.get(url, headers=get_headers('en'), timeout=20, follow_redirects=True)
        human_delay()

        if response.status_code not in [200, 202]:
            return 0

        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', class_='result__url')

        slugs_found = set()
        for link in links[:15]:
            raw = link.get('href', '')
            actual = unquote(raw.split('uddg=')[1].split('&')[0]) if 'uddg=' in raw else raw
            if 'jobs.lever.co' in actual:
                parts = actual.replace('https://jobs.lever.co/', '').split('/')
                if parts and parts[0] and len(parts[0]) > 1:
                    slugs_found.add(parts[0])

        for slug in slugs_found:
            lever_url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            r2 = httpx.get(lever_url, headers=get_headers('en'), timeout=15)
            human_delay(0.5, 1.5)

            if r2.status_code != 200:
                continue

            jobs_list = r2.json()
            if not isinstance(jobs_list, list):
                continue

            company_name = slug.replace('-', ' ').title()
            company, created = Company.objects.get_or_create(
                website=f"https://jobs.lever.co/{slug}",
                defaults={
                    'name': company_name,
                    'careers_url': f"https://jobs.lever.co/{slug}",
                    'discovered_via': f'Lever via DuckDuckGo: {keyword}',
                    'trust_score': 70,
                    'last_checked': timezone.now(),
                }
            )
            if created:
                print(f"    ✅ New Lever company: {company_name}")

            for job_data in jobs_list:
                title = job_data.get('text', '')
                categories = job_data.get('categories', {})
                location = categories.get('location', '')
                commitment = categories.get('commitment', '')
                job_url = job_data.get('hostedUrl', '')
                full_text = f"{title} {location} {commitment}"

                if not is_relevant(title, full_text):
                    continue

                geo_tier = detect_geo_tier(title, full_text)
                if geo_tier == 5:
                    continue

                fingerprint = make_fingerprint(company_name, title, 'lever')
                if Job.objects.filter(fingerprint=fingerprint).exists():
                    continue

                citizenship_flag, citizenship_note = detect_citizenship_flag(full_text)

                Job.objects.create(
                    company=company,
                    title=title,
                    description=full_text,
                    apply_url=job_url,
                    posting_language=detect_posting_language(full_text),
                    work_language='en',
                    job_type=classify_job_type(title, full_text),
                    vacancy_state='active',
                    geo_tier=geo_tier,
                    onboarding_level=detect_onboarding(full_text),
                    citizenship_flag=citizenship_flag,
                    citizenship_note=citizenship_note,
                    physical_required=False,
                    fingerprint=fingerprint,
                    is_new=True,
                    last_confirmed=timezone.now(),
                )
                total_jobs += 1

    except Exception as e:
        print(f"    Lever discovery error '{keyword}': {e}")

    return total_jobs


def discover_via_crtsh(term):
    """
    Monitors SSL certificate logs for new domains.
    Saves promising ones to DiscoveredSource.
    Strict validation — no bad URLs.
    """
    import re
    sources_found = 0
    try:
        url = f"https://crt.sh/?q=%25{term}%25&output=json"
        response = httpx.get(
            url,
            headers=get_headers('en'),
            timeout=40,
            follow_redirects=True,
        )
        human_delay(2, 5)

        if response.status_code == 200:
            certs = response.json()
            seen = set()

            for cert in certs[:50]:
                domain = cert.get('name_value', '').strip()

                # Clean multiline cert entries
                domain = domain.split('\n')[0].strip()

                # Strict validation
                if not domain:
                    continue
                if '*' in domain:
                    continue
                if ' ' in domain:
                    continue
                if '.' not in domain:
                    continue
                if len(domain) > 100:
                    continue
                # Must look like a real domain
                if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', domain):
                    continue

                clean = domain.lower().replace('www.', '')
                if clean in seen:
                    continue
                seen.add(clean)

                full_url = f"https://{clean}"
                country_code, country_name, lang = detect_country_from_url(full_url)

                source, created = DiscoveredSource.objects.get_or_create(
                    url=full_url,
                    defaults={
                        'name': clean,
                        'source_type': 'unknown',
                        'country_code': country_code,
                        'country_name': country_name,
                        'posting_language': lang,
                        'discovered_via': f'crt.sh domain scan: {term}',
                        'trust_score': 40,
                        'crawl_frequency_hours': 72,
                    }
                )
                if created:
                    sources_found += 1
                    print(f"    🆕 New domain: {clean} [{country_code}]")

    except Exception as e:
        print(f"    crt.sh timeout for '{term}' — skipping")

    return sources_found


# ─── PHASE 2: CRAWL DISCOVERED SOURCES ───────────────────────────────────────

def crawl_source(source):
    """
    Visits a discovered source URL and extracts relevant jobs.
    Works on any URL — company careers pages, job boards, ATS pages.
    Uses country-matched language headers.
    """
    jobs_created = 0
    lang = source.posting_language or 'en'

    try:
        response = httpx.get(
            source.url,
            headers=get_headers(lang),
            timeout=20,
            follow_redirects=True,
        )
        human_delay()

        if response.status_code != 200:
            source.consecutive_failures += 1
            source.save()
            CrawlLog.objects.create(
                url=source.url,
                status='error',
                http_code=response.status_code,
                protection_level=source.protection_level,
                jobs_found=0,
            )
            return 0

        soup = BeautifulSoup(response.text, 'html.parser')
        full_text = soup.get_text(separator=' ', strip=True)

        # Detect actual posting language from page content
        detected_lang = detect_posting_language(full_text)
        if detected_lang != 'en' and source.posting_language == 'en':
            source.posting_language = detected_lang
            source.save()

        # Detect vacancy state
        ghost_signals = [
            'no positions available', 'currently fully staffed',
            'no openings at this time', 'not currently hiring',
            'keine stellen verfügbar', 'pas de postes disponibles',
            'geen vacatures', 'inga lediga tjänster',
            'talent pool', 'future opportunities',
            'notify you when', 'we will be in touch',
        ]
        active_signals = [
            'apply now', 'apply today', 'submit application',
            'view openings', 'open positions', 'current openings',
            'jetzt bewerben', 'postuler maintenant', 'solliciteer nu',
            'sök nu', 'søk nå', 'hae nyt',
        ]

        page_lower = full_text.lower()
        is_ghost = any(sig in page_lower for sig in ghost_signals)
        is_active = any(sig in page_lower for sig in active_signals)

        vacancy_state = 'ghost_pipeline' if (is_ghost and not is_active) else \
                        'active' if is_active else 'unknown'

        # Extract job listings from page
        job_elements = (
            soup.find_all('article') or
            soup.find_all(class_=lambda c: c and any(
                kw in str(c).lower() for kw in ['job', 'position', 'vacancy', 'opening', 'rolle', 'stelle']
            )) or
            soup.find_all('li', class_=lambda c: c and any(
                kw in str(c).lower() for kw in ['job', 'result', 'vacancy', 'position']
            )) or
            soup.find_all('div', class_=lambda c: c and any(
                kw in str(c).lower() for kw in ['job-item', 'job_item', 'vacancy', 'position-item']
            ))
        )

        # Get or create company for this source
        company_name = source.name or urlparse(source.url).netloc
        country_code, country_name, _ = detect_country_from_url(source.url)

        company, _ = Company.objects.get_or_create(
            website=source.url[:500],
            defaults={
                'name': company_name,
                'careers_url': source.url,
                'discovered_via': source.discovered_via,
                'country_code': source.country_code or country_code,
                'country_name': source.country_name or country_name,
                'trust_score': source.trust_score,
                'last_checked': timezone.now(),
                'last_active': timezone.now(),
            }
        )

        for element in job_elements[:30]:
            # Extract title
            title_el = (
                element.find('h1') or element.find('h2') or
                element.find('h3') or element.find('h4') or
                element.find(class_=lambda c: c and 'title' in str(c).lower())
            )
            if not title_el:
                continue

            title = title_el.get_text(strip=True)[:500]
            if not title or len(title) < 3:
                continue

            description = element.get_text(separator=' ', strip=True)[:1000]

            if not is_relevant(title, description):
                continue

            # Find apply link
            link = element.find('a', href=True)
            job_url = ''
            if link:
                href = link['href']
                if href.startswith('http'):
                    job_url = href
                elif href.startswith('/'):
                    parsed = urlparse(source.url)
                    job_url = f"{parsed.scheme}://{parsed.netloc}{href}"

            geo_tier = detect_geo_tier(title, description)
            if geo_tier == 5:
                continue

            posting_lang = detect_posting_language(title + ' ' + description)
            citizenship_flag, citizenship_note = detect_citizenship_flag(description)
            fingerprint = make_fingerprint(company_name, title, source.source_type)

            if Job.objects.filter(fingerprint=fingerprint).exists():
                continue

            Job.objects.create(
                company=company,
                title=title,
                description=description,
                apply_url=job_url,
                posting_language=posting_lang,
                work_language='en',
                job_type=classify_job_type(title, description),
                vacancy_state=vacancy_state,
                geo_tier=geo_tier,
                onboarding_level=detect_onboarding(description),
                citizenship_flag=citizenship_flag,
                citizenship_note=citizenship_note,
                physical_required=(geo_tier == 5),
                fingerprint=fingerprint,
                is_new=True,
                last_confirmed=timezone.now(),
            )
            jobs_created += 1
            print(f"      💼 [{posting_lang}→en] {title[:65]}")

        # Update source stats
        source.last_crawled = timezone.now()
        source.consecutive_failures = 0
        source.jobs_found_total += jobs_created
        if jobs_created > 0:
            source.last_job_found = timezone.now()
        source.save()

        CrawlLog.objects.create(
            url=source.url,
            company=company,
            status='success',
            http_code=200,
            protection_level=source.protection_level,
            jobs_found=jobs_created,
        )

    except Exception as e:
        source.consecutive_failures += 1
        source.save()
        CrawlLog.objects.create(
            url=source.url,
            status='error',
            jobs_found=0,
            error_message=str(e)[:500],
        )

    return jobs_created


# ─── PHASE 3: STATE TRANSITION MONITORING ────────────────────────────────────

def check_state_transitions():
    """
    Re-checks known company careers pages for state changes.
    Ghost pipeline → Active = urgent alert.
    Closed → Active = high priority alert.
    """
    print("\n🔄 Checking state transitions on known companies...")
    transitions = 0

    companies = Company.objects.filter(
        status='active'
    ).exclude(careers_url='').order_by('last_checked')[:50]

    for company in companies:
        try:
            response = httpx.get(
                company.careers_url,
                headers=get_headers('en'),
                timeout=15,
                follow_redirects=True,
            )
            human_delay(1, 2)

            if response.status_code != 200:
                continue

            text = response.text.lower()

            ghost_signals = [
                'no positions available', 'currently fully staffed',
                'no openings at this time', 'not currently hiring',
                'talent pool', 'future opportunities', 'notify you when',
                'keine stellen', 'pas de postes', 'geen vacatures',
            ]
            active_signals = [
                'apply now', 'apply today', 'open positions',
                'current openings', 'jetzt bewerben',
                'postuler maintenant', 'solliciteer nu',
            ]

            is_ghost = any(s in text for s in ghost_signals)
            is_active = any(s in text for s in active_signals)

            new_state = 'ghost_pipeline' if (is_ghost and not is_active) else \
                        'active' if is_active else 'unknown'

            last_job = company.jobs.order_by('-first_seen').first()
            previous_state = last_job.vacancy_state if last_job else 'unknown'

            if new_state != previous_state and new_state != 'unknown':
                JobStateHistory.objects.create(
                    company=company,
                    previous_state=previous_state,
                    new_state=new_state,
                    notes='Auto-detected by state transition monitor',
                )
                transitions += 1

                priority = '🔥 URGENT' if new_state == 'active' else '📋 INFO'
                print(f"  {priority}: {company.name} — {previous_state} → {new_state}")

            company.last_checked = timezone.now()
            # Update crawl frequency based on current state
            priority_hours = get_crawl_priority(company)
            company.save()

            # Update DiscoveredSource crawl frequency if exists
            from core.models import DiscoveredSource
            DiscoveredSource.objects.filter(
                url__icontains=company.careers_url or company.website or ''
            ).update(crawl_frequency_hours=priority_hours)

        except Exception:
            pass

    print(f"  {transitions} transitions detected")
    return transitions


# ─── MAIN ORCHESTRATOR ────────────────────────────────────────────────────────

def run_full_discovery():
    """
    Main entry point.

    Phase 1: Discover sources dynamically via search + APIs + domain scan
    Phase 2: Crawl all discovered sources and extract jobs
    Phase 3: Monitor known sources for state transitions
    """
    print("\n🌍 OmniJob Intelligence Engine — Full Discovery\n")
    total_jobs = 0
    total_sources = 0

    # ── PHASE 1: DISCOVER SOURCES ──────────────────────────────────────────

    print("=" * 60)
    print("PHASE 1: Discovering sources dynamically")
    print("=" * 60)

    # ATS keyword discovery — finds individual job pages
    print("\n  📡 Scanning Greenhouse ATS by keyword...")
    ats_keywords = [
        'transcription', 'annotation', 'data labeling',
        'content moderation', 'voice recording', 'quality rater',
        'ai training', 'translation', 'subtitling',
        'transkription', 'transcriptie', 'transkribering',
        'transkripsjon', '文字起こし', '전사',
    ]
    for keyword in ats_keywords:
        found = discover_via_greenhouse_api(keyword)
        if found:
            print(f"    Greenhouse '{keyword}': {found} new sources")
        total_sources += found
        human_delay()

    print("\n  📡 Scanning Lever ATS by keyword...")
    for keyword in ats_keywords[:8]:
        found = discover_via_lever_api(keyword)
        if found:
            print(f"    Lever '{keyword}': {found} new sources")
        total_sources += found
        human_delay()

    # DuckDuckGo multilingual search discovery
    print("\n  🔍 DuckDuckGo multilingual search discovery...")
    for lang, query in SEARCH_QUERIES:
        print(f"    [{lang}] {query[:55]}...")
        found = discover_sources_via_duckduckgo(query, lang)
        if found:
            print(f"      → {found} new sources discovered")
        total_sources += found
        human_delay()

    # crt.sh domain discovery
    print("\n  🔒 SSL certificate domain discovery...")
    crt_terms = ['transcri', 'annotate', 'datalabel', 'freelanc', 'remotejob']
    for term in crt_terms:
        found = discover_via_crtsh(term)
        total_sources += found
        human_delay(2, 4)

    print(f"\n  ✅ Phase 1 complete — {total_sources} new sources discovered")
    print(f"     Total sources in database: {DiscoveredSource.objects.count()}")

    # ── PHASE 2: CRAWL ALL SOURCES ─────────────────────────────────────────

    print("\n" + "=" * 60)
    print("PHASE 2: Crawling discovered sources for jobs")
    print("=" * 60)

    # Prioritize sources never crawled, then least recently crawled
    sources_to_crawl = DiscoveredSource.objects.filter(
        is_active=True,
        consecutive_failures__lt=5,
    ).order_by(
        'last_crawled',  # Never crawled first (NULL sorts first)
        'consecutive_failures',
    )[:200]

    print(f"\n  Crawling {sources_to_crawl.count()} sources...")

    for i, source in enumerate(sources_to_crawl):
        lang = source.posting_language or 'en'
        country = source.country_name or source.country_code or 'Unknown'
        print(f"\n  [{i+1}] {source.name[:50]} [{country}] ({source.source_type})")

        jobs = crawl_source(source)
        if jobs > 0:
            total_jobs += jobs

        # Progress every 20 sources
        if (i + 1) % 20 == 0:
            print(f"\n  📊 Progress: {i+1} sources crawled, {total_jobs} jobs found so far\n")

    print(f"\n  ✅ Phase 2 complete — {total_jobs} new jobs found")

    # ── PHASE 3: STATE TRANSITION MONITORING ───────────────────────────────

    print("\n" + "=" * 60)
    print("PHASE 3: State transition monitoring")
    print("=" * 60)
    transitions = check_state_transitions()

    # ── SUMMARY ────────────────────────────────────────────────────────────

    print("\n" + "=" * 60)
    print("DISCOVERY COMPLETE")
    print("=" * 60)
    print(f"  New sources discovered:  {total_sources}")
    print(f"  Total sources known:     {DiscoveredSource.objects.count()}")
    print(f"  New jobs found:          {total_jobs}")
    print(f"  State transitions:       {transitions}")
    print(f"  Companies in database:   {Company.objects.count()}")
    print(f"  Total jobs in database:  {Job.objects.count()}")

    return total_jobs


def get_crawl_priority(company):
    """
    Determines how frequently a company should be re-crawled.
    Returns frequency in hours.
    
    Priority logic:
    - Recently transitioned ghost→active = every 1 hour (highest)
    - Has active jobs = every 6 hours
    - Has ghost pipeline jobs = every 24 hours  
    - No jobs found = every 72 hours
    - Consistently failing = every 168 hours (weekly)
    """
    from core.models import JobStateHistory
    from django.utils import timezone
    from datetime import timedelta

    # Check for recent ghost→active transition (last 24 hours)
    recent_transition = JobStateHistory.objects.filter(
        company=company,
        new_state='active',
        previous_state='ghost_pipeline',
        changed_at__gte=timezone.now() - timedelta(hours=24)
    ).exists()

    if recent_transition:
        return 1  # Check every hour — window just opened

    # Count active vs ghost jobs
    active_count = company.jobs.filter(vacancy_state='active').count()
    ghost_count = company.jobs.filter(vacancy_state='ghost_pipeline').count()
    total_failures = company.crawl_logs.filter(status='error').count()

    if total_failures > 10:
        return 168  # Weekly — consistently failing

    if active_count > 0:
        return 6  # Active jobs — check frequently

    if ghost_count > 0:
        return 24  # Ghost pipeline — check daily

    return 72  # No jobs — check every 3 days