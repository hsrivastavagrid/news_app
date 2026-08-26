import logging
import random
import datetime
import hashlib
import time
from typing import List, Tuple

from app.models import RawArticle
from app.config import DOMAIN_TAGS, TAG_KEYWORDS, UGLY_KEYWORDS, CATEGORY_TO_TAG
from app.services.sentiment_analyzer import analyze_text
from app.services.news_fetcher import assign_tags, compute_url_hash
from app.database import db

logger = logging.getLogger("newspulse.synthesizer")

# Curated list of news source names (matching NewsAPI output format)
NEWS_SOURCES = [
    "Reuters", "Associated Press", "Bloomberg", "Financial Times",
    "BBC News", "The Wall Street Journal", "CNBC", "TechCrunch",
    "The Guardian", "The Washington Post", "Forbes", "Nature News",
    "ESPN", "Variety", "Al Jazeera", "The New York Times"
]

# Rich combinatorial templates per tag to produce ~100+ unique headlines each
TEMPLATES = {
    "politics": {
        "subjects": [
            "Senate Judiciary Committee", "Bipartisan Coalition of Lawmakers", "Supreme Court Ruling",
            "Presidential Campaign Staff", "Prime Minister", "Opposition Party Leadership",
            "Parliamentary Assembly", "Federal Election Commission", "Cabinet Ministry",
            "State Governor", "Diplomatic Envoy", "UN Security Council Delegation",
            "Legislative Oversight Panel", "Electoral Reform Board", "Government Task Force"
        ],
        "actions": [
            "Passes Comprehensive Reform Legislation", "Launches Investigation into Embezzlement Scandal",
            "Announces Bipartisan Healthcare Bill", "Approves Emergency Sanctions Package",
            "Vetoes Controversial Tax Reform Bill", "Reaches Historic Diplomatic Ceasefire Accord",
            "Debates National Defense Strategy", "Initiates Inquiry into Bribery Allegations",
            "Signs Key Bilateral Trade Agreement", "Proposes Strict Regulatory Policy Framework",
            "Deploys Security Task Force Amid Crisis", "Files Impeachment Resolution Against Officials",
            "Unveils Infrastructure Revitalization Mandate", "Rejects Coalition Policy Compromise",
            "Ratifies Global Human Rights Convention"
        ],
        "contexts": [
            "aimed at stabilizing national economic recovery.",
            "following intense multi-day debates in capital.",
            "amid growing public calls for transparency.",
            "sparking widespread controversy across political spectrum.",
            "prompting immediate response from foreign ministers.",
            "seeking to address long-standing fiscal deficits.",
            "under scrutiny from legal oversight authorities.",
            "aimed at bolstering national security infrastructure.",
            "resulting in urgent legislative sessions.",
            "amid ongoing international summit discussions."
        ]
    },
    "finance": {
        "subjects": [
            "Federal Reserve Board", "Wall Street Equity Analysts", "Global Investment Bank",
            "Central Bank Governors", "Stock Market Index", "Hedge Fund Managers",
            "Fintech Startup Venture", "International Monetary Fund", "Treasury Department",
            "Cryptocurrency Exchange", "Corporate Executive Board", "Securities and Exchange Commission",
            "Private Equity Consortium", "Bond Market Traders", "National Economic Council"
        ],
        "actions": [
            "Adjusts Benchmark Interest Rate Target", "Reports Record High Quarterly Earnings Revenue",
            "Issues Urgent Warning Over Inflation Surge", "Warns of Impending Market Recession Risks",
            "Launches Multi-Billion Dollar Corporate Merger", "Faces Federal Regulatory Fraud Investigation",
            "Unveils New Digital Currency Banking Standard", "Files Initial Public Offering on Nasdaq",
            "Surpasses Stock Market Growth Predictions", "Approves Major Financial Bailout Package",
            "Suffers Severe Dividend Paycut Following Deficit", "Executes Massive Stock Share Buyback Plan",
            "Expands International Forex Trading Operations", "Restructures Corporate Debt Liabilities",
            "Navigates Volatile Yield Curve Adjustments"
        ],
        "contexts": [
            "as global financial markets react to economic data.",
            "driving investor confidence across trading sectors.",
            "causing immediate volatility in stock indices.",
            "aimed at curbing systemic inflation pressure.",
            "following unprecedented quarterly revenue growth.",
            "sparking debate over fiscal policy intervention.",
            "amid rising interest rates and tighter credit.",
            "providing key momentum for retail investors.",
            "under supervision from financial regulators.",
            "as market liquidity conditions stabilize."
        ]
    },
    "tech": {
        "subjects": [
            "Artificial Intelligence Pioneer", "Silicon Valley Tech Giant", "Semiconductor Chip Maker",
            "Cybersecurity Defense Firm", "Cloud Infrastructure Provider", "Robotics Research Institute",
            "Quantum Computing Venture", "Autonomous Vehicle Laboratory", "Software Engineering Team",
            "SaaS Industry Leader", "Open Source Developer Community", "Tech Hardware Manufacturer",
            "Data Privacy Watchdog", "Next-Gen Microchip Consortium", "Mobile Platform Developer"
        ],
        "actions": [
            "Unveils Breakthrough AI Neural Network Architecture", "Discovers Zero-Day Security Data Breach",
            "Launches High-Performance Cloud Microprocessor", "Secures Multi-Million Dollar Seed Funding Round",
            "Deploys Autonomous Robotics in Logistics", "Faces Regulatory Fine Over Data Privacy Policy",
            "Announces Quantum Computing Speed Milestone", "Patents Next-Generation Semiconductor Wafer",
            "Integrates Machine Learning into SaaS Ecosystem", "Releases Major Software Platform Update",
            "Mitigates Massive DDoS Cyberattack Incident", "Partners with Global Tech Hardware Manufacturers",
            "Rolls Out Encryption Security Framework", "Acquires Generative AI Startup Competitor",
            "Demonstrates Real-Time Machine Translation"
        ],
        "contexts": [
            "transforming enterprise software capabilities.",
            "following rigorous security vulnerability audits.",
            "accelerating the pace of digital transformation.",
            "setting a new benchmark for processing speed.",
            "amid heightened global competition in microchips.",
            "addressing urgent cybersecurity threats nationwide.",
            "opening new frontiers for scientific computing.",
            "expanding cloud infrastructure efficiency.",
            "reinforcing consumer data protection compliance.",
            "garnering widespread acclaim across industry leaders."
        ]
    },
    "health": {
        "subjects": [
            "National Health Institute", "Pharmaceutical Research Lab", "Clinical Trial Consortium",
            "Global Health Organization", "Cancer Research Center", "Medical Diagnostics Firm",
            "Biotech Gene Therapy Lab", "Hospital Safety Board", "FDA Review Panel",
            "Epidemiology Working Group", "Mental Health Association", "Surgical Robotics Team",
            "Vaccine Development Lab", "Public Health Department", "Neurology Research Foundation"
        ],
        "actions": [
            "Announces Major Breakthrough in Target Therapy", "Launches Clinical Trial for Novel Cancer Drug",
            "Issues Emergency Advisory on Viral Outbreak", "Receives FDA Approval for Gene Therapy Protocol",
            "Publishes Landmark Study on Mental Health", "Unveils Non-Invasive Surgical Robotic System",
            "Reports Positive Results in Phase 3 Vaccine Trial", "Identifies Critical Biomarker for Early Diagnosis",
            "Allocates Emergency Funding for Hospital Supplies", "Expands Access to Telemedicine Therapeutics",
            "Discovers Novel Antibiotic Treatment Compound", "Implements Elevated Infectious Disease Protocol",
            "Partners with Pharma Leaders for Global Distribution", "Analyzes Post-Pandemic Healthcare Outcomes",
            "Initiates Nationwide Screening Campaign"
        ],
        "contexts": [
            "offering new hope for patients worldwide.",
            "after successful multi-phase human clinical trials.",
            "prompting immediate preventative health measures.",
            "marking a pivotal milestone in medical science.",
            "aimed at reducing hospital readmission rates.",
            "demonstrating exceptional efficacy and safety.",
            "supported by comprehensive medical dataset analysis.",
            "addressing critical gaps in healthcare access.",
            "under rigorous peer-reviewed scientific evaluation.",
            "improving long-term therapeutic outcomes."
        ]
    },
    "sports": {
        "subjects": [
            "National Basketball League", "Premier League Football Club", "Championship Tournament Board",
            "Olympic Committee", "Grand Slam Tennis Champions", "Formula 1 Racing Team",
            "International Cricket Board", "World Athletics Federation", "Professional Golf Association",
            "Collegiate Sports Association", "Franchise Ownership Group", "Sports Sports Commission",
            "National Football Federation", "Marathon Organizing Panel", "Sports Integrity Agency"
        ],
        "actions": [
            "Secures Thrilling Overtime Victory in Final Match", "Announces Record Multi-Year Sponsorship Acquisition",
            "Updates Conduct and Compliance Rules for League", "Shatters World Record in International Tournament",
            "Appoints Decorated Head Coach Following Victory", "Constructs State-of-the-Art Stadium Venue",
            "Dominates Playoff Series with Unbeaten Streak", "Signs Star Player to Historic Contract Extension",
            "Hosts Annual Global Sports Championship Event", "Enforces Strict Anti-Doping Regulations",
            "Clinches Title Championship in Final Round", "Reveals Updated Roster and Player Draft Picks",
            "Launches Youth Athletic Development Program", "Overcomes Second-Half Deficit to Win Cup",
            "Suspends Official Pending Disciplinary Inquiry"
        ],
        "contexts": [
            "delighting thousands of cheering fans in attendance.",
            "crowning an extraordinary undefeated season.",
            "setting high standards for athletic competition.",
            "after an intense and highly dramatic final match.",
            "marking a historic moment in franchise history.",
            "drawing record-breaking global broadcast viewership.",
            "displaying unmatched athletic skill and teamwork.",
            "establishing a new benchmark for championship play.",
            "amid enthusiastic celebrations across the city.",
            "following months of rigorous athletic training."
        ]
    },
    "science": {
        "subjects": [
            "NASA Space Research Team", "European Astronomy Observatory", "Climate Dynamics Institute",
            "Polar Ice Glacier Researchers", "Deep Sea Exploration Vessel", "Particle Physics Laboratory",
            "Astrophysics Consortium", "Renewable Energy Research Center", "Fossil Paleontology Panel",
            "Space Telescope Science Team", "Genome Mapping Initiative", "Atmospheric Carbon Institute",
            "Mars Rover Operation Command", "Oceanographic Institute", "Quantum Physics Laboratory"
        ],
        "actions": [
            "Observes Atmospheric Composition of Exoplanet", "Publishes Major Study on Polar Glacier Dynamics",
            "Discovers Fossilized Remains of Ancient Species", "Achieves Fusion Energy Net Gain Milestone",
            "Detects Gravitational Waves from Deep Space", "Maps High-Resolution Genome Sequence of Organism",
            "Deploys Deep-Space Telescope Array to Orbit", "Calculates Impact Trajectory of Near-Earth Asteroid",
            "Demonstrates High-Efficiency Solar Carbon Capture", "Traces Subatomic Particle Interactions in Collider",
            "Confirms Discovery of Water Ice Deposits on Mars", "Measures Record Ocean Temperature Transformations",
            "Uncovers New Mechanisms of Photosynthesis", "Pioneers Bio-Synthetic Renewable Materials",
            "Verifies Theoretical Physics Model via Experiment"
        ],
        "contexts": [
            "reshaping our understanding of the universe.",
            "providing vital insights into climate patterns.",
            "published today in peer-reviewed scientific journals.",
            "opening groundbreaking avenues for clean energy.",
            "utilizing advanced satellite remote sensing.",
            "confirming decades of astrophysics predictions.",
            "expanding the frontier of space exploration.",
            "highlighting urgent environmental transformation.",
            "achieved through international laboratory collaboration.",
            "offering unprecedented resolution of cosmic phenomena."
        ]
    },
    "entertainment": {
        "subjects": [
            "International Film Festival Panel", "Global Music Streaming Platform", "Hollywood Production Studio",
            "Academy Awards Committee", "Grammy Winning Recording Artist", "Box Office Analytics Group",
            "Television Streaming Network", "Broadway Theater Guild", "Cinematic Arts Academy",
            "World Concert Tour Producers", "Independent Film Directors", "Digital Media Syndicate",
            "Entertainment Industry Guild", "Music Album Production Team", "Pop Culture Critics Panel"
        ],
        "actions": [
            "Announces Winners of Prestigious Top Awards", "Shatters Global Box Office Revenue Records",
            "Releases Highly Anticipated Studio Film Trailer", "Signs Record-Breaking Digital Distribution Deal",
            "Unveils Nominees for Annual Music Awards", "Launches Global Stadium Concert Tour Series",
            "Debuts Original Drama Series to Critical Acclaim", "Premieres Groundbreaking Documentary Feature",
            "Reaches Streaming Milestone with Chart-Topping Hits", "Partners with Independent Directors for Slate",
            "Hosts Red Carpet Premiere Attended by Stars", "Ceases Production Following Creative Disputes",
            "Restructures Digital Streaming Subscription Models", "Celebrates Decades of Cinematic Excellence",
            "Captivates Audiences with Live Performance Show"
        ],
        "contexts": [
            "earning standing ovations from critics and fans.",
            "dominating headlines across global media platforms.",
            "setting new standards for digital entertainment.",
            "marking a triumph for independent filmmaking.",
            "drawing millions of streams within hours of release.",
            "celebrating artistic achievement and creativity.",
            "generating intense anticipation among worldwide audiences.",
            "bringing stellar performances to the main stage.",
            "capping a memorable season of cultural events.",
            "transforming the landscape of modern streaming."
        ]
    },
    "world": {
        "subjects": [
            "United Nations Security Council", "European Union Commission", "NATO Diplomatic Assembly",
            "Global Humanitarian Agency", "International Peacekeeping Mission", "Foreign Affairs Ministry",
            "G7 Summit Economic Council", "Border Security Task Force", "Red Cross Relief Operation",
            "International Court of Justice", "Bilateral Summit Delegation", "Refugee Aid Consortium",
            "Global Environmental Assembly", "World Health Peacekeeping Corps", "Transatlantic Alliance Group"
        ],
        "actions": [
            "Ratifies Historic Global Bilateral Treaty", "Dispatches Emergency Humanitarian Relief Aid",
            "Brokers Diplomatic Ceasefire Agreement", "Convenes Emergency Summit on International Border Crisis",
            "Imposes Strict Economic Sanctions on Rogue Regime", "Adopts Comprehensive Climate Accord Protocol",
            "Deploys Peacekeeping Forces to Conflict Zone", "Resolves Maritime Border Dispute via Arbitration",
            "Issues Joint Declaration on Foreign Policy", "Pledges Bilateral Assistance for Refugee Relief",
            "Condemns Violations of International Law", "Signs Multilateral Trade and Security Charter",
            "Establishes Demilitarized Peace Keeping Buffer Zone", "Coordinates Transatlantic Security Operations",
            "Monitors Electoral Integrity in Sovereign Nations"
        ],
        "contexts": [
            "aimed at ensuring global peace and stability.",
            "providing essential aid to displaced populations.",
            "following intensive round-the-clock negotiations.",
            "strengthening international alliances and cooperation.",
            "in response to escalating regional tensions.",
            "uniting nations around common humanitarian goals.",
            "safeguarding territorial integrity and law.",
            "addressing urgent socio-economic challenges globally.",
            "reaffirming commitment to multilateral diplomacy.",
            "marking a significant victory for international consensus."
        ]
    }
}

# Cross-Domain Keyword Injectors (to force >1 tag matches in assign_tags)
SECONDARY_MIXERS = [
    # (Primary Tag -> Secondary Keywords to append)
    ("politics", " Wall Street stock market investors closely monitor federal tax legislation policy."),
    ("politics", " UN Security Council international ceasefire diplomacy influences global oil markets."),
    ("finance", " Senate election results prompt Wall Street investors to adjust banking stock portfolios."),
    ("finance", " AI startup semiconductor chip tech launch drives Nasdaq market share earnings surge."),
    ("tech", " FDA health agency approves artificial intelligence machine learning diagnostic software."),
    ("tech", " Cybersecurity data breach investigation involves federal supreme court legal policy."),
    ("health", " Pharmaceutical stock earnings rise as clinical trial cancer treatment receives FDA approval."),
    ("health", " Global WHO scientific research team publishes genome study on viral disease outbreak."),
    ("sports", " Premier league football club earnings report highlights massive sponsorship revenue acquisition."),
    ("sports", " International Olympic committee meets with UN diplomats regarding global tournament policy."),
    ("science", " NASA space satellite carbon emission research informs global climate agreement policy."),
    ("science", " AI robotics technology research enables breakthrough deep sea genome discovery."),
    ("entertainment", " Netflix streaming technology platform reports record subscriber earnings and box office revenue."),
    ("entertainment", " Celebrity film director hosts charity concert for global international refugee relief."),
    ("world", " NATO defense summit debates technology cybersecurity policy and military funding."),
    ("world", " International trade treaty impacts global market inflation and stock investor confidence.")
]

# Crisis / Ugly keyword injectors to ensure rich Ugly Mode articles
UGLY_INJECTORS = [
    "Investigation reveals catastrophic corruption and fraud scandal inside administration.",
    "Tragic crash incident leads to devastating loss and public crisis outrage.",
    "Bribery and embezzlement scam uncovered by federal law enforcement authorities.",
    "Horrific explosion and shooting disaster prompts emergency hospital evacuation.",
    "Massacre and human rights abuse allegations spark international legal outrage."
]

def generate_raw_synthesized_articles(records_per_tag: int = 100) -> List[RawArticle]:
    """
    Synthesizes raw news articles matching the exact format from NewsAPI.org.
    
    NOTE: This function ONLY generates raw data (RawArticle objects).
    It does NOT perform sentiment analysis, tag assignment, or database storage.
    All raw articles produced here are fed directly into the standard processing pipeline,
    where sentiment_analyzer.py evaluates scores and labels identically to live API data.
    """
    win_from, win_to = db.get_rolling_window()
    dt_from = datetime.datetime.strptime(win_from, "%Y-%m-%d %H:%M:%S")

    raw_articles: List[RawArticle] = []
    article_index = 0

    logger.info("synthesizing records_per_tag=%s tags=%s", records_per_tag, len(DOMAIN_TAGS))

    for tag in DOMAIN_TAGS:
        template_data = TEMPLATES.get(tag, TEMPLATES["politics"])
        subjects = template_data["subjects"]
        actions = template_data["actions"]
        contexts = template_data["contexts"]

        count_for_tag = 0

        for s in subjects:
            for a in actions:
                if count_for_tag >= records_per_tag:
                    break

                c = random.choice(contexts)
                title = f"{s} {a}"
                description = f"Official update: {s} {a.lower()} {c}"

                # Add secondary tag mixer to ~30% of articles to create multi-tag overlaps (>1 tags)
                if count_for_tag % 3 == 0:
                    mixer_text = random.choice([m[1] for m in SECONDARY_MIXERS if m[0] == tag] or [SECONDARY_MIXERS[0][1]])
                    description += f"{mixer_text}"

                # Add ugly keyword injector to ~15% of articles to ensure Ugly mode keywords are present
                if count_for_tag % 7 == 0:
                    ugly_text = random.choice(UGLY_INJECTORS)
                    description += f" {ugly_text}"

                article_index += 1
                unique_url = f"https://newsapi.org/v2/articles/synth-{tag}-{article_index}-{hashlib.md5(title.encode()).hexdigest()[:8]}"
                source_name = random.choice(NEWS_SOURCES)
                published_at = (dt_from + datetime.timedelta(minutes=random.randint(2, 58))).strftime("%Y-%m-%d %H:%M:%S")

                # Construct standard RawArticle dataclass (matching NewsAPI.org response schema)
                raw_articles.append(
                    RawArticle(
                        title=title,
                        description=description,
                        url=unique_url,
                        source_name=source_name,
                        api_category=tag if tag in CATEGORY_TO_TAG.values() else "general",
                        image_url=None,
                        published_at=published_at,
                        url_hash=compute_url_hash(unique_url),
                    )
                )
                count_for_tag += 1

        logger.info("synthesized tag=%s count=%s", tag, count_for_tag)

    logger.info("synthesized total=%s", len(raw_articles))
    return raw_articles

def synthesize_and_process_dataset(records_per_tag: int = 100) -> int:
    """Synthesizes raw articles and passes them through the standard news processing pipeline."""
    from app.services.news_fetcher import process_raw_articles
    
    # 1. Generate pure raw articles (no sentiment scores)
    raw_articles = generate_raw_synthesized_articles(records_per_tag)
    
    # 2. Compute rolling 1-hour window for DB insertion
    win_from, win_to = db.get_rolling_window()
    dt_from = datetime.datetime.strptime(win_from, "%Y-%m-%d %H:%M:%S")
    window_fetched_at = (dt_from + datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    
    # 3. Process through standard pipeline (sentiment_analyzer.py -> assign_tags -> db)
    return process_raw_articles(raw_articles, fetched_at=window_fetched_at)

if __name__ == "__main__":
    synthesize_and_process_dataset(100)
