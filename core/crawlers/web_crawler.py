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
# SEARCH QUERIES — Company Discovery Focus
# Goal: find UNKNOWN companies' own career pages
# Strategy: search how COMPANIES post jobs, not how job seekers search
# ============================================================
SEARCH_QUERIES = [

    # ── ENGLISH TRANSCRIPTION — Company perspective ─────────
    ('en', 'we are hiring transcriptionists remote freelance'),
    ('en', 'join our transcription team remote work'),
    ('en', 'transcription contractors wanted remote work from home'),
    ('en', '"transcriptionists needed" remote freelance'),
    ('en', 'become a transcriptionist apply our platform'),
    ('en', 'transcription work available apply freelancers'),
    ('en', 'work with us transcription remote freelance'),
    ('en', 'transcription services company careers freelancers'),
    ('en', 'captioning company hiring freelance captioners apply'),
    ('en', 'subtitling company hiring freelancers remote apply'),
    ('en', 'medical transcription company hiring remote freelancers'),
    ('en', 'legal transcription company hiring remote freelancers'),
    ('en', 'court reporting transcription company hiring remote'),
    ('en', 'podcast transcription platform hiring freelancers'),
    ('en', 'audio transcription platform freelancer signup'),
    ('en', 'video transcription company hiring contractors'),
    ('en', '"work from home" transcription company hiring now'),
    ('en', 'transcription platform signup earn money'),
    ('en', 'become a captioner apply now remote'),
    ('en', 'earn money transcribing audio online apply'),

    # ── FRENCH TRANSCRIPTION — Company perspective ──────────
    ('fr', 'nous recrutons transcripteurs freelance télétravail'),
    ('fr', 'rejoignez notre équipe transcription freelance'),
    ('fr', 'transcripteurs recherchés télétravail postuler'),
    ('fr', 'plateforme transcription recrute freelances'),
    ('fr', 'société transcription embauche télétravailleurs'),
    ('fr', 'transcription médicale recrute freelances'),
    ('fr', 'transcription juridique recrute freelances'),
    ('fr', 'sous-titrage recrute freelances télétravail'),
    ('fr', 'travailler avec nous transcription freelance'),
    ('fr', 'gagner argent transcription en ligne postuler'),

    # ── ENGLISH AI ANNOTATION — Company perspective ─────────
    ('en', 'we are hiring data annotators remote freelance'),
    ('en', 'join our annotation team remote work'),
    ('en', 'data labelers wanted remote work from home'),
    ('en', '"annotators needed" remote freelance apply'),
    ('en', 'become a data annotator apply our platform'),
    ('en', 'annotation work available apply freelancers'),
    ('en', 'work with us data annotation remote'),
    ('en', 'AI training company hiring remote contributors'),
    ('en', 'RLHF contractors wanted remote work apply'),
    ('en', 'human feedback AI company hiring remote'),
    ('en', 'machine learning data company hiring annotators'),
    ('en', 'NLP company hiring linguistic annotators remote'),
    ('en', 'computer vision annotation company hiring remote'),
    ('en', 'autonomous vehicle data labeling company hiring'),
    ('en', 'speech recognition training data company hiring'),
    ('en', 'image labeling company hiring remote freelancers'),
    ('en', 'text labeling company hiring remote freelancers'),
    ('en', 'AI startup hiring remote data contributors'),
    ('en', 'earn money AI training data annotation apply'),
    ('en', 'crowdsource AI data platform signup freelancers'),

    # ── FRENCH AI ANNOTATION — Company perspective ──────────
    ('fr', 'nous recrutons annotateurs données IA télétravail'),
    ('fr', 'rejoignez notre équipe annotation IA freelance'),
    ('fr', 'annotateurs données recherchés télétravail'),
    ('fr', 'plateforme annotation IA recrute freelances'),
    ('fr', 'société annotation données embauche télétravailleurs'),
    ('fr', 'formation IA recrute contributeurs freelance'),
    ('fr', 'gagner argent annotation données IA postuler'),
    ('fr', 'travail annotation IA disponible postuler'),
    ('fr', 'évaluation IA recrute freelances télétravail'),

    # ── GERMAN ─────────────────────────────────────────────
    ('de', 'wir suchen Transkriptoren freiberuflich Heimarbeit'),
    ('de', 'Transkriptoren gesucht freiberuflich bewerben'),
    ('de', 'Transkriptionsplattform sucht Freiberufler bewerben'),
    ('de', 'Datenannotation Stelle freiberuflich Heimarbeit bewerben'),
    ('de', 'KI Training Daten freiberuflich gesucht bewerben'),
    ('de', 'wir suchen Datenbeschrifter freiberuflich remote'),
    ('de', 'KI Unternehmen sucht remote Mitarbeiter bewerben'),
    ('de', 'Audio Transkription freiberuflich gesucht bewerben'),
    ('de', 'Sprachdaten Sammlung freiberuflich gesucht bewerben'),

    # ── DUTCH ──────────────────────────────────────────────
    ('nl', 'wij zoeken transcriptionist freelance thuiswerk'),
    ('nl', 'transcriptionisten gezocht freelance solliciteren'),
    ('nl', 'dataannotatie freelance gezocht thuiswerk solliciteren'),
    ('nl', 'AI training data freelance gezocht solliciteren'),
    ('nl', 'wij zoeken data-annotator freelance remote'),
    ('nl', 'transcriptieplatform zoekt freelancers solliciteren'),

    # ── JAPANESE ───────────────────────────────────────────
    ('ja', '文字起こしスタッフ募集 在宅 フリーランス 応募'),
    ('ja', 'アノテーター募集 在宅ワーク フリーランス 応募'),
    ('ja', 'データラベリング スタッフ募集 在宅 応募'),
    ('ja', 'AI訓練データ 募集 在宅ワーク 応募'),
    ('ja', '音声データ収集 スタッフ募集 在宅 応募'),
    ('ja', '字幕制作 フリーランス 募集 在宅 応募'),

    # ── KOREAN ─────────────────────────────────────────────
    ('ko', '전사 작업자 모집 재택근무 프리랜서 지원'),
    ('ko', '데이터 어노테이터 모집 재택 프리랜서 지원'),
    ('ko', 'AI 데이터 라벨링 모집 재택 지원'),
    ('ko', '음성 데이터 수집 모집 재택 지원'),
    ('ko', '자막 제작 프리랜서 모집 재택 지원'),

    # ── CHINESE ────────────────────────────────────────────
    ('zh', '招募 转录员 远程 自由职业 申请'),
    ('zh', '招募 数据标注员 远程 自由职业 申请'),
    ('zh', 'AI训练数据 招募 远程 申请'),
    ('zh', '语音数据采集 招募 远程 申请'),
    ('zh', '字幕制作 招募 远程 自由职业'),

    # ── SPANISH ────────────────────────────────────────────
    ('es', 'buscamos transcriptores freelance teletrabajo'),
    ('es', 'se buscan anotadores datos IA teletrabajo'),
    ('es', 'plataforma transcripción busca freelancers'),
    ('es', 'empresa IA busca anotadores remote aplicar'),
    ('es', 'gana dinero transcripción en línea aplicar'),
    ('es', 'gana dinero anotación datos IA aplicar'),

    # ── PORTUGUESE ─────────────────────────────────────────
    ('pt', 'procuramos transcritores freelance teletrabalho'),
    ('pt', 'anotadores dados IA procurados teletrabalho'),
    ('pt', 'plataforma transcrição procura freelancers'),
    ('pt', 'ganhar dinheiro transcrição online candidatar'),
    ('pt', 'ganhar dinheiro anotação dados IA candidatar'),

    # ── ITALIAN ────────────────────────────────────────────
    ('it', 'cerchiamo trascrittori freelance telelavoro'),
    ('it', 'cercasi annotatori dati IA telelavoro'),
    ('it', 'guadagna trascrivendo audio online candidarsi'),

    # ── SWEDISH ────────────────────────────────────────────
    ('sv', 'vi söker transkribenter frilansar distansarbete'),
    ('sv', 'dataannoterare sökes distansarbete frilansar'),
    ('sv', 'tjäna pengar transkribering online ansökan'),

    # ── POLISH ─────────────────────────────────────────────
    ('pl', 'szukamy transkrybentów freelance praca zdalna'),
    ('pl', 'adnotatorzy danych szukani praca zdalna aplikuj'),
    ('pl', 'zarabiaj transkrybując audio online aplikuj'),

    # ── ARABIC ─────────────────────────────────────────────
    ('ar', 'نبحث عن متفرغين للنسخ عن بعد تقديم'),
    ('ar', 'مطلوب محررو بيانات ذكاء اصطناعي عن بعد'),

    # ── VERY SPECIFIC NICHES (find truly unknown companies) ─
    ('en', 'focus group transcription company hiring remote'),
    ('en', 'interview transcription company hiring freelancers'),
    ('en', 'academic research transcription company hiring'),
    ('en', 'market research transcription hiring remote'),
    ('en', 'insurance transcription company hiring remote'),
    ('en', 'financial transcription company hiring freelancers'),
    ('en', 'government transcription contractor remote hiring'),
    ('en', 'broadcast captioning company hiring remote'),
    ('en', 'real time captioning company hiring freelancers'),
    ('en', 'e-learning captioning company hiring remote'),
    ('en', 'sentiment analysis company hiring remote annotators'),
    ('en', 'named entity recognition company hiring remote'),
    ('en', 'intent classification company hiring annotators'),
    ('en', 'chatbot training data company hiring remote'),
    ('en', 'conversational AI data company hiring freelancers'),
    ('en', 'autonomous driving data annotation company hiring'),
    ('en', 'retail AI data annotation company hiring remote'),
    ('en', 'healthcare NLP data company hiring annotators'),
    ('en', 'fintech AI data company hiring remote annotators'),
    ('en', 'edtech AI data company hiring remote annotators'),
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

# ============================================================
# APPLY URL VALIDATOR — rejects jobs with bad apply_url
# Even if AI extracts a job, we reject it if apply_url
# points to an article, aggregator, or job board
# ============================================================
BAD_APPLY_DOMAINS = [
    # Article and blog sites
    'earnbeyondborders.com', 'remoteleaf.com', 'remoteotter.com',
    'nonphoneworkathome.com', 'wahojobs.com', 'remoteworkrebels.com',
    'ivetriedthat.com', 'improveworkspace.com', 'schemaninja.com',
    'stephatch.com', 'thinkoutsidethecubiclenow.com', 'nichepursuits.com',
    'etoppc.com', 'etechpt.com', 'newsblog.pl', 'chalized.com',
    'solidgigs.com', 'remotech.ai', 'aitrainer.work', 'genaijobs.co',
    'huntscreens.com', 'aidoos.com', 'remotive.com', 'arc.dev',
    'careerspage.io', 'realremotejobs.com', 'up2staff.com',
    'workfromhomies.net', 'yaoweibin.cn', 'liezhe.com',
    'news.like.tg', 'zaitakushigoto.com', 'toolify.ai',
    'emilyturrettini.substack.com', 'note.com', 'fireflies.ai',
    'speechify.com', 'appendata.com', 'comologia.com',
    'goworkship.com', 'v2ex.com', 'kaigai-job.jp',
    'remoterocketship.com', 'fr.workopolis.com', 'egyjob.net',
    'jobplanet.co.kr', 'vakanser.se', 'remotetalentcloud.com',
    'remoter.me', 'jp.indeed.com', 'linkedin.com',
    'stanby.jp', 'indeed.com', 'glassdoor.com',
    'aitoolnet.com', 'lesbonsfreelances.com', 'transgate.ai',
    'ziloservices.com', 'sonix.ai/resources', 'amino.dk',
    'remote.com/jobs', 'ghostwriting.com', 'duction.com',
    'workathomesmart.com', 'escribr.com', 'geekflare.com',
    'toptips.fr', 'etoppc.com', 'scriptme.io',
    'remoteotter.com', 'wahojobs.com', 'remoteworkrebels.com',
    # Job aggregators
    'freelancer.com', 'freelancer.de', 'freelancer.mx',
    'freelancer.es', 'freelancer.fr', 'freelancer.pt',
    'crowdworks.jp', 'upwork.com', 'fiverr.com',
    # Remote job boards
    'remotive.io', 'remoteok.com', 'weworkremotely.com',
    'remotehub.com', 'flexjobs.com', 'workingnomads.com',
]

def is_valid_apply_url(url):
    """Returns True if the apply_url points to a direct employer page."""
    if not url or not url.startswith('http'):
        return False
    domain = urlparse(url).netloc.lower()
    if any(bad in domain for bad in BAD_APPLY_DOMAINS):
        return False
    return True



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
                time.sleep(random.uniform(1, 2))
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
        time.sleep(random.uniform(2, 4))

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


def find_jobs_subpage(url, soup):
    """
    If a page looks like a careers landing page with no jobs,
    try to find the actual jobs listing subpage.
    """
    from urllib.parse import urljoin
    
    JOB_LINK_PATTERNS = [
        'open roles', 'view jobs', 'see jobs', 'explore jobs',
        'current openings', 'open positions', 'view openings',
        'apply now', 'join our team', 'work with us',
        'freelancer', 'freelance', 'contractor', 'crowd',
        'opportunities', 'vacancies', 'explore open',
    ]
    
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True).lower()
        href = a['href'].lower()
        
        if any(p in text or p in href for p in JOB_LINK_PATTERNS):
            full_url = a['href']
            if full_url.startswith('http'):
                return full_url
            elif full_url.startswith('/'):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                return f"{parsed.scheme}://{parsed.netloc}{full_url}"
    
    return None


def crawl_website(url, lang='en'):
    """
    Visits any website and uses Claude to extract job opportunities.
    Works on company websites, job boards, in any language.
    Follows one level deeper if careers landing page found.
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
        time.sleep(random.uniform(0.3, 0.8))

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

        # Use Azure OpenAI — no cost limit, burning Azure credits
        jobs = extract_jobs_with_claude(url, page_text, lang)
        
        # If no jobs found and page looks like a landing page, try subpage
        if not jobs:
            subpage_url = find_jobs_subpage(url, soup)
            if subpage_url and subpage_url != url:
                logger.info(f'Following subpage: {subpage_url}')
                sub_hash = __import__("hashlib").md5(subpage_url.encode()).hexdigest()
                if not cache.get(f"crawled_url:{sub_hash}"):
                    return crawl_website(subpage_url, lang)

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

            # Validate apply_url — reject if pointing to article/aggregator
            apply_url_check = job_data.get('apply_url', url)
            if not is_valid_apply_url(apply_url_check):
                logger.debug(f'Rejected job with bad apply_url: {apply_url_check[:60]}')
                continue

            # Reject suspicious company names
            BAD_COMPANY_PATTERNS = [
                'multiple', 'listed', 'platforms', 'companies',
                'article', 'blog', 'guide', 'not specified',
            ]
            if any(p in company_name.lower() for p in BAD_COMPANY_PATTERNS):
                logger.debug(f'Rejected suspicious company: {company_name}')
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
                # No jobs found — revisit in 14 days in case they start hiring
                cache.set(cache_key, True, timeout=86400 * 14)

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

        time.sleep(random.uniform(0.3, 0.8))

    print(f"\n✅ Web discovery complete")
    print(f"   Queries run:     {len(SEARCH_QUERIES)}")
    print(f"   URLs scanned:    {total_urls}")
    print(f"   New jobs found:  {total_jobs}")

    return total_jobs