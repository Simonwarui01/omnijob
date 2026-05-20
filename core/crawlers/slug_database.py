"""
Master database of verified ATS slugs for companies
that hire English-speaking task-based remote workers.
Organized by category and regularly expandable.
"""

GREENHOUSE_SLUGS = [
    # ── AI Training & Annotation ──────────────────────────
    'scaleai',          # Scale AI
    'snorkelai',        # Snorkel AI
    'labelbox',         # Labelbox
    'prolific',         # Prolific
    'remotasks',        # Remotasks
    'hive',             # Hive
    'anthropic',        # Anthropic
    'openai',           # OpenAI
    'cohere',           # Cohere
    'adept',            # Adept AI
    'inflection',       # Inflection AI
    'characterai',      # Character AI
    'midjourney',       # Midjourney
    'runway',           # Runway ML
    'stability',        # Stability AI
    'huggingface',      # HuggingFace
    'aleph-alpha',      # Aleph Alpha (Germany)
    'mistral',          # Mistral AI (France)
    'deepmind',         # Google DeepMind
    'googledeepmind',   # DeepMind alt
    'xai',              # xAI
    'perplexity',       # Perplexity AI
    'together',         # Together AI
    'replicate',        # Replicate
    'modal',            # Modal
    'anyscale',         # Anyscale
    'weights-biases',   # Weights & Biases
    'roboflow',         # Roboflow
    'v7labs',           # V7 Labs
    'superannotate',    # SuperAnnotate
    'dataloop',         # Dataloop
    'encord',           # Encord
    'segments-ai',      # Segments AI
    'kili-technology',  # Kili Technology (France)
    'hasty',            # Hasty AI
    'imerit',           # iMerit
    'sama',             # Sama (formerly Samasource)
    'cloudfactory',     # CloudFactory
    'cogito',           # Cogito
    'defined',          # Defined AI
    'surge',            # Surge AI
    'tasq',             # Tasq.ai
    'dataannotation',   # DataAnnotation

    # ── Transcription & Captioning ────────────────────────
    '3playmedia',       # 3Play Media
    'verbit',           # Verbit
    'otter',            # Otter.ai
    'assemblyai',       # AssemblyAI
    'deepgram',         # Deepgram
    'speechify',        # Speechify
    'descript',         # Descript
    'trint',            # Trint
    'sonix',            # Sonix
    'rev',              # Rev.com
    'cielo24',          # Cielo24
    'vitac',            # VITAC
    'captionmax',       # CaptionMax
    'ai-media',         # AI-Media
    'verbit-ai',        # Verbit alt
    'streamtext',       # StreamText
    'netlingo',         # NetLingo
    'captioning-key',   # Captioning Key

    # ── Translation & Localization ────────────────────────
    'smartling',        # Smartling
    'lokalise',         # Lokalise
    'crowdin',          # Crowdin
    'phrase',           # Phrase
    'transifex',        # Transifex
    'welocalize',       # Welocalize
    'transperfect',     # TransPerfect
    'lionbridge',       # Lionbridge
    'rws',              # RWS Group
    'languageline',     # LanguageLine
    'translated',       # Translated.com (Italy)
    'unbabel',          # Unbabel (Portugal)
    'lilt',             # Lilt
    'smartcat',         # Smartcat
    'localize',         # Localize
    'onehourtranslation', # One Hour Translation
    'straker',          # Straker Translations
    'thebigword',       # thebigword (UK)
    'moravia',          # Moravia (Czech)
    'keywords',         # Keywords Studios
    'localizationgroup', # Localization Group (Italy)
    'acolad',           # Acolad (France)
    'translation-agency', # Various
    'argos-multilingual', # Argos Multilingual
    'bureau-van-dijk',  # Bureau van Dijk
    'eurocom-translation', # Eurocom

    # ── Content Moderation & Trust & Safety ──────────────
    'taskus',           # TaskUs
    'concentrix',       # Concentrix
    'teleperformance',  # Teleperformance
    'foundever',        # Foundever (formerly SITEL)
    'alorica',          # Alorica
    'teletech',         # TTEC
    'conduent',         # Conduent
    'accenture',        # Accenture
    'webhelp',          # Webhelp
    'transcom',         # Transcom
    'sutherland',       # Sutherland
    'synnex',           # SYNNEX
    'ibex',             # IBEX
    'startek',          # Startek
    'arvato',           # Arvato (Germany)
    'capita',           # Capita (UK)
    'sitel',            # Sitel Group
    'pactera',          # Pactera

    # ── Voice & Audio ─────────────────────────────────────
    'heygen',           # HeyGen
    'synthesia',        # Synthesia
    'elevenlabs',       # ElevenLabs
    'murf',             # Murf AI
    'resemble',         # Resemble AI
    'voicemod',         # Voicemod
    'audo',             # Audo AI
    'cleanvoice',       # Cleanvoice
    'auphonic',         # Auphonic
    'adobe',            # Adobe
    'nuance',           # Nuance (Microsoft)

    # ── Quality Rating & Search Evaluation ───────────────
    'testlio',          # Testlio
    'utest',            # uTest
    'applause',         # Applause
    'testbirds',        # Testbirds (Germany)
    'bugfenders',       # Bugfenders
    'testerwork',       # Testerwork
    'rainforest-qa',    # Rainforest QA

    # ── Research & Usability ──────────────────────────────
    'usertesting',      # UserTesting
    'userinterviews',   # User Interviews
    'respondent',       # Respondent
    'dscout',           # dScout
    'lookback',         # Lookback
    'validately',       # Validately
    'userlytics',       # Userlytics
    'trymyui',          # TryMyUI
    'maze',             # Maze
    'useberry',         # Useberry
    'hotjar',           # Hotjar
    'fullstory',        # FullStory

    # ── Non-English Companies Hiring English Workers ──────
    # Germany
    'aleph-alpha',      # Aleph Alpha (German AI company)
    'deepl',            # DeepL (German translation)
    'idealo',           # Idealo
    'zalando',          # Zalando
    'delivery-hero',    # Delivery Hero
    'n26',              # N26
    'celonis',          # Celonis
    'personio',         # Personio
    'sumup',            # SumUp
    # France
    'mistral',          # Mistral AI
    'doctrine',         # Doctrine
    'contentsquare',    # ContentSquare
    'mirakl',           # Mirakl
    'sendinblue',       # Sendinblue
    'akeneo',           # Akeneo
    # Netherlands
    'adyen',            # Adyen
    'booking',          # Booking.com
    'messagebird',      # MessageBird
    'mollie',           # Mollie
    'sendcloud',        # Sendcloud
    # Sweden
    'spotify',          # Spotify
    'klarna',           # Klarna
    'king',             # King (Candy Crush)
    'mojang',           # Mojang
    # Japan
    'mercari',          # Mercari
    'linecorp',         # LINE Corp
    'smartnews',        # SmartNews
    # South Korea
    'kakao',            # Kakao
    'krafton',          # Krafton
    # Finland
    'supercell',        # Supercell
    'nokia',            # Nokia
    # Israel
    'wix',              # Wix
    'monday',           # Monday.com
    'fiverr',           # Fiverr
    'similarweb',       # SimilarWeb
    # India
    'freshworks',       # Freshworks
    'zoho',             # Zoho
    # Africa
    'andela',           # Andela
    'flutterwave',      # Flutterwave
    'paystack',         # Paystack
    'gebeya',           # Gebeya
]

LEVER_SLUGS = [
    'appen',            # Appen — confirmed 40 jobs
    'hive',             # Hive
    'superannotate',    # SuperAnnotate
    'defined-ai',       # Defined AI
    'surge-hq',         # Surge HQ
    'invisible',        # Invisible Technologies
    'outlier-ai',       # Outlier AI
    'scale-ai',         # Scale AI alt
    'telusinternational', # TELUS International
    'lionbridge-ai',    # Lionbridge AI
    'welocalize',       # Welocalize
    'unbabel',          # Unbabel
    'taskus',           # TaskUs
    'concentrix',       # Concentrix
    'teleperformance',  # Teleperformance
    'usertesting',      # UserTesting
    'respondent',       # Respondent
    'deepgram',         # Deepgram
    'elevenlabs',       # ElevenLabs
    'synthesia',        # Synthesia
    'heygen',           # HeyGen
    'descript',         # Descript
    'rev',              # Rev.com
    'verbit',           # Verbit
    'smartling',        # Smartling
    'lokalise',         # Lokalise
    'phrase',           # Phrase
    'lilt',             # Lilt
    'translated',       # Translated.com
    'testlio',          # Testlio
    'applause',         # Applause
    'anthropic',        # Anthropic
    'cohere',           # Cohere
    'huggingface',      # HuggingFace
    'mistral',          # Mistral AI
    'aleph-alpha',      # Aleph Alpha
    'stability-ai',     # Stability AI
    'runway',           # Runway
    'midjourney',       # Midjourney
    'perplexity-ai',    # Perplexity
]