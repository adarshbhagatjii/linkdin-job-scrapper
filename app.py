# app.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import logging
import re
import os

# Many deployment sandboxes give the container a read-only home directory
# (e.g. /home/sbx_user1051) while /tmp stays writable. Chrome, webdriver_manager,
# and other libraries default to writing config/cache under $HOME regardless
# of --user-data-dir, so override HOME globally BEFORE anything else runs.
os.environ.setdefault('HOME', '/tmp')
os.makedirs(os.environ['HOME'], exist_ok=True)

import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── LinkedIn f_TPR values ────────────────────────────────────────────────────
RECENCY_TO_TPR = {
    '1d': 'r86400',
    '3d': 'r259200',
    '7d': 'r604800',
    '14d': 'r1209600',
    '30d': 'r2592000',
    'all': '',
}


def parse_posted_date(raw: str) -> datetime:
    """Parse LinkedIn relative date string to approximate Date"""
    now = datetime.now()
    lower = (raw or '').lower().strip()

    if not lower or lower in ['recently posted', 'just now', 'today']:
        return now

    match = re.search(r'(\d+)', lower)
    num = int(match.group(1)) if match else 0

    if 'minute' in lower or 'hour' in lower:
        return now
    if 'day' in lower:
        return now - timedelta(days=num)
    if 'week' in lower:
        return now - timedelta(weeks=num)
    if 'month' in lower:
        return now - timedelta(days=30 * num)
    if 'year' in lower:
        return now - timedelta(days=365 * num)

    return now


def strip_time(d: datetime) -> datetime:
    """Strip time component from a Date"""
    return datetime(d.year, d.month, d.day)


app = FastAPI(title="LinkedIn Job Scraper API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic Models ──────────────────────────────────────────────────────────
class JobItem(BaseModel):
    id: str
    title: str
    company: str
    location: str
    postedDate: str
    url: str
    applyLink: str


class JobResponse(BaseModel):
    success: bool
    totalJobs: int
    jobs: List[JobItem]
    searchCriteria: dict
    message: Optional[str] = None


# ─── Chrome binary detection ──────────────────────────────────────────────────
def find_chrome_binary() -> Optional[str]:
    """Locate an installed Chrome/Chromium binary. Returns None if not found —
    webdriver_manager only installs the DRIVER, never the browser itself."""
    candidates = [
        os.environ.get("CHROME_BIN"),
        os.environ.get("GOOGLE_CHROME_BIN"),
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


# ─── Driver setup (OS-agnostic) ───────────────────────────────────────────────
_cached_driver_path: Optional[str] = None


def get_chromedriver_path() -> str:
    """Resolve the ChromeDriver binary path once per process and reuse it,
    instead of re-downloading/re-resolving on every request."""
    global _cached_driver_path
    if _cached_driver_path and os.path.isfile(_cached_driver_path):
        return _cached_driver_path

    # DriverCacheManager appends its own ".wdm" subfolder to root_dir, so pass
    # the plain temp dir here (not a path already ending in .wdm) to avoid
    # nested /tmp/.wdm/.wdm/... paths.
    wdm_cache_dir = tempfile.gettempdir()
    os.makedirs(wdm_cache_dir, exist_ok=True)

    logger.info('Resolving ChromeDriver binary via webdriver_manager...')
    cache_manager = DriverCacheManager(root_dir=wdm_cache_dir)
    _cached_driver_path = ChromeDriverManager(cache_manager=cache_manager).install()
    logger.info(f'Using ChromeDriver: {_cached_driver_path}')
    return _cached_driver_path


def build_chrome_driver() -> tuple[webdriver.Chrome, str]:
    """
    Launch a headless Chrome instance that works on both local machines
    (macOS/Windows) and Linux deployment containers, with an isolated
    profile directory so concurrent requests don't collide.

    Returns (driver, user_data_dir) so the caller can clean up afterwards.
    """
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-sync')
    chrome_options.add_argument('--disable-translate')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--no-default-browser-check')
    chrome_options.add_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
    )

    # Reduce headless-automation fingerprint
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # Isolated profile dir per request — prevents "user data directory already
    # in use" crashes when multiple requests run concurrently in production.
    user_data_dir = tempfile.mkdtemp(prefix=f"chrome-profile-{uuid.uuid4()}-")
    chrome_options.add_argument(f'--user-data-dir={user_data_dir}')
    # Chrome writes disk cache and crash dumps to separate locations from
    # --user-data-dir; pin those into /tmp too so nothing falls back to a
    # read-only $HOME.
    chrome_options.add_argument(f'--disk-cache-dir={tempfile.mkdtemp(prefix="chrome-cache-")}')
    chrome_options.add_argument('--disable-crash-reporter')
    chrome_options.add_argument('--disable-breakpad')

    # Locate the Chrome/Chromium binary. webdriver_manager only installs the
    # DRIVER — the browser itself must already be present on the host (via
    # the Dockerfile's apt-get install, or a platform buildpack). Fail fast
    # with a clear message instead of letting Selenium surface a cryptic
    # "exit code 127" when chromedriver can't find a browser to launch.
    chrome_bin = find_chrome_binary()
    if not chrome_bin:
        raise RuntimeError(
            "No Chrome/Chromium binary found on this host. webdriver_manager "
            "only installs ChromeDriver, not the browser itself. If deploying "
            "via Docker, confirm your build is actually using the Dockerfile "
            "that runs 'apt-get install google-chrome-stable' and sets "
            "CHROME_BIN=/usr/bin/google-chrome — some platforms silently fall "
            "back to a native/buildpack build unless Docker is explicitly "
            "selected. If not using Docker, you must add a build step or "
            "platform-native buildpack that installs a Chrome/Chromium binary."
        )
    chrome_options.binary_location = chrome_bin
    logger.info(f'Using Chrome binary: {chrome_bin}')

    # Resolved once per process (cached), with its cache dir forced into
    # /tmp since the sandbox's home directory is read-only.
    driver_path = get_chromedriver_path()

    if not os.access(driver_path, os.X_OK):
        os.chmod(driver_path, 0o755)

    service = Service(driver_path)

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        shutil.rmtree(user_data_dir, ignore_errors=True)
        raise

    # Hide webdriver flag from page JS as an extra stealth measure
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)
    return driver, user_data_dir


# ─── Main Scraping Function ──────────────────────────────────────────────────
def scrape_linkedin_jobs(skill: str, location: str, filters: dict = None):
    """
    Scrape jobs from LinkedIn using Selenium.
    """
    driver = None
    user_data_dir = None

    try:
        if filters is None:
            filters = {}

        search_keyword = skill or 'DATASCIENCE'
        search_location = location or 'Noida'
        recency = filters.get('recency', 'all')
        tpr = 86400
        print(f"Recency filter: {recency} -> f_TPR={tpr}")
        tpr_param = f'&f_TPR={tpr}' if tpr else ''

        url = (
            f'https://www.linkedin.com/jobs/search?keywords={search_keyword}'
            f'&location={search_location}&distance=50{tpr_param}&position=1&pageNum=0'
        )

        logger.info(
            f'Fetching jobs | keyword="{search_keyword}" location="{search_location}" '
            f'recency="{recency}" tpr="{tpr or "all-time"}"'
        )
        logger.info(f'URL: {url}')

        logger.info('Launching Chrome browser...')
        driver, user_data_dir = build_chrome_driver()

        # Navigate to URL with retry logic
        logger.info('Navigating to LinkedIn jobs page...')
        max_retries = 3
        for attempt in range(max_retries):
            try:
                driver.get(url)
                logger.info('Page loaded successfully')
                break
            except Exception as e:
                logger.warning(f'Navigation attempt {attempt + 1} failed: {e}')
                if attempt == max_retries - 1:
                    raise

        time.sleep(3)

        logger.info('Waiting for job cards to load...')
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, '.job-search-card, .base-search-card')
                )
            )
            logger.info('Job cards found!')
        except Exception as e:
            logger.warning(f'Job cards timeout: {e}')

        logger.info('Extracting job data...')
        jobs = driver.execute_script('''
            const jobCards = document.querySelectorAll('.job-search-card, .base-search-card');
            const results = [];

            jobCards.forEach((card) => {
                const titleSelectors = [
                    '.job-search-card__title',
                    '.base-search-card__title',
                    '.base-card__title'
                ];
                let title = '';
                for (const selector of titleSelectors) {
                    const el = card.querySelector(selector);
                    if (el) {
                        title = el.textContent?.trim() || '';
                        break;
                    }
                }

                const companySelectors = [
                    '.job-search-card__company-name',
                    '.base-search-card__subtitle',
                    '.base-card__subtitle'
                ];
                let company = '';
                for (const selector of companySelectors) {
                    const el = card.querySelector(selector);
                    if (el) {
                        company = el.textContent?.trim() || '';
                        break;
                    }
                }

                const locationSelectors = [
                    '.job-search-card__location',
                    '.base-search-card__location',
                    '.job-card-list__location'
                ];
                let location = '';
                for (const selector of locationSelectors) {
                    const el = card.querySelector(selector);
                    if (el) {
                        location = el.textContent?.trim() || '';
                        break;
                    }
                }

                const linkEl = card.querySelector('a.base-card__full-link, a[href*="/jobs/view/"]');
                let link = '';
                if (linkEl) {
                    link = linkEl.href || '';
                    if (!link && linkEl.getAttribute('href')) {
                        const href = linkEl.getAttribute('href');
                        link = href.startsWith('http') ? href : `https://www.linkedin.com${href}`;
                    }
                }

                const dateSelectors = [
                    '.job-search-card__listdate',
                    '.job-search-card__listdate--new',
                    '.base-search-card__duration'
                ];
                let postedDate = 'Recently posted';
                for (const selector of dateSelectors) {
                    const el = card.querySelector(selector);
                    if (el) {
                        postedDate = el.textContent?.trim() || 'Recently posted';
                        break;
                    }
                }

                if (title && company) {
                    results.push({ title, company, location, postedDate, link });
                }
            });

            return results;
        ''')

        logger.info(f'Extracted {len(jobs)} jobs from page')

        driver.quit()
        driver = None
        if user_data_dir:
            shutil.rmtree(user_data_dir, ignore_errors=True)
            user_data_dir = None

        if not jobs:
            logger.warning('No jobs found - LinkedIn may have changed HTML, blocked the request, '
                            'or is challenging this IP (common on cloud/datacenter IPs).')
            return {
                'success': False,
                'totalJobs': 0,
                'jobs': [],
                'searchCriteria': {
                    'keyword': search_keyword,
                    'location': search_location,
                    'recency': recency
                },
                'message': 'No jobs found. LinkedIn may have changed their HTML structure, '
                            'blocked the request, or challenged this server\'s IP address.'
            }

        search_location_lower = search_location.lower()

        def sort_key(j):
            location_match = (j['location'] or '').lower().find(search_location_lower) >= 0
            return (not location_match, '')

        sorted_jobs = sorted(jobs, key=sort_key)

        formatted_jobs = []
        for idx, job in enumerate(sorted_jobs):
            location_match = (job['location'] or '').lower().find(search_location_lower) >= 0
            formatted_jobs.append({
                'id': f'job_{idx + 1}',
                'title': job['title'],
                'company': job['company'],
                'location': job['location'] or search_location,
                'description': f"{job['title']} position at {job['company']}",
                'postedDate': job['postedDate'],
                'url': job['link'],
                'applyLink': job['link'],
                'locationMatch': location_match
            })

        date_from = filters.get('dateFrom')
        date_to = filters.get('dateTo')

        if date_from or date_to:
            try:
                from_date = strip_time(datetime.fromisoformat(date_from)) if date_from else None
                to_date = datetime.fromisoformat(date_to) + timedelta(hours=24) if date_to else None

                filtered_jobs = []
                for job in formatted_jobs:
                    posted = parse_posted_date(job['postedDate'])
                    if from_date and posted < from_date:
                        continue
                    if to_date and posted > to_date:
                        continue
                    filtered_jobs.append(job)

                formatted_jobs = filtered_jobs
                logger.info(
                    f'Date-range filter applied [{date_from or "—"} → {date_to or "today"}]: '
                    f'{len(formatted_jobs)} jobs remaining'
                )
            except Exception as e:
                logger.warning(f'Date filter error: {e}')

        logger.info(f'Successfully scraped {len(formatted_jobs)} jobs')

        return {
            'success': True,
            'jobs': formatted_jobs,
            'totalJobs': len(formatted_jobs),
            'searchCriteria': {
                'keyword': search_keyword,
                'location': search_location,
                'recency': recency,
                'dateFrom': date_from or None,
                'dateTo': date_to or None
            },
            'source': 'LinkedIn (via Selenium)'
        }

    except Exception as e:
        logger.error(f'Error fetching from LinkedIn: {str(e)}', exc_info=True)
        return {
            'success': False,
            'totalJobs': 0,
            'jobs': [],
            'searchCriteria': {
                'keyword': skill or 'DATASCIENCE',
                'location': location or 'Noida'
            },
            'message': f'Failed to fetch jobs from LinkedIn: {str(e)}'
        }

    finally:
        # Always clean up, even on exceptions raised mid-scrape.
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        if user_data_dir:
            shutil.rmtree(user_data_dir, ignore_errors=True)


# ─── FastAPI Endpoints ──────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def home():
    """Serve the frontend chatbot UI."""
    return FileResponse("index.html")


@app.get("/jobs", response_model=JobResponse)
async def get_jobs(
    skill: str = Query(..., description="Skill or job title to search for"),
    location: str = Query(..., description="Location to search in"),
    recency: Optional[str] = Query('all', description="Recency filter: 1d, 3d, 7d, 14d, 30d, all"),
    dateFrom: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    dateTo: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)")
):
    """Fetch jobs from LinkedIn based on skill and location"""
    try:
        if not skill or len(skill.strip()) == 0:
            raise HTTPException(status_code=400, detail="Skill parameter is required")

        if not location or len(location.strip()) == 0:
            raise HTTPException(status_code=400, detail="Location parameter is required")

        skill = skill.strip()
        location = location.strip()

        filters = {
            'recency': recency or 'all',
            'dateFrom': dateFrom,
            'dateTo': dateTo
        }

        result = scrape_linkedin_jobs(skill, location, filters)
        return JobResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error in get_jobs: {str(e)}')
        return JobResponse(
            success=False,
            totalJobs=0,
            jobs=[],
            searchCriteria={"skill": skill, "location": location},
            message=f"Failed to fetch jobs: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/debug-chrome")
async def debug_chrome():
    """Diagnostic: confirms whether a Chrome/Chromium binary is actually
    installed on this host, without running a full scrape."""
    chrome_bin = find_chrome_binary()
    result = {
        "chrome_found": chrome_bin is not None,
        "chrome_path": chrome_bin,
        "CHROME_BIN_env": os.environ.get("CHROME_BIN"),
        "HOME_env": os.environ.get("HOME"),
    }
    if chrome_bin:
        try:
            import subprocess
            version_out = subprocess.run(
                [chrome_bin, "--version"], capture_output=True, text=True, timeout=10
            )
            result["chrome_version"] = version_out.stdout.strip() or version_out.stderr.strip()
        except Exception as e:
            result["chrome_version_error"] = str(e)
    return result