import httpx
import logging
import time
import random
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
from django.utils import timezone
from core.models import Company, Job, CrawlLog, DiscoveredSource

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

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
    'da': 'da-DK,da;q=0.9,en;q=0.8',
    'ar': 'ar-SA,ar;q=0.9,en;q=0.8',
}

# Search queries in many languages
# Each finds companies posting task-based English work
SEARCH_QUERIES = [
    # English
    ('en', 'hiring english transcribers remote worldwide freelance'),
    ('en', 'hiring english data annotators remote worldwide'),
    ('en', 'english content moderators remote freelance worldwide'),
    ('en', 'english voice recording remote freelance worldwide'),
    ('en', 'english quality raters remote freelance worldwide'),
    ('en', 'english search evaluators remote freelance worldwide'),
    ('en', 'english AI trainers remote freelance worldwide'),
    ('en', 'english subtitle captioners remote freelance worldwide'),
    ('en', 'remote english transcription jobs freelance apply'),
    ('en', 'remote english annotation jobs freelance apply'),
    # German — companies in Germany/Austria/Switzerland hiring English speakers
    ('de', 'Englisch Transkription Stelle freiberuflich weltweit bewerben'),
    ('de', 'Englisch Annotation Stelle freiberuflich weltweit bewerben'),
    ('de', 'Englisch Sprachaufnahme freiberuflich weltweit bewerben'),
    ('de', 'Englisch Untertitelung freiberuflich weltweit bewerben'),
    ('de', 'Englisch Qualitätsbewertung freiberuflich weltweit bewerben'),
    ('de', 'English speakers annotation job remote worldwide apply'),
    ('de', 'Englisch KI Training Daten freiberuflich weltweit'),
    # French
    ('fr', 'transcription anglais freelance monde entier postuler'),
    ('fr', 'annotation données anglais télétravail monde entier'),
    ('fr', 'modération contenu anglais freelance monde entier'),
    ('fr', 'évaluation IA anglais freelance monde entier postuler'),
    ('fr', 'enregistrement vocal anglais freelance monde entier'),
    # Dutch — Netherlands, Belgium
    ('nl', 'engelse transcriptie freelance wereldwijd solliciteren'),
    ('nl', 'engelse data annotatie thuiswerk wereldwijd solliciteren'),
    ('nl', 'engelse ondertiteling freelance wereldwijd solliciteren'),
    ('nl', 'engelse contentbeoordeling freelance wereldwijd'),
    # Swedish
    ('sv', 'engelsk transkribering distansarbete världen freelance ansökan'),
    ('sv', 'engelsk dataannotering distansjobb världen ansökan'),
    ('sv', 'engelsk röstinspelning distansarbete världen ansökan'),
    # Norwegian
    ('no', 'engelsk transkripsjon hjemmekontor verden freelance søknad'),
    ('no', 'engelsk dataannotering fjernarbeid verden søknad'),
    # Finnish
    ('fi', 'englannin transkriptio etätyö maailmanlaajuinen freelance hakemus'),
    ('fi', 'englannin data-annotointi kotityö maailmanlaajuinen hakemus'),
    # Danish — missing before, now added
    ('da', 'engelsk transskription freelance verdensomspændende ansøg'),
    ('da', 'engelsk dataannotering hjemmearbejde verdensomspændende'),
    ('da', 'engelsk indholdsmoderator freelance verdensomspændende'),
    # Japanese — many Japanese companies need English annotators
    ('ja', '英語 文字起こし リモートワーク 世界中 フリーランス 応募'),
    ('ja', '英語 アノテーション 在宅勤務 世界中 フリーランス 応募'),
    ('ja', '英語 音声録音 在宅 フリーランス 応募'),
    ('ja', '英語ネイティブ AIトレーニング リモート 応募'),
    # Korean
    ('ko', '영어 전사 재택근무 전세계 프리랜서 지원'),
    ('ko', '영어 어노테이션 재택근무 전세계 지원'),
    ('ko', '영어 원어민 AI 훈련 원격 지원'),
    # Polish
    ('pl', 'transkrypcja angielski freelance cały świat praca zdalna aplikuj'),
    ('pl', 'adnotacja angielski praca zdalna cały świat aplikuj'),
    # Italian
    ('it', 'trascrizione inglese freelance tutto il mondo candidati'),
    ('it', 'annotazione dati inglese telelavoro tutto il mondo'),
    # Spanish
    ('es', 'transcripción inglés freelance todo el mundo aplicar'),
    ('es', 'anotación datos inglés teletrabajo todo el mundo'),
    # Portuguese
    ('pt', 'transcrição inglês freelance mundo todo candidatar'),
    ('pt', 'anotação dados inglês teletrabalho mundo todo'),
    # Chinese
    ('zh', '英语 转录 远程 全球 自由职业 申请'),
    ('zh', '英语 数据标注 远程 全球 申请'),
    # Arabic
    ('ar', 'نسخ إنجليزي عن بعد عالمي مستقل تقديم'),
    ('ar', 'تعليق بيانات إنجليزي عمل عن بعد عالمي تقديم'),
    # Missing categories — surveys, research, testing
    ('en', 'paid online surveys english remote worldwide apply'),
    ('en', 'research participant english remote paid study'),
    ('en', 'user testing remote english paid worldwide'),
    ('en', 'beta testing remote english paid worldwide'),
    ('en', 'english tutor online remote worldwide apply'),
    ('en', 'proofreading remote english freelance worldwide'),
    ('en', 'copy editing remote english freelance worldwide'),
    ('en', 'social media evaluator remote english worldwide'),
    ('en', 'online focus group english remote paid'),
    ('en', 'mystery shopping remote english worldwide'),
    ('en', 'chat support english remote freelance worldwide'),
    ('en', 'english language evaluator remote worldwide'),
    ('de', 'Online Umfrage bezahlt Englisch weltweit bewerben'),
    ('de', 'Nutzertest Englisch freiberuflich weltweit bewerben'),
    ('fr', 'sondage en ligne anglais payé monde entier postuler'),
    ('fr', 'test utilisateur anglais freelance monde entier'),
    ('ja', '英語 オンライン調査 在宅 報酬 応募'),
    ('ko', '영어 온라인 설문 재택 보수 지원'),
    ('zh', '英语 在线调查 远程 付费 申请'),
]

SKIP_DOMAINS = [
    'facebook.com', 'twitter.com', 'youtube.com', 'instagram.com',
    'linkedin.com', 'wikipedia.org', 'reddit.com', 'tiktok.com',
    'amazon.com', 'ebay.com', 'etsy.com', 'pinterest.com',
    'quora.com', 'medium.com', 'wordpress.com', 'blogspot.com',
    # Freelancer marketplaces — people post skills, not companies posting jobs
    'upwork.com', 'freelancer.com', 'fiverr.com', 'peopleperhour.com',
    'guru.com', 'toptal.com', 'workhoppers.com', 'bark.com',
    'tasker.com', 'airtasker.com', 'servicescape.com',
    'freelancer.nl', 'werkspot.nl', 'twago.com',
    # Job aggregators that just list other sites
    'indeed.com', 'glassdoor.com', 'ziprecruiter.com',
    'monster.com', 'careerbuilder.com', 'simplyhired.com',
    'jooble.org', 'jobrapido.com', 'neuvoo.com',
    # Article/blog sites — not actual job postings
    'flexjobs.com', 'remote.co', 'remoteok.com',
    'weworkremotely.com', 'workingnomads.com', 'justremote.co',
    'remotehub.com', 'virtualvocations.com',
    'mostaql.com',      # Arabic freelancer marketplace
    'genaijobs.co',     # job aggregator
    'appendata.com',    # Appen data portal, not jobs
    'mercor.io',        # AI hiring platform, not direct employer
    # Blog and review sites masquerading as job boards
    'chalized.com',
    'abacityblog.com',
    'harowaka.com',
    '求人ボックス.com',
    'contentwriter.pl',
    'topcontent.com',
    'workersonboard.com',
    'dreamhomebasedwork.com',
    'rat-race-rebellion.com',
    'theworkathomewoman.com',
    'moneypantry.com',
    'thecrazycouponer.com',
    'makealivingwriting.com',
    'thepennymatters.com',
    'workathomenoscams.com',
    'smartmoneymamas.com',
    'singlemamedesperate.com',
    'bayt.com',
    'wuzzuf.net', 
    'forasna.com',
    'tanqeeb.com',
    'akhtaboot.com',
    'mihnati.com',
    'naukrigulf.com',
    'gulftalent.com',
    'saudijobs24.com',
    'egyjob.net',
    'alchamel.net',
    'payoneer.com',
    'duction.com',
]


def search_web(query, lang='en', max_results=8):
    """
    Searches the web using multiple engines with rotation.
    Falls back to next engine if one is blocked.
    """
    urls = search_duckduckgo(query, lang, max_results)
    if urls:
        return urls

    # DuckDuckGo blocked — try Bing
    urls = search_bing(query, lang, max_results)
    if urls:
        return urls

    return []


def get_proxy():
    import os
    username = os.getenv('DECODO_USERNAME')
    password = os.getenv('DECODO_PASSWORD')
    if not username or not password:
        return None
    port = random.randint(10001, 10200)
    proxy_url = f'http://{username}:{password}@dc.decodo.com:{port}'
    return {'http://': proxy_url, 'https://': proxy_url}


def search_duckduckgo(query, lang='en', max_results=8, region='wt-wt'):
    """Searches DuckDuckGo with country rotation — finds different results per region."""
    urls = []
    try:
        accept_lang = LANG_HEADERS.get(lang, 'en-US,en;q=0.9')
        headers = {**HEADERS, 'Accept-Language': accept_lang}
        proxy = get_proxy()

        r = httpx.get(
            f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}&kl={region}",
            headers=headers,
            proxy=proxy.get('https://') if proxy else None,
            timeout=25,
            follow_redirects=True,
        )
        time.sleep(random.uniform(2, 4))  # Longer delay — avoid rate limiting

        if r.status_code not in [200, 202]:
            return urls

        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', class_='result__url')

        if not links:
            return urls  # Blocked — return empty

        for link in links[:max_results]:
            raw = link.get('href', '')
            if 'uddg=' in raw:
                url = unquote(raw.split('uddg=')[1].split('&')[0])
            elif raw.startswith('http'):
                url = raw
            else:
                continue

            if not url.startswith('http'):
                continue

            domain = urlparse(url).netloc.lower()
            if any(skip in domain for skip in SKIP_DOMAINS):
                continue

            urls.append(url)

    except Exception as e:
        logger.error(f'DDG error: {e}')

    return urls


def search_bing(query, lang='en', max_results=8):
    """
    Searches Bing as backup when DuckDuckGo is blocked.
    Uses different User-Agent to avoid same block pattern.
    """
    urls = []
    try:
        accept_lang = LANG_HEADERS.get(lang, 'en-US,en;q=0.9')
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': accept_lang,
        }

        r = httpx.get(
            f"https://www.bing.com/search?q={query.replace(' ', '+')}&count=10",
            headers=headers,
            timeout=20,
            follow_redirects=True,
        )
        time.sleep(random.uniform(5, 10))

        if r.status_code != 200:
            return urls

        soup = BeautifulSoup(r.text, 'html.parser')

        # Bing result links are in <li class="b_algo"> elements
        results = soup.find_all('li', class_='b_algo')
        for result in results[:max_results]:
            link = result.find('a', href=True)
            if not link:
                continue
            url = link['href']
            if not url.startswith('http'):
                continue
            domain = urlparse(url).netloc.lower()
            if any(skip in domain for skip in SKIP_DOMAINS):
                continue
            urls.append(url)

    except Exception as e:
        logger.error(f'Bing error: {e}')

    return urls

def extract_jobs_with_keywords(url, soup, page_text, lang='en'):
    """
    FREE replacement for Claude — uses keyword matching and HTML parsing.
    No API calls, no cost. Works in any language.
    """
    from urllib.parse import urlparse

    jobs = []
    domain = urlparse(url).netloc
    page_lower = page_text.lower()

    # Job type detection
    JOB_PATTERNS = {
        'transcription': ['transcri', 'transkri', 'transcriptie', 'transkribering',
                         '文字起こし', '전사', 'transkripsjon', 'transkriptio'],
        'annotation': ['annot', 'label', 'tagger', 'datenanno', 'annotatie',
                      'アノテーション', '어노테이션', '标注', 'adnotacja'],
        'translation': ['translat', 'übersetz', 'traducteur', 'vertaler',
                       '翻訳', '번역', 'traduttore', 'traductor', 'tłumacz'],
        'voice': ['voice record', 'voice over', 'sprachaufnahme',
                 '音声録音', '음성녹음', '语音采集', 'voice actor'],
        'content_moderation': ['content moderat', 'modération', 'moderatie', 'trust and safety'],
        'ai_training': ['ai train', 'rlhf', 'reinforcement learning', 'prompt eval',
                       'ki training', 'AIトレーニング'],
        'qa': ['quality rat', 'search eval', 'quality eval', 'internet assessor',
               'map analyst', 'caption', 'subtitl', 'ondertitel'],
        'survey': ['survey', 'umfrage', 'sondage', 'アンケート', '설문'],
        'research': ['research participant', 'user research', 'focus group'],
        'testing': ['user test', 'beta test', 'app test', 'nutzertest'],
        'tutoring': ['tutor', 'teach english', 'esl'],
        'proofreading': ['proofread', 'copy edit', 'lektorat'],
    }

    detected_type = 'other'
    for job_type, patterns in JOB_PATTERNS.items():
        if any(p in page_lower for p in patterns):
            detected_type = job_type
            break

    # Extract company name
    company_name = None
    meta_site = soup.find('meta', property='og:site_name')
    if meta_site:
        company_name = meta_site.get('content', '').strip()
    if not company_name:
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            for sep in [' | ', ' - ', ' – ', ' — ']:
                if sep in title_text:
                    parts = title_text.split(sep)
                    company_name = parts[-1].strip() or parts[0].strip()
                    break
            if not company_name:
                company_name = title_text[:50]
    if not company_name:
        company_name = domain.replace('www.', '').split('.')[0].title()

    # Find apply URL
    apply_url = url
    apply_patterns = ['apply', 'signup', 'sign-up', 'register', 'join',
                      'bewerben', 'postuler', 'solliciteren', 'hae', 'ansöka']
    for a in soup.find_all('a', href=True):
        href = a.get('href', '').lower()
        text = a.get_text(strip=True).lower()
        if any(p in href or p in text for p in apply_patterns):
            full_href = a['href']
            if full_href.startswith('http'):
                apply_url = full_href
            elif full_href.startswith('/'):
                parsed = urlparse(url)
                apply_url = f"{parsed.scheme}://{parsed.netloc}{full_href}"
            break

    # Hiring signals
    HIRING_SIGNALS = [
        'apply now', 'apply today', 'join our team', 'we are hiring',
        'now hiring', 'open position', 'current opening', 'job opening',
        'jetzt bewerben', 'wir suchen', 'postuler maintenant', 'nous recrutons',
        'solliciteer nu', 'wij zoeken', 'vacature', 'sök nu', 'vi söker',
        'søk nå', 'vi søker', 'hae nyt', 'etsimme', '応募する', '採用',
        '지원하기', '채용', '申请', '招聘', 'تقديم', 'وظيفة',
    ]
    has_hiring_signal = any(sig in page_lower for sig in HIRING_SIGNALS)

    if not has_hiring_signal:
        return []

    # Try to find specific job elements
    job_elements = (
        soup.find_all('li', class_=lambda c: c and any(
            kw in str(c).lower() for kw in ['job', 'position', 'vacancy', 'opening']
        )) or
        soup.find_all('div', class_=lambda c: c and any(
            kw in str(c).lower() for kw in ['job', 'position', 'vacancy', 'career']
        )) or
        soup.find_all('article') or []
    )

    if job_elements:
        for element in job_elements[:5]:
            title_el = (
                element.find('h1') or element.find('h2') or
                element.find('h3') or element.find('h4') or
                element.find(class_=lambda c: c and 'title' in str(c).lower())
            )
            if not title_el:
                continue
            title = title_el.get_text(strip=True)[:200]
            if not title or len(title) < 3:
                continue

            job_link = element.find('a', href=True)
            job_url = apply_url
            if job_link:
                href = job_link['href']
                if href.startswith('http'):
                    job_url = href
                elif href.startswith('/'):
                    parsed = urlparse(url)
                    job_url = f"{parsed.scheme}://{parsed.netloc}{href}"

            jobs.append({
                'title': title,
                'description': element.get_text(separator=' ', strip=True)[:300],
                'apply_url': job_url,
                'job_type': detected_type,
                'geo_tier': 0,
                'posting_language': lang,
                'work_language': 'en',
                'company_name': company_name,
                'is_relevant': True,
                'english_work_confirmed': True,
            })

    # No specific elements — create one generic entry if hiring signals found
    if not jobs and detected_type != 'other':
        title = None
        for tag in ['h1', 'h2', 'h3']:
            el = soup.find(tag)
            if el:
                text = el.get_text(strip=True)
                if 5 < len(text) < 100:
                    title = text
                    break
        if not title:
            title = f'{detected_type.replace("_", " ").title()} Position'

        jobs.append({
            'title': title,
            'description': f'{detected_type} work at {company_name}',
            'apply_url': apply_url,
            'job_type': detected_type,
            'geo_tier': 0,
            'posting_language': lang,
            'work_language': 'en',
            'company_name': company_name,
            'is_relevant': True,
            'english_work_confirmed': False,
        })

    return jobs


def extract_jobs_with_claude(url, page_text, lang='en'):
    try:
        import anthropic
        import os
        import json

        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        text_sample = page_text[:4000]

        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": f"""Analyze this webpage for task-based remote freelance jobs for English speakers.

URL: {url}
Content: {text_sample}

Return [] immediately if ANY of these are true:
- This is a blog, article, or list of companies/websites
- This is a software/tool product page (transcription software, survey tools, etc.)
- This is a job aggregator listing multiple companies
- This is a search results page or directory
- No direct application link exists on this page
- The actual work requires a non-English language
- This is not the actual employer directly hiring

Only return jobs if ALL are true:
- This IS the actual employer company website
- They ARE directly hiring freelancers/contractors right now
- The work requires English language ability
- There IS a clear apply/signup link on this page

Return JSON array only, no other text:
[{{"title":"specific job title","description":"what the work involves","apply_url":"direct application link","job_type":"transcription|annotation|ai_training|translation|voice|content_moderation|qa|survey|research|tutoring|testing|proofreading|other","geo_tier":0,"posting_language":"{lang}","work_language":"en","company_name":"actual company name","is_relevant":true,"english_work_confirmed":true}}]

If not a direct employer hiring page: []"""
            }]
        )

        response_text = message.content[0].text.strip()
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()

        jobs = json.loads(response_text)
        return jobs if isinstance(jobs, list) else []

    except Exception as e:
        logger.error(f'Claude extraction error for {url}: {e}')
        return []


def crawl_website(url, lang='en'):
    """
    Visits any website and uses Claude to extract job opportunities.
    Works on company websites, job boards, in any language.
    """
    jobs_created = 0

    # Skip known ATS platforms — handled by dedicated crawlers
    if 'boards.greenhouse.io' in url or 'jobs.lever.co' in url:
        return 0

    # Skip if crawled in last 2 weeks — saves Claude credits
    from django.core.cache import cache
    import hashlib as _hashlib
    url_hash = _hashlib.md5(url.encode()).hexdigest()
    cache_key = f'crawled_url:{url_hash}'
    if cache.get(cache_key):
        return 0
    # Default — don't revisit for 30 days
    # Will be updated after crawling based on what we found
    # Set initial cache — will be updated after crawl based on results
    # This prevents re-crawling if the process crashes mid-way
    cache.set(cache_key, True, timeout=86400 * 365)

    try:
        accept_lang = LANG_HEADERS.get(lang, 'en-US,en;q=0.9')
        headers = {**HEADERS, 'Accept-Language': accept_lang}

        r = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
        time.sleep(random.uniform(1, 2))

        if r.status_code != 200:
            return 0

        # Extract text content
        soup = BeautifulSoup(r.text, 'html.parser')

        # Remove scripts and styles
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()

        page_text = soup.get_text(separator=' ', strip=True)

        if len(page_text) < 200:
            return 0

        # FREE keyword pre-filter — skip Claude if no relevant keywords found
        # This saves 80% of API costs
        KEYWORDS = [
            # Core task types
            'transcri', 'annot', 'moderat', 'caption', 'subtitl',
            'voice record', 'data label', 'ai train', 'quality rat',
            'search evaluat', 'data collect', 'data entry',
            # Roles often used
            'freelanc', 'contributor', 'tagger', 'reviewer',
            'assessor', 'evaluator', 'rater', 'labeler', 'labeller',
            'linguist', 'interpreter', 'translator', 'proofreader',
            'transcriptionist', 'captioner', 'subtitler',
            # AI/ML specific
            'rlhf', 'reinforcement learning', 'human feedback',
            'prompt engineer', 'ai safety', 'content review',
            'image label', 'audio label', 'text label',
            'model train', 'dataset', 'ground truth',
            # Work context
            'remote work', 'work from home', 'work at home',
            'hiring', 'apply now', 'job opening', 'we are looking',
            'part.time', 'part time', 'flexible hours', 'gig work',
            'crowdsourc', 'microtask', 'task.based',
            # German
            'transkri', 'übersetz', 'untertitel', 'sprachaufnahme',
            'datenanno', 'qualitätsbew', 'freiberuf', 'heimarbeit',
            # French
            'transcripteur', 'annotateur', 'modérateur', 'traducteur',
            'sous-titrag', 'évaluateur', 'télétravail', 'freelance',
            # Dutch
            'transcriptie', 'annotatie', 'ondertitel', 'vertaler',
            'thuiswerk', 'vrijgevestig', 'beeldbeschrijv',
            # Swedish/Norwegian/Danish/Finnish
            'transkribering', 'annotering', 'undertekst', 'översättare',
            'transkriptio', 'annotointi', 'etätyö', 'kotityö',
            # Japanese
            '文字起こし', 'アノテーション', '字幕', '翻訳', '在宅',
            '音声録音', 'データ収集', 'フリーランス', 'リモート',
            # Korean
            '전사', '어노테이션', '자막', '번역', '재택',
            '음성녹음', '데이터수집', '프리랜서',
            # Chinese
            '转录', '标注', '字幕', '翻译', '远程',
            '语音采集', '数据采集', '自由职业',
            # Arabic
            'نسخ', 'تعليق', 'ترجمة', 'تقييم', 'عن بعد',
            # Italian/Spanish/Portuguese
            'trascrizi', 'annotazi', 'sottotitol', 'traduttore',
            'transcripci', 'anotaci', 'subtítul', 'traductor',
            'transcrição', 'anotação', 'legendas', 'tradutor',
            # Survey and research
            'survey', 'paid survey', 'online survey',
            'research participant', 'focus group',
            'user research', 'usability', 'user test',
            'beta test', 'app test', 'software test',
            # Tutoring and education
            'tutor', 'teach english', 'esl', 'language teach',
            'online teach', 'english teach',
            # Writing and editing
            'proofread', 'copy edit', 'copy writing',
            'content writ', 'blog writ', 'article writ',
            # Other remote work
            'mystery shop', 'chat support', 'virtual assist',
            'data entry', 'online juror', 'mock juror',
            # German surveys
            'umfrage', 'nutzertest', 'marktforschung',
            # French surveys  
            'sondage', 'enquête', 'test utilisateur',
            # Japanese surveys
            'アンケート', 'ユーザーテスト', '調査',
            # Korean surveys
            '설문', '사용자테스트', '조사',
        ]

        page_lower = page_text.lower()
        has_keywords = any(kw.lower() in page_lower for kw in KEYWORDS)

        if not has_keywords:
            logger.debug(f'No relevant keywords found on {url} — skipping Claude')
            return 0

        # Skip if page looks like a blog article listing companies
        # rather than a company directly hiring
        ARTICLE_SIGNALS = [
            'best transcription companies',
            'best annotation jobs',
            'top 10 sites',
            'top 10 companies',
            'list of companies',
            'sites like',
            'alternatives to',
            'review of',
            'we tested',
            'our review',
            'in this article',
            'in this post',
            'in this guide',
            'jump to section',
            'table of contents',
            'here are the best',
            'here are some',
            'top websites',
            'best websites',
            'best platforms',
            'list of sites',
            '10 best',
            '15 best',
            '20 best',
            'how to make money',
            'ways to make money',
            'side hustle',
            'passive income',
            'おすすめ',
            '推荐网站',
            '추천 사이트',
            'أفضل مواقع',
            'meilleurs sites',
            'beste websites',
        ]
        is_article = any(signal in page_lower for signal in ARTICLE_SIGNALS)
        if is_article:
            logger.debug(f'Article/list page detected — skipping {url}')
            return 0

        # Use FREE keyword scraper — no API cost
        # Rate limit Claude — max 150 calls/day to stay under $5/month
        from django.core.cache import cache
        daily_calls = cache.get('claude_daily_calls', 0)
        if daily_calls >= 50:
            logger.debug(f'Claude daily limit reached — using keyword scraper for {url}')
            jobs = extract_jobs_with_keywords(url, soup, page_text, lang)
        else:
            cache.set('claude_daily_calls', daily_calls + 1, timeout=86400)
            jobs = extract_jobs_with_claude(url, page_text, lang)

        if not jobs:
            return 0

        # Save found jobs
        domain = urlparse(url).netloc
        for job_data in jobs:
            if not job_data.get('is_relevant', False):
                continue
            # If work language is explicitly non-English — skip
            work_lang = job_data.get('work_language', 'en')
            if work_lang not in ['en', 'unknown', '']:
                continue
            # If english not confirmed but not denied — keep with flag
            english_confirmed = job_data.get('english_work_confirmed', True)
            needs_review = not english_confirmed

            company_name = job_data.get('company_name') or domain
            title = job_data.get('title', '')

            if not title or len(title) < 3:
                continue

            # Get or create company
            # Try to find existing company by name first
            existing = Company.objects.filter(
                name__iexact=company_name
            ).first()

            if existing:
                company = existing
                created = False
            else:
                company, created = Company.objects.get_or_create(
                    website=f"https://{domain}",
                    defaults={
                        'name': company_name,
                        'careers_url': url,
                        'discovered_via': 'Web search',
                        'trust_score': 55,
                        'last_checked': timezone.now(),
                        'last_active': timezone.now(),
                    }
                )

            if created:
                print(f"    🏢 New company: {company_name} [{domain}]")

            # Deduplicate
            import hashlib
            # Deduplicate by company domain + job_type
            # Prevents same company appearing 20x with different titles
            # Use company NAME + job_type for deduplication
            # This prevents same company appearing from different URLs
            company_key = company_name.lower().strip()
            # Normalize common variations
            company_key = company_key.replace(' inc', '').replace(' ltd', '').replace(' llc', '').replace('.com', '').strip()
            job_type = job_data.get('job_type', 'other')
            fingerprint = hashlib.sha256(
                f"web:{company_key}:{job_type}".lower().encode()
            ).hexdigest()

            if Job.objects.filter(fingerprint=fingerprint).exists():
                continue

            Job.objects.create(
                company=company,
                title=title,
                description=job_data.get('description', '')[:500],
                apply_url=job_data.get('apply_url', url),
                posting_language=job_data.get('posting_language', 'en'),
                work_language='en',
                job_type=job_data.get('job_type', 'other'),
                vacancy_state='active',
                geo_tier=job_data.get('geo_tier', 0),
                onboarding_level=2,
                citizenship_flag=needs_review,
                citizenship_note='English work language unconfirmed — please verify' if needs_review else '',
                physical_required=False,
                fingerprint=fingerprint,
                is_new=True,
                last_confirmed=timezone.now(),
            )
            jobs_created += 1
            print(f"      💼 [{job_data.get('posting_language', 'en')}→en] {title[:65]}")

        CrawlLog.objects.create(
            url=url,
            status='success',
            http_code=200,
            protection_level=2,
            jobs_found=jobs_created,
        )

        # Smart revisit logic
        if jobs_created > 0:
            # Found jobs — never revisit, we got what we needed
            cache.set(cache_key, True, timeout=86400 * 365)
        else:
            # Check if page signals "check back later" (ghost pipeline)
            ghost_signals = [
                'check back', 'coming soon', 'no positions',
                'no openings', 'not hiring', 'future opportunities',
                'talent pool', 'stay tuned', 'watch this space',
                'keine stellen', 'pas de postes', 'geen vacatures',
                'inga lediga', 'ei avoimia', 'ingen stillinger',
            ]
            page_lower_check = page_text.lower()
            is_ghost = any(sig in page_lower_check for sig in ghost_signals)

            if is_ghost:
                # Ghost pipeline — check back in 7 days
                cache.set(cache_key, True, timeout=86400 * 7)
            else:
                # No jobs, no ghost signal — irrelevant source, never revisit
                cache.set(cache_key, True, timeout=86400 * 365)

    except Exception as e:
        logger.error(f'Web crawl error for {url}: {e}')

    return jobs_created


def run_web_discovery():
    """
    Main web discovery engine.
    Searches DuckDuckGo in 15+ languages.
    Visits every result URL.
    Uses Claude to read pages in ANY language.
    Finds task-based English freelance work worldwide.
    """
    print("\n🌐 Web Discovery Engine starting...")
    print(f"   Searching in {len(SEARCH_QUERIES)} queries across 15 languages\n")

    total_jobs = 0
    total_urls = 0
    seen_urls = set()

    for lang, query in SEARCH_QUERIES:
        print(f"  [{lang}] {query[:60]}...")

        urls = search_web(query, lang)

        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Handle Greenhouse URLs specially
            if 'boards.greenhouse.io' in url:
                parts = url.replace('https://boards.greenhouse.io/', '').replace('https://www.boards.greenhouse.io/', '').split('/')
                if parts and parts[0] and len(parts[0]) > 1:
                    from core.crawlers.greenhouse import crawl_greenhouse_slug
                    jobs = crawl_greenhouse_slug(parts[0])
                    if jobs > 0:
                        total_jobs += jobs
                        print(f"      💼 Greenhouse {parts[0]}: {jobs} jobs")
                continue

            # Handle Lever URLs specially
            if 'jobs.lever.co' in url:
                parts = url.replace('https://jobs.lever.co/', '').split('/')
                if parts and parts[0] and len(parts[0]) > 1:
                    from core.crawlers.lever import crawl_lever_slug
                    jobs = crawl_lever_slug(parts[0])
                    if jobs > 0:
                        total_jobs += jobs
                        print(f"      💼 Lever {parts[0]}: {jobs} jobs")
                continue

            # For all other URLs — use Claude to read the page
            total_urls += 1
            print(f"    🔍 Scanning: {url[:70]}")
            jobs = crawl_website(url, lang)
            if jobs > 0:
                total_jobs += jobs

        time.sleep(random.uniform(1, 2))

    print(f"\n✅ Web discovery complete")
    print(f"   Queries run:     {len(SEARCH_QUERIES)}")
    print(f"   URLs scanned:    {total_urls}")
    print(f"   New jobs found:  {total_jobs}")

    return total_jobs