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

# ============================================================
# SEARCH QUERIES — Transcription + AI Annotation ONLY
# Deep search across 12 languages, multiple angles per type
# Goal: find UNKNOWN companies hiring worldwide
# ============================================================
SEARCH_QUERIES = [

    # ── ENGLISH TRANSCRIPTION ──────────────────────────────
    ('en', 'hiring english transcribers remote freelance apply now'),
    ('en', 'english transcription work from home apply'),
    ('en', 'freelance transcriptionist remote job opening apply'),
    ('en', 'transcription company hiring remote workers apply'),
    ('en', 'audio transcription remote freelance worldwide hiring'),
    ('en', 'video transcription remote freelance hiring apply'),
    ('en', 'medical transcription remote freelance hiring'),
    ('en', 'legal transcription remote freelance hiring'),
    ('en', 'academic transcription remote freelance hiring'),
    ('en', 'interview transcription remote freelance hiring'),
    ('en', 'podcast transcription remote freelance hiring'),
    ('en', 'court transcription remote freelance hiring'),
    ('en', 'transcription platform freelancers signup worldwide'),
    ('en', 'captioning subtitling remote freelance hiring apply'),
    ('en', 'closed captions remote freelance transcriber hiring'),
    ('en', 'live captioning remote freelance hiring apply'),

    # ── FRENCH TRANSCRIPTION ───────────────────────────────
    ('fr', 'recrutement transcripteurs français télétravail postuler'),
    ('fr', 'emploi transcription français freelance postuler maintenant'),
    ('fr', 'transcripteur freelance français télétravail embauche'),
    ('fr', 'société transcription recrute télétravailleurs postuler'),
    ('fr', 'transcription audio français freelance recrutement'),
    ('fr', 'transcription médicale français freelance recrutement'),
    ('fr', 'transcription juridique français freelance recrutement'),
    ('fr', 'sous-titrage français freelance recrutement postuler'),
    ('fr', 'plateforme transcription freelance inscription worldwide'),

    # ── ENGLISH AI TRAINING / ANNOTATION ───────────────────
    ('en', 'hiring english data annotators remote apply now'),
    ('en', 'AI training data labeling english remote freelance apply'),
    ('en', 'human feedback AI english remote freelance hiring'),
    ('en', 'RLHF english speakers remote freelance hiring apply'),
    ('en', 'AI annotation remote freelance worldwide hiring apply'),
    ('en', 'data labeling company hiring remote annotators apply'),
    ('en', 'machine learning data collection remote freelance hiring'),
    ('en', 'image annotation remote freelance worldwide hiring apply'),
    ('en', 'text annotation remote freelance worldwide hiring apply'),
    ('en', 'audio annotation remote freelance worldwide hiring apply'),
    ('en', 'video annotation remote freelance worldwide hiring apply'),
    ('en', 'content annotation platform freelancers signup worldwide'),
    ('en', 'AI model training remote freelance contributors hiring'),
    ('en', 'prompt evaluation remote freelance english hiring apply'),
    ('en', 'search quality rater remote freelance hiring apply'),
    ('en', 'internet assessor remote freelance hiring apply'),
    ('en', 'AI safety researcher remote freelance hiring apply'),
    ('en', 'LLM evaluation remote freelance english hiring apply'),
    ('en', 'named entity recognition remote freelance hiring apply'),
    ('en', 'sentiment analysis remote freelance hiring apply'),
    ('en', 'speech recognition training remote freelance hiring'),
    ('en', 'natural language processing data collection hiring remote'),

    # ── FRENCH AI TRAINING / ANNOTATION ────────────────────
    ('fr', 'annotation données IA français télétravail postuler'),
    ('fr', 'formation IA français freelance recrutement postuler'),
    ('fr', 'annotateur données français télétravail embauche'),
    ('fr', 'étiquetage données IA français freelance recrutement'),
    ('fr', 'évaluation modèle IA français freelance recrutement'),
    ('fr', 'collecte données IA français télétravail recrutement'),
    ('fr', 'annotation audio français freelance recrutement postuler'),
    ('fr', 'retour humain IA français freelance recrutement'),
    ('fr', 'évaluateur qualité IA français freelance postuler'),

    # ── GERMAN ─────────────────────────────────────────────
    ('de', 'Transkription Englisch freiberuflich weltweit bewerben Stelle'),
    ('de', 'Transkription Französisch freiberuflich weltweit bewerben'),
    ('de', 'Unternehmen sucht Transkriptoren remote bewerben'),
    ('de', 'KI Datenerfassung Annotation freiberuflich bewerben weltweit'),
    ('de', 'Datenannotation KI Training freiberuflich bewerben'),
    ('de', 'Sprachdaten Sammlung freiberuflich remote bewerben'),
    ('de', 'Audio Transkription freiberuflich remote Stelle bewerben'),
    ('de', 'KI Training freiberuflich remote Stelle bewerben'),

    # ── DUTCH ──────────────────────────────────────────────
    ('nl', 'transcriptie Engels freelance thuiswerk solliciteren vacature'),
    ('nl', 'transcriptie Frans freelance thuiswerk solliciteren'),
    ('nl', 'dataannotatie AI freelance thuiswerk solliciteren vacature'),
    ('nl', 'AI training data freelance thuiswerk solliciteren'),
    ('nl', 'bedrijf zoekt transcriptionist remote solliciteren'),
    ('nl', 'spraakherkenning data freelance remote solliciteren'),

    # ── JAPANESE ───────────────────────────────────────────
    ('ja', '英語 文字起こし リモート 採用 フリーランス 応募'),
    ('ja', 'フランス語 文字起こし リモート 採用 フリーランス 応募'),
    ('ja', 'AIデータアノテーション リモート 採用 フリーランス 応募'),
    ('ja', 'データラベリング AI リモートワーク 採用 応募'),
    ('ja', '音声データ収集 リモート フリーランス 採用 応募'),
    ('ja', '機械学習 データ収集 リモート フリーランス 採用'),

    # ── KOREAN ─────────────────────────────────────────────
    ('ko', '영어 전사 재택근무 프리랜서 채용 지원'),
    ('ko', '프랑스어 전사 재택근무 프리랜서 채용'),
    ('ko', 'AI 데이터 어노테이션 재택 프리랜서 채용 지원'),
    ('ko', '데이터 라벨링 AI 재택 프리랜서 채용'),
    ('ko', '음성 데이터 수집 재택 프리랜서 채용'),

    # ── CHINESE ────────────────────────────────────────────
    ('zh', '英语 转录 远程 招聘 自由职业 申请'),
    ('zh', '法语 转录 远程 招聘 自由职业'),
    ('zh', 'AI 数据标注 远程 招聘 自由职业 申请'),
    ('zh', '数据标注 机器学习 远程 招聘 申请'),
    ('zh', '语音数据采集 远程 自由职业 招聘'),

    # ── SPANISH ────────────────────────────────────────────
    ('es', 'empresa contrata transcriptores inglés freelance remoto aplicar'),
    ('es', 'empresa contrata transcriptores francés freelance remoto'),
    ('es', 'anotación datos IA inglés teletrabajo freelance aplicar'),
    ('es', 'etiquetado datos IA remoto freelance contratando aplicar'),
    ('es', 'entrenamiento IA inglés freelance remoto aplicar'),

    # ── PORTUGUESE ─────────────────────────────────────────
    ('pt', 'empresa contrata transcritores inglês remoto freelance candidatar'),
    ('pt', 'empresa contrata transcritores francês remoto freelance'),
    ('pt', 'anotação dados IA inglês teletrabalho freelance candidatar'),
    ('pt', 'rotulagem dados IA remoto freelance candidatar'),

    # ── ITALIAN ────────────────────────────────────────────
    ('it', 'azienda cerca trascrittori inglese remoto freelance candidarsi'),
    ('it', 'annotazione dati IA inglese telelavoro freelance candidarsi'),
    ('it', 'etichettatura dati IA remoto freelance candidarsi'),

    # ── SWEDISH ────────────────────────────────────────────
    ('sv', 'företag söker transkribenter engelska distansarbete ansökan'),
    ('sv', 'AI dataannotering distansjobb freelance engelska ansökan'),
    ('sv', 'dataetiketting AI distansarbete freelance ansökan'),

    # ── POLISH ─────────────────────────────────────────────
    ('pl', 'firma zatrudnia transkrybentów angielski zdalnie freelance aplikuj'),
    ('pl', 'adnotacja danych AI angielski praca zdalna freelance aplikuj'),

    # ── ARABIC ─────────────────────────────────────────────
    ('ar', 'شركة تبحث عن متفرغين للنسخ الإنجليزي عن بعد تقديم'),
    ('ar', 'تعليق بيانات الذكاء الاصطناعي عن بعد تقديم'),

    # ── DEEP NICHE ENGLISH (page 2+ territory) ─────────────
    ('en', 'transcription startup hiring remote workers worldwide'),
    ('en', 'new transcription company hiring freelancers apply'),
    ('en', 'transcription service provider hiring remote transcribers'),
    ('en', 'annotation startup hiring remote workers worldwide'),
    ('en', 'new AI company hiring data annotators remote apply'),
    ('en', 'AI data company hiring remote annotators worldwide'),
    ('en', 'NLP company hiring remote data collectors apply'),
    ('en', 'speech AI company hiring transcribers remote apply'),
    ('en', 'computer vision company hiring annotators remote apply'),
    ('en', 'autonomous vehicle data annotation remote hiring apply'),
    ('en', 'healthcare AI data annotation remote hiring apply'),
    ('en', 'legal AI data annotation remote hiring apply'),
    ('en', 'financial AI data annotation remote hiring apply'),
    ('en', 'ecommerce product annotation remote freelance hiring'),
    ('en', 'social media content annotation remote freelance hiring'),
    ('en', 'multilingual transcription remote freelance hiring apply'),
    ('en', 'bilingual transcriber english french remote hiring apply'),
    ('en', 'freelance transcription signup platform worldwide apply'),
    ('en', 'crowdsource transcription platform hiring apply'),
    ('en', 'remote transcription contractor hiring apply worldwide'),
]

# ============================================================
# SKIP DOMAINS — ALL job aggregators, article sites, boards
# We want DIRECT employer pages ONLY
# ============================================================
SKIP_DOMAINS = [
    # Social media
    'facebook.com', 'twitter.com', 'x.com', 'youtube.com',
    'instagram.com', 'tiktok.com', 'pinterest.com', 'snapchat.com',
    'telegram.org', 'whatsapp.com', 'discord.com', 'slack.com',

    # Professional networks
    'linkedin.com', 'xing.com', 'viadeo.com',

    # General knowledge
    'wikipedia.org', 'wikihow.com', 'quora.com', 'reddit.com',
    'stackexchange.com', 'stackoverflow.com', 'medium.com',
    'wordpress.com', 'blogspot.com', 'substack.com', 'tumblr.com',

    # E-commerce (not employers)
    'amazon.com', 'ebay.com', 'etsy.com', 'aliexpress.com',
    'shopify.com', 'walmart.com',

    # Freelancer MARKETPLACES (people sell skills, not companies hiring)
    'upwork.com', 'freelancer.com', 'fiverr.com', 'peopleperhour.com',
    'guru.com', 'toptal.com', 'workhoppers.com', 'bark.com',
    'tasker.com', 'airtasker.com', 'servicescape.com',
    'freelancer.nl', 'werkspot.nl', 'twago.com', 'malt.com',
    'malt.fr', 'malt.de', 'malt.es', 'malt.nl',
    'codementor.io', 'truelancer.com', 'workana.com',
    'freelancemap.com', 'freelancermap.com', 'freelance.de',
    'freelance.fr', 'freelance.nl', 'freelancer.de',
    'freelancer.es', 'freelancer.fr', 'freelancer.pt',
    'freelancer.in', 'freelancer.com.au',

    # MAJOR JOB AGGREGATORS
    'indeed.com', 'glassdoor.com', 'ziprecruiter.com',
    'monster.com', 'careerbuilder.com', 'simplyhired.com',
    'jooble.org', 'jobrapido.com', 'neuvoo.com', 'talent.com',
    'snagajob.com', 'dice.com', 'ladders.com', 'salary.com',
    'payscale.com', 'getwork.com', 'joblist.com',

    # REMOTE JOB BOARDS (aggregators, not employers)
    'flexjobs.com', 'remote.co', 'remoteok.com', 'remoteok.io',
    'weworkremotely.com', 'workingnomads.com', 'justremote.co',
    'remotehub.com', 'virtualvocations.com', 'remoteleaf.com',
    'remoote.app', 'remote.com', 'remotive.com', 'remotive.io',
    'jobspresso.co', 'outsourcely.com', 'pangian.com',
    'nodesk.co', 'authentic-jobs.com', 'dribbble.com',
    'himalayas.app', 'wellfound.com', 'angel.co',
    'builtin.com', 'builtinnyc.com', 'builtinla.com',
    'eurostaffgroup.com', 'eurastaff.com',

    # COUNTRY-SPECIFIC JOB BOARDS
    # Netherlands/Belgium
    'thuiswerk.nl', 'thuiswerken.nl', 'thuiswerkvacatures.nl',
    'thuiswerkweb.nl', 'thuisaanhetwerk.nl', 'werkvanuithuisvacatures.nl',
    'werkenvanuithuis.nl', 'workingremotely.nl', 'werkenvanuitthuis.nl',
    'vacaturesite.nl', 'nationale-vacaturebank.nl', 'intermediair.nl',
    'monsterboard.nl', 'jobbird.com', 'werk.nl', 'jobsonline.nl',
    'vdab.be', 'actiris.brussels', 'forem.be',
    'freelance.nl', 'freelancespecialisten.nl', 'freelancefirm.nl',
    'freelancenetwork.be', 'flexspot.io', 'youngones.com',
    'startpeople.nl', 'unique.nl', 'tempo-team.nl',

    # Germany/Austria/Switzerland
    'stepstone.de', 'xing.com', 'kimeta.de', 'heyjobs.co',
    'de.whatjobs.com', 'karrierex.de', 'jobware.de',
    'jobbörse.de', 'stellenanzeigen.de', 'jobscout24.de',
    'meinestadt.de', 'kalaydo.de', 'yourfirm.de',
    'remotely.de', 'dasauge.de', 'machdudas.de',
    'jobs.ch', 'jobup.ch', 'jobscout24.ch',

    # Japan
    'stanby.jp', 'rikunabi.com', 'mynavi.jp', 'doda.jp',
    'en-japan.com', 'bizreach.jp', 'wantedly.com',

    # Singapore
    'jobsdb.com', 'jobstreet.com', 'efinancialcareers.sg',

    # France
    'emploi.fr', 'pole-emploi.fr', 'cadremploi.fr',
    'regionsjob.com', 'welcometothejungle.com',

    # Spain/Portugal/Brazil
    'infojobs.net', 'tecnoempleo.com', 'bumeran.com',
    'catho.com.br', 'vagas.com.br', 'empregos.com.br',

    # UK
    'reed.co.uk', 'totaljobs.com', 'cv-library.co.uk',
    'fish4.co.uk', 'jobsite.co.uk',

    # General European
    'eurojobs.com', 'europeanmobility.eu',

    # ARTICLE/BLOG SITES pretending to be job boards
    'flexjobs.com', 'rat-race-rebellion.com',
    'theworkathomewoman.com', 'dreamhomebasedwork.com',
    'moneypantry.com', 'smartmoneymamas.com',
    'workathomenoscams.com', 'thecrazycouponer.com',
    'makealivingwriting.com', 'thepennymatters.com',
    'singlemamedesperate.com', 'abacityblog.com',
    'chalized.com', 'harowaka.com', 'contentwriter.pl',
    'workersonboard.com', 'genaijobs.co',
    'theworkfromhomequeen.com', 'searchlabz.com',
    'speechify.com', 'scribejoy.com',

    # ATS platforms (handled by dedicated crawlers)
    'boards.greenhouse.io', 'jobs.lever.co', 'apply.workable.com',
    'jobs.ashbyhq.com', 'smartrecruiters.com',

    # Middle East job boards
    'bayt.com', 'wuzzuf.net', 'forasna.com', 'tanqeeb.com',
    'akhtaboot.com', 'mihnati.com', 'naukrigulf.com',
    'gulftalent.com',

    # Payment/finance (not employers)
    'payoneer.com', 'paypal.com', 'wise.com',

    # Review sites
    'trustpilot.com', 'g2.com', 'capterra.com', 'sitejabber.com',
    'glassdoor.com',

    # Misc non-employer
    'appendata.com', 'mercor.io', 'mostaql.com',
    'topcontent.com', 'textmaster.com',
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


def search_duckduckgo(query, lang='en', max_results=30, region='wt-wt'):
    """
    Searches DuckDuckGo across multiple pages to find unknown companies.
    Goes deep — not just page 1. Page 1 has Rev/GoTranscript.
    Pages 2-5 have the unknown companies we actually want.
    """
    urls = []
    seen = set()
    try:
        accept_lang = LANG_HEADERS.get(lang, 'en-US,en;q=0.9')
        headers = {**HEADERS, 'Accept-Language': accept_lang}
        proxy = get_proxy()

        # Page 1 — standard search
        r = httpx.get(
            f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}&kl={region}",
            headers=headers,
            proxy=proxy.get('https://') if proxy else None,
            timeout=25,
            follow_redirects=True,
        )
        time.sleep(random.uniform(2, 4))

        if r.status_code not in [200, 202]:
            return urls

        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', class_='result__url')

        if not links:
            return urls

        for link in links:
            raw = link.get('href', '')
            if 'uddg=' in raw:
                url = unquote(raw.split('uddg=')[1].split('&')[0])
            elif raw.startswith('http'):
                url = raw
            else:
                continue

            if not url.startswith('http'):
                continue
            if 'duckduckgo.com/y.js' in url:
                continue

            domain = urlparse(url).netloc.lower()
            if any(skip in domain for skip in SKIP_DOMAINS):
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)

        # Pages 2-4 — dig deeper for unknown companies
        # DuckDuckGo uses 's' parameter for pagination (s=30, s=60, s=90)
        for page_start in [30, 60, 90]:
            try:
                time.sleep(random.uniform(3, 5))
                r2 = httpx.get(
                    f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}&kl={region}&s={page_start}",
                    headers=headers,
                    proxy=proxy.get('https://') if proxy else None,
                    timeout=25,
                    follow_redirects=True,
                )
                if r2.status_code not in [200, 202]:
                    break

                soup2 = BeautifulSoup(r2.text, 'html.parser')
                links2 = soup2.find_all('a', class_='result__url')
                if not links2:
                    break

                new_found = 0
                for link in links2:
                    raw = link.get('href', '')
                    if 'uddg=' in raw:
                        url = unquote(raw.split('uddg=')[1].split('&')[0])
                    elif raw.startswith('http'):
                        url = raw
                    else:
                        continue

                    if not url.startswith('http'):
                        continue
                    if 'duckduckgo.com/y.js' in url:
                        continue

                    domain = urlparse(url).netloc.lower()
                    if any(skip in domain for skip in SKIP_DOMAINS):
                        continue
                    if url not in seen:
                        seen.add(url)
                        urls.append(url)
                        new_found += 1

                if new_found == 0:
                    break  # No new results — stop paginating

            except Exception as e:
                logger.debug(f'DDG page {page_start} error: {e}')
                break

    except Exception as e:
        logger.error(f'DDG error: {e}')

    logger.info(f'DDG found {len(urls)} URLs for: {query[:50]}')
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
    # Disabled — keyword scraper too permissive, AI only
    return []

def _extract_jobs_with_keywords_disabled(url, soup, page_text, lang='en'):
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
        from core.crawlers.ai_client import client, DEPLOYMENT
        import os
        import json

        text_sample = page_text[:4000]

        message = client.chat.completions.create(
            model=DEPLOYMENT,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": f"""You are analyzing a webpage to find companies DIRECTLY hiring remote freelance transcribers or AI data annotators.

URL: {url}
Content: {text_sample}

Return [] IMMEDIATELY if ANY of these are true:
- This is a blog, article, guide, or list ("10 best...", "how to find...", "top sites...")
- This is a job aggregator or job board listing multiple companies
- This is a freelancer marketplace (upwork, fiverr, malt, etc.)
- This is a search results page or directory
- This is a news article or press release
- This is a software/tool product page (transcription software, AI tools, etc.)
- The company is NOT directly hiring (they just provide software/tools)
- No transcription OR data annotation/AI training work is mentioned
- No application/signup link exists on this page

Only return jobs if ALL of these are true:
- This IS the actual employer company website directly hiring
- They ARE actively hiring remote freelancers RIGHT NOW
- The work is transcription (audio/video to text) OR AI data annotation/labeling/training
- Work can be done in English OR French (or both)
- There IS a clear apply/signup link on this page

Return JSON array only, no other text:
[{{"title":"exact job title from page","description":"what the work involves","apply_url":"direct application URL","job_type":"transcription|ai_annotation","work_language":"en|fr|en+fr","posting_language":"{lang}","company_name":"company name","is_relevant":true}}]

If not a direct employer hiring transcribers or annotators: []"""
            }]
        )

        response_text = message.choices[0].message.content.strip()
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
            # Transcription
            'transcri', 'transkri', 'transcriptie', 'transkribering',
            'transkriptio', 'transkripsjon', 'transcripteur',
            '文字起こし', '전사', 'caption', 'subtitl', 'sous-titrag',
            'captioner', 'subtitler', 'transcriptionist',
            # AI Annotation / Data Labeling
            'annot', 'label', 'tagger', 'datenanno', 'annotatie',
            'アノテーション', '어노테이션', '标注', 'adnotacja',
            'annotateur', 'annotator', 'labeler', 'labeller',
            'data label', 'data collect', 'image label',
            'audio label', 'text label', 'video label',
            # AI Training
            'rlhf', 'reinforcement learning', 'human feedback',
            'ai train', 'ki training', 'AIトレーニング',
            'prompt eval', 'ai safety', 'model train',
            'ground truth', 'dataset collection',
            'quality rat', 'search evaluat', 'internet assessor',
            'LLM eval', 'NLP data', 'speech recogni',
            # Work context
            'hiring', 'apply now', 'job opening', 'we are hiring',
            'now hiring', 'freelanc', 'contributor', 'remote work',
            'work from home', 'crowdsourc', 'microtask',
            # German
            'transkri', 'untertitel', 'sprachaufnahme',
            'datenanno', 'freiberuf', 'KI Training',
            # French
            'transcripteur', 'annotateur', 'sous-titrag',
            'évaluateur', 'télétravail', 'annotation données',
            # Dutch
            'transcriptie', 'annotatie', 'ondertitel', 'thuiswerk',
            # Japanese
            '文字起こし', 'アノテーション', '字幕', '在宅',
            '音声録音', 'データ収集', 'フリーランス',
            # Korean
            '전사', '어노테이션', '자막', '재택', '음성녹음',
            # Chinese
            '转录', '标注', '字幕', '远程', '语音采集',
            # Arabic
            'نسخ', 'تعليق', 'عن بعد',
            # Spanish/Portuguese/Italian
            'transcripci', 'anotaci', 'subtítul',
            'transcrição', 'anotação', 'trascrizi', 'annotazi',
        ]

        page_lower = page_text.lower()
        has_keywords = any(kw.lower() in page_lower for kw in KEYWORDS)

        if not has_keywords:
            logger.debug(f'No relevant keywords found on {url} — skipping Claude')
            return 0

        # Skip if page looks like a blog article listing companies
        # rather than a company directly hiring
        ARTICLE_SIGNALS = [
            # Chinese article signals
            '行业调研', '市场占有率', '解决方案', '行业报告',
            '市场分析', '趋势分析', '软件市场', '系统行业',
            # Korean article signals
            '리스트', '방법', '플랫폼 소개', '회사가 있나요',
            # Japanese article signals
            'おすすめ', 'ランキング', '比較', '一覧',
            # General article signals
            'market report', 'industry report', 'market analysis',
            'market share', 'industry trends', 'solutions provider',
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
        if daily_calls >= 200:
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

            # STRICT: only transcription and ai_annotation
            job_type = job_data.get('job_type', 'other')
            if job_type not in ['transcription', 'ai_annotation']:
                # Try to remap close types
                if job_type in ['annotation', 'ai_training', 'qa']:
                    job_type = 'ai_annotation'
                    job_data['job_type'] = 'ai_annotation'
                else:
                    logger.debug(f'Skipping irrelevant job type: {job_type}')
                    continue

            # If work language is explicitly non-English/French — skip
            work_lang = job_data.get('work_language', 'en')
            if work_lang not in ['en', 'fr', 'en+fr', 'unknown', '']:
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