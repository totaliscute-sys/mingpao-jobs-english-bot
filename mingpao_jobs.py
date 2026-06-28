#!/usr/bin/env python3
"""
Ming Pao Job Scraper for Primary English Teacher Positions
Scrapes job listings and sends top 3 matches via Telegram
"""

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import urllib3
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Suppress SSL warnings
urllib3.disable_warnings(InsecureRequestWarning)

# File to track sent jobs
SENT_JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mingpao_sent_jobs.json')

# Cache file for school district lookups
SCHOOL_DISTRICT_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'school_district_cache.json')

# Guard file recording the last date (HKT) a message was sent, so that multiple
# redundant scheduled runs in one day result in at most ONE Telegram message.
LAST_RUN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'last_run.json')


def hkt_today():
    """Return today's date string in Hong Kong time (UTC+8)."""
    return (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d')


def already_sent_today():
    try:
        if os.path.exists(LAST_RUN_FILE):
            with open(LAST_RUN_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('last_sent_date') == hkt_today()
    except Exception:
        pass
    return False


def mark_sent_today():
    try:
        with open(LAST_RUN_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last_sent_date': hkt_today()}, f)
    except Exception as e:
        print(f"   寫入 last_run 失敗: {e}")

# HK Districts list for matching
HK_DISTRICTS = [
    '中西區', '灣仔區', '東區', '南區', '油尖旺區', '深水埗區', 
    '九龍城區', '黃大仙區', '觀塘區', '荃灣區', '屯門區', '元朗區',
    '北區', '大埔區', '西貢區', '沙田區', '葵青區', '離島區'
]

# Hardcoded school district lookup (school name keywords -> district)
SCHOOL_DISTRICT_LOOKUP = {
    # 黃大仙區
    "ST. PATRICK'S CATHOLIC PRIMARY": "黃大仙區",
    "PO KONG VILLAGE": "黃大仙區",
    "聖博德": "黃大仙區",
    "慈雲山": "黃大仙區",
    "黃大仙": "黃大仙區",
    "鑽石山": "黃大仙區",
    "慈正": "黃大仙區",
    "慈民": "黃大仙區",
    "慈安": "黃大仙區",
    "聖文德": "黃大仙區",
    
    # 觀塘區
    "觀塘": "觀塘區",
    "藍田": "觀塘區",
    "油塘": "觀塘區",
    "秀茂坪": "觀塘區",
    "將軍澳": "西貢區",  # Note: Tseung Kwan O is actually Sai Kung
    "樂善堂": "觀塘區",
    "九龍灣": "觀塘區",
    "牛頭角": "觀塘區",
    "四順": "觀塘區",
    "聖若翰": "觀塘區",  # 九龍灣聖若翰天主教小學
    
    # 九龍城區
    "九龍城": "九龍城區",
    "土瓜灣": "九龍城區",
    "何文田": "九龍城區",
    "啟德": "九龍城區",
    "馬頭圍": "九龍城區",
    "馬頭涌": "九龍城區",
    "聖羅撒": "九龍城區",
    
    # 油尖旺區
    "油尖旺": "油尖旺區",
    "旺角": "油尖旺區",
    "尖沙咀": "油尖旺區",
    "油麻地": "油尖旺區",
    "大角咀": "油尖旺區",
    
    # 深水埗區
    "深水埗": "深水埗區",
    "長沙灣": "深水埗區",
    "石硤尾": "深水埗區",
    
    # 沙田區
    "沙田": "沙田區",
    "大圍": "沙田區",
    "火炭": "沙田區",
    "馬鞍山": "沙田區",
    "第一城": "沙田區",
    "禾輋": "沙田區",
    "沙田圍": "沙田區",
    
    # 大埔區
    "大埔": "大埔區",
    
    # 北區
    "北區": "北區",
    "上水": "北區",
    "粉嶺": "北區",
    
    # 元朗區
    "元朗": "元朗區",
    "天水圍": "元朗區",
    
    # 屯門區
    "屯門": "屯門區",
    
    # 荃灣區
    "荃灣": "荃灣區",
    "梨木樹": "荃灣區",
    "石圍角": "荃灣區",
    "三水同鄉會劉本章": "荃灣區",  # 三水同鄉會劉本章學校
    "劉本章": "荃灣區",
    
    # 葵青區
    "葵青": "葵青區",
    "葵涌": "葵青區",
    "青衣": "葵青區",
    # Note: 路德會啟聾學校 is now found via web search, not hardcoded
    
    # 西貢區
    "西貢": "西貢區",
    
    # 離島區
    "離島": "離島區",
    "大嶼山": "離島區",
    "東涌": "離島區",
    
    # 東區
    "東區": "東區",
    "筲箕灣": "東區",
    "柴灣": "東區",
    "小西灣": "東區",
    
    # 灣仔區
    "灣仔": "灣仔區",
    
    # 中西區
    "中西區": "中西區",
    "西環": "中西區",
    
    # 南區
    "南區": "南區",
    "香港仔": "南區",
    "鴨脷洲": "南區",

    # === Patched: common primary schools by full name (English / Chinese) ===
    # 灣仔區
    "MARYMOUNT PRIMARY": "灣仔區",
    "瑪利曼小學": "灣仔區",
    "ST. JOSEPH'S PRIMARY": "灣仔區",
    "聖若瑟小學": "灣仔區",
    "ROSARYHILL": "灣仔區",
    "玫瑰崗": "灣仔區",
    "ST. PAUL'S CONVENT": "灣仔區",
    "聖保祿學校": "灣仔區",
    # 油尖旺區
    "SAINT MARY'S CANOSSIAN": "油尖旺區",
    "嘉諾撒聖瑪利": "油尖旺區",
    # 中西區
    "ST. STEPHEN'S": "中西區",
    "聖士提反": "中西區",
    # 葵青區
    "SAM SHUI NATIVES": "葵青區",
    "三水同鄉會禤景榮": "葵青區",
    "禤景榮": "葵青區",
    # 深水埗區
    "ST. FRANCIS OF ASSISI'S": "深水埗區",
    "聖方濟各英文小學": "深水埗區",
    # 九龍城區
    "DIOCESAN PREPARATORY": "九龍城區",
    "拔萃小學": "九龍城區",
    "LA SALLE PRIMARY": "九龍城區",
    "喇沙小學": "九龍城區",
    "MARYKNOLL CONVENT": "九龍城區",
    "瑪利諾修院": "九龍城區",
    "HOLY FAMILY CANOSSIAN": "九龍城區",
    "嘉諾撒聖家": "九龍城區",
    # 沙田區
    "BAPTIST LUI MING CHOI": "沙田區",
    "浸信會呂明才": "沙田區",
    # 觀塘區
    "LING LIANG CHURCH M H LAU": "觀塘區",
    "靈糧堂劉梅軒": "觀塘區",
    # 離島區
    "LING LIANG CHURCH SAU TAK": "離島區",
    "靈糧堂秀德": "離島區",
    # 東區
    "QUARRY BAY SCHOOL": "東區",
}


def load_district_cache():
    """Load cached school district lookups"""
    try:
        if os.path.exists(SCHOOL_DISTRICT_CACHE_FILE):
            with open(SCHOOL_DISTRICT_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"   讀取地區緩存錯誤: {e}")
    return {}


def save_district_cache(cache):
    """Save school district cache to file"""
    try:
        with open(SCHOOL_DISTRICT_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"   保存地區緩存錯誤: {e}")


def search_web_for_district(school_name):
    """
    Search for school district information using web search.
    Returns district name or None if not found.
    """
    try:
        # Try Tavily API first if available
        tavily_key = os.environ.get('TAVILY_API_KEY')
        if tavily_key:
            search_query = f"{school_name} 地址 香港 地區 district"
            headers = {'Authorization': f'Bearer {tavily_key}'}
            payload = {
                'query': search_query,
                'max_results': 5,
                'include_answer': True
            }
            
            resp = requests.post('https://api.tavily.com/search',
                               headers=headers, json=payload, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get('answer', '')
                results = data.get('results', [])
                
                # Combine answer and results for district extraction
                search_text = answer + ' ' + ' '.join([r.get('content', '') for r in results]) + ' ' + ' '.join([r.get('title', '') for r in results])
                search_text = search_text.upper()
                
                # District mapping for English names
                district_map = {
                    'CENTRAL AND WESTERN': '中西區',
                    'CENTRAL & WESTERN': '中西區',
                    'WAN CHAI': '灣仔區',
                    'EASTERN': '東區',
                    'SOUTHERN': '南區',
                    'YAU TSIM MONG': '油尖旺區',
                    'SHAM SHUI PO': '深水埗區',
                    'KOWLOON CITY': '九龍城區',
                    'WONG TAI SIN': '黃大仙區',
                    'KWUN TONG': '觀塘區',
                    'TSUEN WAN': '荃灣區',
                    'TUEN MUN': '屯門區',
                    'YUEN LONG': '元朗區',
                    'NORTH': '北區',
                    'TAI PO': '大埔區',
                    'SAI KUNG': '西貢區',
                    'SHA TIN': '沙田區',
                    'KWAI TSING': '葵青區',
                    'ISLANDS': '離島區'
                }
                
                # Check for English district names first (more specific)
                for eng_name, chinese_name in district_map.items():
                    if eng_name in search_text:
                        return chinese_name
                
                # Then check for Chinese district names
                for district in HK_DISTRICTS:
                    if district in search_text:
                        return district
                    # Try without 區 suffix
                    district_no_suffix = district.replace('區', '')
                    if district_no_suffix in search_text:
                        return district
        
        # Fallback: Try school info websites
        from urllib.parse import quote
        
        # Try schooland.hk
        try:
            schooland_url = f"https://www.schooland.hk/search?search={quote(school_name)}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(schooland_url, headers=headers, timeout=10, verify=False)
            
            if resp.status_code == 200:
                content = resp.text.upper()
                # Check English district names first
                for eng_name, chinese_name in district_map.items():
                    if eng_name in content:
                        return chinese_name
                # Then check Chinese
                for district in HK_DISTRICTS:
                    if district.upper() in content:
                        return district
        except:
            pass
        
        # Try openschool.hk
        try:
            openschool_url = f"https://www.openschool.hk/school/primary/{quote(school_name)}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(openschool_url, headers=headers, timeout=10, allow_redirects=True, verify=False)
            
            if resp.status_code == 200:
                content = resp.text.upper()
                # Check English district names first
                for eng_name, chinese_name in district_map.items():
                    if eng_name in content:
                        return chinese_name
                # Then check Chinese
                for district in HK_DISTRICTS:
                    if district.upper() in content:
                        return district
        except:
            pass
        
    except Exception as e:
        print(f"   網上搜尋地區錯誤: {e}")
    
    return None

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
# Read from the TELEGRAM_CHAT_ID secret (no hard-coded fallback, so the chat ID
# is not exposed if the repo is made public).
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
BASE_URL = "https://jump.mingpao.com"
SEARCH_URL = f"{BASE_URL}/job/search/Jobs"

# Keywords
KEYWORDS = ["english", "英文", "英文科", "English Teacher", "老師", "教師", "老師", "英文教師"]

# --- Performance / search-depth tuning ---
NUM_PAGES = 12          # listing pages to scan (more = searches further back)
FETCH_WORKERS = 4       # parallel HTTP workers for fetching job-detail pages
                        # (kept low: requests go through a single WireGuard VPN
                        # tunnel, which drops connections under high concurrency)
PAGE_SLEEP = 0.3        # seconds between listing-page fetches
# Date windows (hours) tried in order until we have >=3 jobs; widened well past
# 7 days so the bot keeps searching further when recent posts are scarce.
SEARCH_WINDOWS = [24, 48, 72, 168, 336, 720]  # 1d, 2d, 3d, 7d, 14d, 30d
MIN_JOBS = 3            # target number of jobs to send

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-HK,zh;q=0.9,en;q=0.8',
}


def send_telegram_message(message):
    """Send message via Telegram bot"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return None


def fetch_page(url, params=None):
    """Fetch page with retries"""
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=30, verify=False)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    return None


def parse_job_date(date_text):
    """Parse job posting date like '23 Apr 26' into datetime"""
    if not date_text:
        return None
    try:
        # Clean up the text
        date_text = date_text.strip()
        # Parse formats like "23 Apr 26" or "23 Apr 2026"
        for fmt in ['%d %b %y', '%d %b %Y', '%d %B %y', '%d %B %Y']:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue
    except Exception as e:
        print(f"   Error parsing date '{date_text}': {e}")
    return None


def parse_job_listings(html):
    """Parse job listings from HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    jobs = []
    
    # Look for job listings in the #jobListing element
    job_listing = soup.find('ul', id='jobListing')
    
    if job_listing:
        items = job_listing.find_all('li', {'adid': True})
        print(f"   Found {len(items)} job items in #jobListing")
        
        for item in items:
            try:
                # Extract AdID
                ad_id = item.get('adid', '')
                
                # Find job title link
                title_link = item.find('a', href=re.compile(r'/job/'))
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                job_url = title_link['href']
                if not job_url.startswith('http'):
                    job_url = f"{BASE_URL}{job_url}"
                
                # Find school/company name - look for link with CustNo
                school = "Unknown"
                school_link = item.find('a', href=re.compile(r'CustNo='))
                if school_link:
                    school = school_link.get_text(strip=True)
                else:
                    # Fallback: look for company name in various places
                    school_elem = item.find(['span', 'div'], class_=re.compile('company|school|employer', re.I))
                    if school_elem:
                        school = school_elem.get_text(strip=True)
                    else:
                        # Try to find in the item text after the title
                        item_text = item.get_text(separator=' ', strip=True)
                        lines = [l.strip() for l in item_text.split('\n') if l.strip()]
                        if len(lines) > 1:
                            school = lines[1] if len(lines[1]) < 50 else "Unknown"
                
                # Extract posted date
                posted_date = None
                date_elem = item.find('span', class_=re.compile('date|posted', re.I))
                if date_elem:
                    posted_date = parse_job_date(date_elem.get_text(strip=True))
                else:
                    # Try to find date pattern in text
                    date_match = re.search(r'(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})', item.get_text())
                    if date_match:
                        posted_date = parse_job_date(date_match.group(1))
                
                jobs.append({
                    'title': title,
                    'school': school,
                    'url': job_url,
                    'ad_id': ad_id,
                    'posted_date': posted_date,
                    'full_text': item.get_text(separator=' ', strip=True)
                })
            except Exception as e:
                print(f"   Error parsing item: {e}")
                continue
    
    # Alternative: look for any links with /job/ in href
    if not jobs:
        job_links = soup.find_all('a', href=re.compile(r'/job/\d+'))
        seen = set()
        for link in job_links:
            href = link.get('href', '')
            if href in seen:
                continue
            seen.add(href)
            
            title = link.get_text(strip=True)
            job_url = href if href.startswith('http') else f"{BASE_URL}{href}"
            
            jobs.append({
                'title': title,
                'school': 'Unknown',
                'url': job_url,
                'full_text': title
            })
    
    return jobs


def matches_keywords(text):
    """Check if text matches any keywords"""
    if not text:
        return False, None
    text_lower = text.lower()
    for keyword in KEYWORDS:
        if keyword.lower() in text_lower:
            return True, keyword
    return False, None


def is_secondary_school(text):
    """Check if text indicates secondary school - used for exclusion"""
    if not text:
        return False
    secondary_indicators = ['secondary', '中學', 'college', '中學部']
    return any(ind in text.lower() for ind in secondary_indicators)


def is_primary_school(text):
    """Check if text indicates primary school"""
    if not text:
        return False
    indicators = ['小學', 'primary', 'p.s.', '小一至小六', '小學部']
    return any(ind in text.lower() for ind in indicators)


def is_confirmed_primary_school(school_name, content, title=''):
    """
    STRICT PRIMARY ONLY filter.
    Considers the job TITLE as well as the school name — many primary posts
    (e.g. 助理小學學位教師 / APSM, 小學學位教師) state 小學 in the title even when
    the employer name or detail page does not literally contain 小學/primary.
    Excludes jobs that clearly indicate secondary (中學/secondary) without any
    primary indicator. Returns True if primary indicators are found in the
    title, school name, OR content.
    """
    # Title is the strongest signal for APSM-style government/aided posts whose
    # employer name omits 小學, so check it together with the school name.
    name_text = f"{title} {school_name}".strip()
    if not name_text:
        return False

    has_secondary = is_secondary_school(name_text)
    has_primary = is_primary_school(name_text)

    # Secondary indicated and no primary indicator anywhere in title/name -> exclude
    if has_secondary and not has_primary:
        return False

    # Accept if primary indicators in title or school name (strong signal)
    if has_primary:
        return True

    # Otherwise check content if available
    if content and is_primary_school(content):
        return True

    return False


# Non-teaching roles to exclude
NON_TEACHING_KEYWORDS = [
    '文書助理', '行政主任', '庶務', '校工', '言語治療', '社工', '書記', '文員',
    '秘書', '司機', '保安', '清潔', '校務處', '實驗室技術員', '圖書館助理',
    '資訊科技員', '網頁管理', '總務', '會計', '出納', '人事', '維修',
    '助理員', '協調員', '校巴', '電腦技術',
    'clerk', 'admin', 'secretary', 'driver', 'security', 'cleaner',
    'assistant (non-teaching)', 'technician', 'librarian assistant'
]

# Substitute/temporary teacher keywords to reject
SUBSTITUTE_KEYWORDS = [
    '代課', '供替', '日薪代課', '短期代課',
    'substitute', 'relief teacher', 'supply teacher',
]

# Support / assistant (NON-degree) roles to reject.
# The user wants APSM (助理小學學位教師, a registered degree teacher), NOT teaching
# assistants / support teachers. These keywords are chosen so they do NOT match
# the APSM title "助理小學學位教師" (it contains neither "教學助理" nor "助理教師").
SUPPORT_ROLE_KEYWORDS = [
    '教學助理', '助教', '助理教師', '支援教師', '支援老師', '學習支援', '副教師',
    'teaching assistant', 'teacher assistant', 'associate teacher',
    'support teacher', 'learning support',
]

# Teaching role indicators (TA / teaching assistant deliberately excluded — see
# SUPPORT_ROLE_KEYWORDS — because the user only wants degree teachers / APSM).
TEACHING_KEYWORDS = [
    '教師', '老師', 'teacher',
    '學位教師', '小學學位教師', '助理小學學位教師', 'APSM', 'GM', 'SGM', 'PSM',
    '學位教師', '常額教師', '合約教師', '代課教師', '日薪代課'
]


def is_support_role(title):
    """Check if the job is a (non-degree) teaching-assistant / support role to reject."""
    text = (title or '').lower()
    for keyword in SUPPORT_ROLE_KEYWORDS:
        if keyword.lower() in text:
            return True, keyword
    return False, None

# Social service organization keywords to exclude
SOCIAL_SERVICE_KEYWORDS = [
    '服務處', '社會服務', '基督教服務', '社福', 'NGO', '非政府機構',
    '服務中心', '福利會', '善會', '慈善', '社工服務'
]

# Special school keywords (for adding note)
SPECIAL_SCHOOL_KEYWORDS = [
    '啟聾', '聾', '盲', '特殊', '匡智', '明愛', '扶康會',
    'deaf', 'blind', 'special school'
]


def is_social_service_org(school_name):
    """Check if employer is a social service organization (not a school)"""
    if not school_name:
        return True  # Reject if no school name
    
    # Must contain school-related keywords
    school_keywords = ['學校', '小學', 'primary', 'school', '小學部']
    has_school_keyword = any(kw in school_name.lower() for kw in school_keywords)
    
    # Check for social service keywords
    for kw in SOCIAL_SERVICE_KEYWORDS:
        if kw in school_name:
            return True  # It's a social service org
    
    return not has_school_keyword  # Reject if no school keyword


def is_special_school(school_name):
    """Check if school is a special school for adding note"""
    if not school_name:
        return False
    school_lower = school_name.lower()
    return any(kw in school_lower for kw in SPECIAL_SCHOOL_KEYWORDS)


def deduplicate_jobs(jobs):
    """Remove duplicate jobs with same school+title combination"""
    seen = {}
    unique_jobs = []
    
    for job in jobs:
        key = f"{job.get('school', '')}|{job.get('title', '')}"
        if key not in seen:
            seen[key] = job
            unique_jobs.append(job)
        else:
            # Keep the one with more recent date if available
            existing = seen[key]
            if job.get('posted_date') and existing.get('posted_date'):
                if job['posted_date'] > existing['posted_date']:
                    seen[key] = job
                    unique_jobs.remove(existing)
                    unique_jobs.append(job)
    
    return unique_jobs


def is_non_teaching_role(title):
    """Check if the job is a non-teaching role - only check title"""
    text = title.lower()
    for keyword in NON_TEACHING_KEYWORDS:
        if keyword.lower() in text:
            return True, keyword
    return False, None


def is_teaching_role(title, content=''):
    """Check if the job is clearly a teaching position"""
    title_lower = title.lower()
    
    # First check title for non-teaching roles
    is_non_teaching, matched_keyword = is_non_teaching_role(title)
    if is_non_teaching:
        return False, f"non-teaching:{matched_keyword}"
    
    # Check title for teaching indicators (strong signal)
    for keyword in TEACHING_KEYWORDS:
        if keyword.lower() in title_lower:
            return True, f"teaching:{keyword}"
    
    # If not found in title, check content as fallback
    if content:
        content_lower = content.lower()
        for keyword in TEACHING_KEYWORDS:
            if keyword.lower() in content_lower:
                return True, f"teaching-in-content:{keyword}"
    
    return False, "no-teaching-keyword"


# Other subjects to check against (if these appear in title, it's not English)
OTHER_SUBJECTS = [
    # 中文 (Chinese)
    '中文科', '中文教師', '中文老師', '中文', 'chinese teacher', 'chinese',
    # 數學 (Math)
    '數學科', '數學', 'math teacher', 'mathematics', 'maths',
    # 常識 / 通識
    '常識', '通識',
    # 音樂 (Music)
    '音樂', 'music teacher',
    # 體育 (PE / Physical)
    '體育', 'physical teacher', 'physical education', 'pe teacher', 'p.e.',
    # 視藝 (Art)
    '視藝', '美術', 'art teacher', 'visual arts',
    # 科學 / STEM
    '科學', 'science teacher', 'stem',
    # 電腦 / IT
    '電腦', '資訊科技', 'ict teacher', 'computer',
    # 其他
    '地理', 'geography', '歷史', 'history', '生物', 'biology',
    '化學', 'chemistry', '物理', 'physics', '普通話', 'putonghua',
    '公社', '經濟', 'economics', '會計', 'accounting', 'bafs',
    # 宗教 (Religious)
    '宗教', '聖經', 'religious studies',
]


def is_english_subject(title, content=''):
    """
    Check if job is for English subject.
    
    Logic:
    1. If title contains 英文/English → auto confirmed
    2. If title has teaching keywords (學位教師/APSM/GM) but no subject mentioned → 
       MUST check content and find English keywords to confirm
    3. If content fetch fails or no English found → REJECT (must explicitly confirm English)
    """
    if not title:
        return False, 'no_title'

    # LEVEL 0: Reject NET (Native English Teacher) postings.
    import re as _net_re
    if _net_re.search(r'\bNET\b', title):
        return False, 'title_is_net_teacher'
    _net_phrases = [
        'native speaking english teacher',
        'native-speaking english teacher',
        'native english teacher',
        '外籍英語教師',
        '外籍英文教師',
        '外籍英語老師',
        '外籍英文老師',
    ]
    _t_lower = title.lower()
    for _ph in _net_phrases:
        if _ph in _t_lower:
            return False, 'title_is_net_teacher'

    title_lower = title.lower()
    content_lower = content.lower() if content else ''
    
    # LEVEL 1: Title explicitly mentions English → AUTO CONFIRMED
    english_in_title = any(kw in title_lower for kw in ['english', '英文科', '英文教師', '英文老師', 'english teacher', '教英文', '任教英文'])
    if english_in_title:
        return True, 'title_has_english'
    
    # LEVEL 2: Title has teaching role but no specific subject → MUST CHECK CONTENT FOR ENGLISH
    teaching_keywords = ['學位教師', 'apsm', 'gm', 'sgm', 'psm', '老師', '教師', 'teacher']
    has_teaching_keyword = any(kw in title_lower for kw in teaching_keywords)
    
    # Check if title mentions OTHER subjects (if so, it's not English)
    has_other_subject = any(subj.lower() in title_lower for subj in OTHER_SUBJECTS)
    
    if has_teaching_keyword and not has_other_subject:
        # Check content for English - MUST find an EXPLICIT English-SUBJECT signal.
        # NOTE: a bare "english" / "英文" in the description is NOT enough — almost
        # every HK teaching post asks for "good command of English", which used to
        # cause generic posts (e.g. 支援教師/TA) to be mis-classified as English.
        if content and len(content) > 100:
            english_subject_signals = [
                '英文科', '英語科', '英文教師', '英文老師', '英語教師', '英語老師',
                '教英文', '任教英文', '教授英文', '英文課', '英文班',
                'english teacher', 'teach english', 'teaching of english',
                'english panel', 'english subject', 'english language teacher',
                'subject teacher (english)', 'subject: english', 'panel (english)',
            ]
            content_has_english = any(kw in content_lower for kw in english_subject_signals)
            if content_has_english:
                return True, 'content_has_english'
            else:
                # Content exists but NO English found - REJECT
                return False, 'content_no_english'
        else:
            # Content fetch failed or empty - CANNOT confirm English, REJECT
            return False, 'content_failed_cannot_confirm_english'
    
    # LEVEL 3: Title has other subject → REJECT
    if has_other_subject:
        return False, 'title_has_other_subject'
    
    return False, 'not_english_role'


def strip_html_tags(text):
    """Remove all HTML tags from text"""
    if not text:
        return ""
    # Use regex to remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip()


def fetch_job_details(url):
    """Fetch and parse job detail page"""
    html = fetch_page(url)
    if not html:
        return {'content': '', 'salary': 'Not specified'}
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract content - try multiple selectors
    content = ""
    
    # Try job description container
    content_elem = soup.find('div', class_=re.compile('job-detail|jobDescription|job-desc', re.I))
    if content_elem:
        content = content_elem.get_text(separator=' ', strip=True)
    
    # Try main content area
    if not content:
        content_elem = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile('content|main', re.I))
        if content_elem:
            content = content_elem.get_text(separator=' ', strip=True)
    
    # Fallback: get all text from body
    if not content:
        body = soup.find('body')
        if body:
            content = body.get_text(separator=' ', strip=True)
    
    # Extract salary - look for salary section
    salary = "Not specified"
    
    # Try to find salary in specific elements
    salary_elem = soup.find(string=re.compile(r'(薪金|月薪|Salary)', re.I))
    if salary_elem:
        # Get parent element text
        parent = salary_elem.parent
        if parent:
            salary_text = parent.get_text(strip=True)
            # Extract text after the label
            salary_match = re.search(r'(薪金|月薪|Salary)[：:\s]*([^\n<]+)', salary_text, re.I)
            if salary_match:
                salary = strip_html_tags(salary_match.group(2)).strip()
    
    # Fallback: regex on full HTML
    if salary == "Not specified":
        salary_match = re.search(r'(薪金|月薪|Salary)[：:\s]*([^\n<]+)', html, re.I)
        if salary_match:
            salary = strip_html_tags(salary_match.group(2)).strip()[:50]
    
    return {'content': content, 'salary': salary}


def search_school_info(school_name):
    """
    Determine school type and district from school name.
    Uses naming patterns instead of web search for reliability.
    """
    # Get school type from name patterns
    result = infer_school_info_from_name(school_name)
    
    # Try web search for district only (school type is already determined)
    try:
        import os
        tavily_key = os.environ.get('TAVILY_API_KEY')
        
        if tavily_key:
            search_query = f"{school_name} Hong Kong primary school district 地區"
            
            headers = {'Authorization': f'Bearer {tavily_key}'}
            payload = {
                'query': search_query,
                'max_results': 3,
                'include_answer': True
            }
            
            resp = requests.post('https://api.tavily.com/search',
                               headers=headers, json=payload, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get('answer', '').lower()
                
                # Extract district
                district = None
                district_patterns = [
                    r'(中西區|灣仔區|東區|南區|油尖旺區|深水埗區|九龍城區|黃大仙區|觀塘區|荃灣區|屯門區|元朗區|北區|大埔區|西貢區|沙田區|葵青區|離島區)',
                    r'(kwun tong|wong tai sin|kowloon city|sha tin|tuen mun|yuen long|tai po|sai kung|central|wan chai|eastern|southern|yau tsim mong|sham shui po|tsuen wan|kwai tsing|islands)',
                ]
                for pattern in district_patterns:
                    match = re.search(pattern, answer, re.I)
                    if match:
                        district = match.group(1)
                        break
                
                # District mapping
                district_map = {
                    'central': '中西區', 'wan chai': '灣仔區', 'eastern': '東區', 'southern': '南區',
                    'yau tsim mong': '油尖旺區', 'sham shui po': '深水埗區', 'kowloon city': '九龍城區',
                    'wong tai sin': '黃大仙區', 'kwun tong': '觀塘區', 'tsuen wan': '荃灣區',
                    'tuen mun': '屯門區', 'yuen long': '元朗區', 'north': '北區', 'tai po': '大埔區',
                    'sai kung': '西貢區', 'sha tin': '沙田區', 'kwai tsing': '葵青區', 'islands': '離島區'
                }
                if district and district.lower() in district_map:
                    result['district'] = district_map[district.lower()]
        
    except Exception as e:
        pass  # Silently fail, we already have the type from name
    
    return result


# Global cache for district lookups (loaded once)
_district_cache = None

def get_district_cache():
    """Get or load the district cache"""
    global _district_cache
    if _district_cache is None:
        _district_cache = load_district_cache()
    return _district_cache


def infer_school_info_from_name(school_name):
    """
    Determine school type and district from school name.
    First tries web search with caching, then falls back to hardcoded dictionary.
    Returns dict with type_chinese and district.
    """
    name = school_name.upper()
    name_lower = school_name.lower()
    
    # Get cache
    cache = get_district_cache()
    
    # Check cache first
    if school_name in cache:
        district = cache[school_name]
        print(f"      📍 地區緩存: {district}")
    else:
        # Try web search
        district = None
        web_district = search_web_for_district(school_name)
        if web_district:
            district = web_district
            cache[school_name] = district
            save_district_cache(cache)
            print(f"      🔍 網上搜尋地區: {district}")
        else:
            # Fallback to hardcoded dictionary
            district = '未知地區'
            for keyword, dist in SCHOOL_DISTRICT_LOOKUP.items():
                if keyword.upper() in name:
                    district = dist
                    break
            if district != '未知地區':
                print(f"      📖 字典查找: {district}")
    
    # 1. Contains "官立" → 官立小學
    if '官立' in name:
        return {'type_chinese': '官立小學', 'district': district}
    
    # 2. Contains religious indicators → 津貼小學
    religious_indicators = ['天主教', '聖', '基督教', '循道', '信義', '浸信', '佛教', '孔教', '伊斯蘭', '宣道']
    for indicator in religious_indicators:
        if indicator in name:
            return {'type_chinese': '津貼小學', 'district': district}
    
    # 3. Contains "直資" → 直資小學
    if '直資' in name or 'dss' in name_lower:
        return {'type_chinese': '直資小學', 'district': district}
    
    # 4. Contains "私立/國際" → 私立小學
    if '私立' in name or 'private' in name_lower or '國際' in name:
        return {'type_chinese': '私立小學', 'district': district}
    
    # 5. Default → 津貼小學 (most HK primary schools are aided)
    return {'type_chinese': '津貼小學', 'district': district}


def load_sent_jobs():
    """Load list of already sent job URLs"""
    try:
        if os.path.exists(SENT_JOBS_FILE):
            with open(SENT_JOBS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
    except Exception as e:
        print(f"   讀取已發送職位記錄錯誤: {e}")
    return set()


def save_sent_jobs(sent_urls):
    """Save list of sent job URLs"""
    try:
        with open(SENT_JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(sent_urls), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"   保存已發送職位記錄錯誤: {e}")


def filter_jobs_by_date(jobs, hours=24):
    """Filter jobs posted within the last N hours"""
    cutoff = datetime.now() - timedelta(hours=hours)
    return [job for job in jobs if job.get('posted_date') and job['posted_date'] >= cutoff]


def rank_jobs(jobs):
    """
    Rank jobs and return top 3, preferring variety (one job per school when possible).
    """
    for job in jobs:
        score = 0
        reasons = []
        
        if job.get('is_primary'):
            score += 5
            reasons.append("✓ Primary")
        
        if job.get('is_english'):
            score += 5
            reasons.append("✓ English")
        
        if job.get('is_primary') and job.get('is_english'):
            score += 3
            reasons.append("✓ Primary English")
        
        # Bonus for having English explicitly in title
        title = job.get('title', '').lower()
        if any(kw in title for kw in ['english', '英文科', '英文教師', '英文老師']):
            score += 2
            reasons.append("✓ Title has English")
        
        job['score'] = score
        job['match_reasons'] = reasons
    
    # Sort by score
    jobs.sort(key=lambda x: x['score'], reverse=True)
    
    # Prefer variety: take best job from each school first
    selected = []
    schools_seen = set()
    
    for job in jobs:
        school = job.get('school', '')
        if school not in schools_seen:
            selected.append(job)
            schools_seen.add(school)
            if len(selected) >= 3:
                break
    
    # If we don't have 3 jobs from different schools, fill with remaining best jobs
    if len(selected) < 3:
        for job in jobs:
            if job not in selected:
                selected.append(job)
                if len(selected) >= 3:
                    break
    
    return selected


def escape_html(text):
    """Escape HTML special characters"""
    if not text:
        return ""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def format_chinese_date(date_obj):
    """Format date as 2026年4月23日"""
    if not date_obj:
        return "未知日期"
    return f"{date_obj.year}年{date_obj.month}月{date_obj.day}日"


def format_message(jobs, search_hours=24):
    """Format Telegram message in Traditional Chinese"""
    today = datetime.now().strftime("%Y年%m月%d日")
    msg = f"<b>📚 小學英文科教師職位</b>\n<i>更新日期：{today}</i>\n"
    
    if search_hours is None:
        msg += "<i>搜尋範圍：所有可用職位</i>\n\n"
    elif search_hours > 24:
        days = search_hours // 24
        msg += f"<i>搜尋範圍：過去{days}天</i>\n\n"
    else:
        msg += "\n"
    
    if not jobs:
        msg += "<i>暫無符合條件的小學英文科教師職位</i>\n\n"
        msg += "<i>來源：明報 JUMP</i>"
        return msg
    
    for i, job in enumerate(jobs, 1):
        info = job.get('school_info', {})
        title = escape_html(job['title'][:50])
        school = escape_html(job['school'])
        school_type = escape_html(info.get('type_chinese', '小學'))
        district = escape_html(info.get('district', '未知地區'))
        posted_date = format_chinese_date(job.get('posted_date'))
        
        # Add special school note
        special_note = ""
        if job.get('is_special_school'):
            special_note = " 🏷 特殊學校"

        # Mark top-up jobs that were sent in a previous run
        repeat_note = " 🔁 已發過" if job.get('already_sent') else ""

        msg += f"<b>#{i} {title}</b>{repeat_note}\n"
        msg += f"🏫 {school}{special_note}\n"
        msg += f"🏛 {school_type}\n"
        msg += f"📍 {district}\n"
        msg += f"📅 {posted_date}\n"
        msg += f"🔗 <a href='{job['url']}'>查看職位</a>\n\n"
    
    msg += "<i>來源：明報 JUMP</i>"
    return msg


# Cache of fetched job-detail pages keyed by URL (avoids re-fetching across passes)
_detail_cache = {}


def prefetch_details(jobs):
    """Fetch all job-detail pages in PARALLEL and attach content/salary to jobs.

    This is the single biggest speed-up: previously each date window re-fetched
    the same detail pages sequentially (10x+ redundant work). Now every unique
    job is fetched exactly once, concurrently.
    """
    to_fetch = [j for j in jobs if j['url'] not in _detail_cache]
    print(f"\n🌐 並行抓取 {len(to_fetch)} 個職位詳情 ({FETCH_WORKERS} workers)...")
    if to_fetch:
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
            future_map = {ex.submit(fetch_job_details, j['url']): j['url'] for j in to_fetch}
            for fut in as_completed(future_map):
                url = future_map[fut]
                try:
                    _detail_cache[url] = fut.result()
                except Exception as e:
                    print(f"   抓取失敗 {url}: {e}")
                    _detail_cache[url] = {'content': '', 'salary': 'Not specified'}
    for j in jobs:
        d = _detail_cache.get(j['url'], {'content': '', 'salary': 'Not specified'})
        j['content'] = d['content']
        j['salary'] = d['salary']


def classify_jobs(jobs, sent_jobs):
    """Run each (already detail-fetched) job through the full filter pipeline ONCE.

    Returns (verified, debug_results). Network is only hit here for the district
    lookup of ACCEPTED jobs (search_school_info), so this pass is fast.
    """
    verified = []
    debug_results = []

    def reject(job_title, school, reason):
        debug_results.append({'title': job_title, 'school': school[:30],
                              'status': 'REJECTED', 'reason': reason})

    for job in jobs:
        job_title = job['title'][:50]
        content = job.get('content', '') or ''
        # Tag (don't skip) already-sent jobs, so they can be used to top up to
        # MIN_JOBS when there aren't enough brand-new ones.
        job['already_sent'] = job['url'] in sent_jobs

        # Teaching role?
        is_teaching, teaching_reason = is_teaching_role(job['title'], content)
        if not is_teaching:
            reject(job_title, job['school'], f'非教學職位 ({teaching_reason})')
            continue

        # Reject teaching-assistant / support (non-degree) roles — user wants APSM only.
        is_support, support_kw = is_support_role(job['title'])
        if is_support:
            reject(job_title, job['school'], f'助理/支援職位 ({support_kw})')
            continue

        # Reject substitute / temporary teacher roles
        _sub_match = next((kw for kw in SUBSTITUTE_KEYWORDS if kw in job['title'].lower()), None)
        if _sub_match:
            reject(job_title, job['school'], f'代課職位 ({_sub_match})')
            continue

        # Primary school? (title is the strongest signal for APSM posts)
        if not is_confirmed_primary_school(job['school'], content, job['title']):
            reject(job_title, job['school'], '非小學')
            continue

        # Must be an actual school, not a social-service org
        if is_social_service_org(job['school']):
            reject(job_title, job['school'], '社會服務機構')
            continue

        job['is_special_school'] = is_special_school(job['school'])

        # English subject?
        is_english, english_reason = is_english_subject(job['title'], content)
        job['is_primary'] = True
        job['is_english'] = is_english

        if is_english:
            job['school_info'] = search_school_info(job['school'])
            verified.append(job)
            tag = ' (已發過)' if job['already_sent'] else ''
            debug_results.append({'title': job_title, 'school': job['school'][:30],
                                  'status': 'ACCEPTED', 'reason': english_reason + tag})
            print(f"   ✓✓✓ {job_title}{tag}  ({english_reason})")
        else:
            reject(job_title, job['school'], f'非英文科 ({english_reason})')

    return verified, debug_results


def fetch_listing_pages():
    """Fetch all listing pages (sequentially with a short pause) and return raw HTML list."""
    htmls = []
    for page in range(1, NUM_PAGES + 1):
        print(f"📄 第 {page} 頁...")
        html = fetch_page(SEARCH_URL, {'JobAreaID[]': '10-0', 'Page': page})
        htmls.append(html)
        time.sleep(PAGE_SLEEP)
    return htmls


def main():
    print("="*60)
    print("明報 JUMP 小學英文科教師職位搜尋")
    print(f"開始時間: {datetime.now()}")
    print("="*60)

    # Daily guard: any number of redundant triggers (GitHub schedule, an external
    # cron hitting the API, etc.) result in at most ONE Telegram message per HKT
    # day. Pass FORCE_SEND=true (manual "force" dispatch) to bypass for testing.
    force = os.environ.get('FORCE_SEND', '').strip().lower() == 'true'
    if not force and already_sent_today():
        print(f"⏭ 今日 ({hkt_today()}) 已經發送過，跳過。(force=true 可強制重發)")
        return

    # 1. Fetch listing pages and pre-filter candidates
    pages = fetch_listing_pages()
    ok_pages = sum(1 for h in pages if h)
    if ok_pages == 0:
        # Every page failed to load -> the source site (jump.mingpao.com) is
        # unreachable, NOT "no jobs". Stay silent and DON'T mark today as sent,
        # so the bot keeps retrying and auto-resumes once the site is back up.
        print("⚠️ 所有頁面抓取失敗 — 源網站 jump.mingpao.com 連線失敗，"
              "今次唔發送、唔記錄，稍後自動重試。")
        return

    all_jobs = []
    for html in pages:
        if not html:
            continue
        for job in parse_job_listings(html):
            text = f"{job['title']} {job['school']}"
            matches, _ = matches_keywords(text)
            title_lower = job['title'].lower()
            title_has_english_hint = any(
                kw in title_lower for kw in
                ['english', '英文', '英文科', '英文教師', '英文老師', 'english teacher']
            )
            if matches or is_primary_school(text) or title_has_english_hint:
                all_jobs.append(job)

    # Deduplicate candidates by URL (so each detail page is fetched at most once)
    seen_urls = set()
    unique_jobs = []
    for job in all_jobs:
        if job['url'] in seen_urls:
            continue
        seen_urls.add(job['url'])
        unique_jobs.append(job)
    print(f"\n📊 初步匹配: {len(all_jobs)} 個 (去重後 {len(unique_jobs)} 個獨立職位)")

    sent_jobs = load_sent_jobs()
    print(f"   已發送職位記錄: {len(sent_jobs)} 個")

    # 2. Fetch all detail pages in parallel, then classify ONCE
    prefetch_details(unique_jobs)
    print(f"\n{'='*60}\n🔎 驗證職位...\n{'='*60}")
    verified_all, debug_results = classify_jobs(unique_jobs, sent_jobs)

    accepted = sum(1 for r in debug_results if r['status'] == 'ACCEPTED')
    rejected = sum(1 for r in debug_results if r['status'] == 'REJECTED')
    new_verified = [j for j in verified_all if not j.get('already_sent')]
    sent_verified = [j for j in verified_all if j.get('already_sent')]
    print(f"\n📊 驗證結果: 共 {len(debug_results)} | ✓ {accepted} | ✗ {rejected}")
    print(f"   符合條件: {len(verified_all)} 個 (未發送 {len(new_verified)} / 已發過 {len(sent_verified)})")

    # 3. Pick NEW jobs first, widening the date window (14d, 30d) and finally
    #    falling back to all new verified jobs (incl. undated).
    selected = []
    search_hours = None
    for hours in SEARCH_WINDOWS:
        cutoff = datetime.now() - timedelta(hours=hours)
        in_window = [j for j in new_verified if j.get('posted_date') and j['posted_date'] >= cutoff]
        print(f"📅 {hours}小時窗口: {len(in_window)} 個新職位")
        if len(in_window) >= MIN_JOBS:
            selected = in_window
            search_hours = hours
            print(f"✓ 達標 (≥{MIN_JOBS})，停止擴展")
            break
    if len(selected) < MIN_JOBS:
        selected = new_verified
        search_hours = None
        print(f"⚠ 新職位不足 {MIN_JOBS} 個，改用全部 {len(selected)} 個新職位")

    selected = deduplicate_jobs(selected)
    top_jobs = rank_jobs(selected)  # up to MIN_JOBS new jobs, school-diverse

    # 4. Top up to MIN_JOBS with the most recent already-sent (but still valid)
    #    jobs, clearly tagged so the user knows they are repeats.
    if len(top_jobs) < MIN_JOBS:
        need = MIN_JOBS - len(top_jobs)
        chosen_urls = {j['url'] for j in top_jobs}
        pool = deduplicate_jobs([j for j in sent_verified if j['url'] not in chosen_urls])
        pool.sort(key=lambda x: x.get('posted_date') or datetime.min, reverse=True)
        topups = pool[:need]
        if topups:
            search_hours = None  # mixed freshness once we include repeats
            for j in topups:
                j['already_sent'] = True
            top_jobs += topups
            print(f"🔁 用 {len(topups)} 個『已發過』職位補足至 {len(top_jobs)} 個")

    print(f"\n📤 發送 {len(top_jobs)} 個職位...")
    message = format_message(top_jobs, search_hours)
    result = send_telegram_message(message)

    if result and result.get('ok'):
        print("✅ 發送成功!")
        # Only record genuinely new jobs as sent (top-ups are already recorded).
        for job in top_jobs:
            if not job.get('already_sent'):
                sent_jobs.add(job['url'])
        save_sent_jobs(sent_jobs)
        mark_sent_today()  # block other redundant scheduled runs today
        print(f"   已保存新職位到記錄 (總計 {len(sent_jobs)} 個)")
    else:
        print(f"❌ 發送失敗: {result}")

    print(f"\n完成時間: {datetime.now()}")
    print("="*60)


if __name__ == "__main__":
    main()
