# app.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import logging
import re
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
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
        return now - timedelta(days=30*num)
    if 'year' in lower:
        return now - timedelta(days=365*num)
    
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

# ─── Main Scraping Function ──────────────────────────────────────────────────
def scrape_linkedin_jobs(skill: str, location: str, filters: dict = None):
    """
    Scrape jobs from LinkedIn using Selenium
    Based on Node.js jobMatching.service.js
    """
    driver = None
    
    try:
        if filters is None:
            filters = {}
        
        search_keyword = skill or 'DATASCIENCE'
        search_location = location or 'Noida'
        recency = filters.get('recency', 'all')
        tpr = RECENCY_TO_TPR.get(recency, '')
        tpr_param = f'&f_TPR={tpr}' if tpr else ''
        
        url = f'https://www.linkedin.com/jobs/search?keywords={search_keyword}&location={search_location}&distance=50{tpr_param}&position=1&pageNum=0'
        
        logger.info(f'Fetching jobs | keyword="{search_keyword}" location="{search_location}" recency="{recency}" tpr="{tpr or "all-time"}"')
        logger.info(f'URL: {url}')
        
        # Configure Chrome options for macOS ARM64
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-web-resources')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--disable-translate')
        chrome_options.add_argument('--disable-preconnect')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-media-session-api')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--no-default-browser-check')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36')
        
        # Initialize driver with proper architecture detection
        logger.info('Launching Chrome browser...')
        import os
        
        # Get the chromedriver path from webdriver-manager
        driver_path = ChromeDriverManager().install()
        
        # The install() might return a wrong path due to webdriver-manager issues
        # Let's construct the expected path manually
        driver_dir = os.path.dirname(driver_path)
        
        # The actual binary should be in chromedriver-mac-arm64 subdirectory
        actual_driver_path = os.path.join(driver_dir, 'chromedriver-mac-arm64', 'chromedriver')
        
        if not os.path.isfile(actual_driver_path):
            # Try alternative path
            actual_driver_path = os.path.join(driver_dir, '..', '..', 'chromedriver')
        
        if not os.path.isfile(actual_driver_path) or not os.access(actual_driver_path, os.X_OK):
            # Fallback: search for chromedriver in the directory tree
            for root, dirs, files in os.walk(os.path.dirname(driver_dir)):
                if 'chromedriver' in files:
                    candidate = os.path.join(root, 'chromedriver')
                    # Check if it's the binary (not a text file like THIRD_PARTY_NOTICES.chromedriver)
                    try:
                        with open(candidate, 'rb') as f:
                            header = f.read(4)
                            # ELF or Mach-O binary header
                            if header.startswith(b'\x7fELF') or header.startswith(b'\xcf\xfa\xed\xfe') or header.startswith(b'\xca\xfe\xba\xbe'):
                                actual_driver_path = candidate
                                break
                    except:
                        pass
        
        if not os.path.isfile(actual_driver_path):
            raise FileNotFoundError(f'ChromeDriver binary not found. Expected at: {actual_driver_path}')
        
        logger.info(f'Using ChromeDriver: {actual_driver_path}')
        
        # Ensure the binary is executable (webdriver-manager sometimes skips this on macOS)
        if not os.access(actual_driver_path, os.X_OK):
            logger.info('Fixing chromedriver permissions...')
            os.chmod(actual_driver_path, 0o755)
        
        service = Service(actual_driver_path)
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(10)
        
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
        
        # Wait for page to load
        time.sleep(3)
        
        # Wait for job cards
        logger.info('Waiting for job cards to load...')
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.job-search-card, .base-search-card'))
            )
            logger.info('Job cards found!')
        except Exception as e:
            logger.warning(f'Job cards timeout: {e}')
        
        # Extract job data using JavaScript
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
        
        # Close driver
        driver.quit()
        driver = None
        
        if not jobs:
            logger.warning('No jobs found - LinkedIn may have changed HTML or blocked request')
            return {
                'success': False,
                'totalJobs': 0,
                'jobs': [],
                'searchCriteria': {
                    'keyword': search_keyword,
                    'location': search_location,
                    'recency': recency
                },
                'message': 'No jobs found. LinkedIn may have changed their HTML structure or blocked the request.'
            }
        
        # Sort: exact location match first
        search_location_lower = search_location.lower()
        
        def sort_key(j):
            location_match = (j['location'] or '').lower().find(search_location_lower) >= 0
            return (not location_match, '')
        
        sorted_jobs = sorted(jobs, key=sort_key)
        
        # Format jobs
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
        
        # Apply date-range filter if provided
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
                logger.info(f'Date-range filter applied [{date_from or "—"} → {date_to or "today"}]: {len(formatted_jobs)} jobs remaining')
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
        if driver:
            try:
                driver.quit()
            except:
                pass
        
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

# ─── FastAPI Endpoints ──────────────────────────────────────────────────────

# @app.get("/")
# async def root():
#     """Root endpoint with API information"""
#     return {
#         "message": "LinkedIn Job Scraper API",
#         "version": "2.0.0",
#         "usage": "GET /jobs?skill=python&location=bangalore"
#     }
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
