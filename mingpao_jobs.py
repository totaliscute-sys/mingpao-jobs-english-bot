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

# Suppress SSL warnings
urllib3.disable_warnings(InsecureRequestWarning)

# File to track sent jobs
SENT_JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mingpao_sent_jobs.json')

# Cache file for school district lookups
SCHOOL_DISTRICT_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'school_district_cache.json')

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
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "892783133")
BASE_URL = "https://jump.mingpao.com"
SEARCH_URL = f"{BASE_URL}/job/search/Jobs"

# Keywords
KEYWORDS = ["english", "英文", "英文科", "English Teacher", "老師", "教師", "老師", "英文教師"]

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


def is_confirmed_primary_school(school_name, content):
    """
    STRICT PRIMARY ONLY filter.
    Excludes any job where school_name contains secondary indicators (unless it also has primary indicators).
    Returns True if primary indicators found in school_name OR content.
    If school_name clearly indicates primary (has 'PRIMARY' or '小學'), accept even if content is empty.
    """
    if not school_name:
        return False
    
    # Check if school name has secondary indicators but NO primary indicators - exclude
    has_secondary_in_name = is_secondary_school(school_name)
    has_primary_in_name = is_primary_school(school_name)
    
    if has_secondary_in_name and not has_primary_in_name:
        return False
    
    # Accept if primary indicators in school name (strong signal)
    if has_primary_in_name:
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

# Teaching role indicators
TEACHING_KEYWORDS = [
    '教師', '老師', 'teacher', '教學助理', 'teaching assistant',
    '學位教師', '小學學位教師', '助理小學學位教師', 'APSM', 'GM', 'SGM', 'PSM',
    '學位教師', '常額教師', '合約教師', '代課教師', '日薪代課'
]

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
        # Check content for English - MUST find explicit English keywords
        if content and len(content) > 100:
            # Content fetched successfully - check it for English keywords
            content_has_english = any(kw in content_lower for kw in ['english', '英文科', '教英文', '任教英文', '英文教師', '英文老師'])
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
    
    if search_hours > 24:
        msg += f"<i>搜尋範圍：過去{search_hours}小時</i>\n\n"
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
        
        msg += f"<b>#{i} {title}</b>\n"
        msg += f"🏫 {school}{special_note}\n"
        msg += f"🏛 {school_type}\n"
        msg += f"📍 {district}\n"
        msg += f"📅 {posted_date}\n"
        msg += f"🔗 <a href='{job['url']}'>查看職位</a>\n\n"
    
    msg += "<i>來源：明報 JUMP</i>"
    return msg


def verify_jobs(jobs, sent_jobs, max_verify=20):
    """Verify jobs through full filter pipeline. Returns list of verified jobs."""
    verified = []
    debug_results = []
    
    for i, job in enumerate(jobs):
        if len(verified) >= max_verify:
            break
        
        # Skip already sent
        if job['url'] in sent_jobs:
            debug_results.append({
                'title': job['title'][:50],
                'school': job['school'][:30],
                'status': 'SKIPPED',
                'reason': '已發送'
            })
            continue
            
        job_title = job['title'][:50]
        print(f"\n   {i+1}. {job_title}...")
        details = fetch_job_details(job['url'])
        
        job['content'] = details['content']
        job['salary'] = details['salary']
        content_length = len(job['content']) if job['content'] else 0
        print(f"      內容長度: {content_length} chars")
        
        # Check if it's a teaching role
        is_teaching, teaching_reason = is_teaching_role(job['title'], job['content'])
        if not is_teaching:
            print(f"      ✗ 非教學職位 ({teaching_reason})")
            debug_results.append({
                'title': job_title,
                'school': job['school'][:30],
                'status': 'REJECTED',
                'reason': f'非教學職位 ({teaching_reason})'
            })
            continue
        print(f"      ✓ 教學職位 ({teaching_reason})")

        # Reject substitute/temporary teacher roles
        _sub_match = next((kw for kw in SUBSTITUTE_KEYWORDS if kw in job['title'].lower()), None)
        if _sub_match:
            print(f"      ✗ 代課職位 ({_sub_match})")
            debug_results.append({
                'title': job_title,
                'school': job['school'][:30],
                'status': 'REJECTED',
                'reason': f'代課職位 ({_sub_match})'
            })
            continue
        
        # Check primary school
        is_primary = is_confirmed_primary_school(job['school'], job['content'])
        if not is_primary:
            print(f"      ✗ 非小學")
            debug_results.append({
                'title': job_title,
                'school': job['school'][:30],
                'status': 'REJECTED',
                'reason': '非小學'
            })
            continue
        print(f"      ✓ 小學確認")
        
        # Check for social service organizations (must be actual school)
        if is_social_service_org(job['school']):
            print(f"      ✗ 社會服務機構（非學校）")
            debug_results.append({
                'title': job_title,
                'school': job['school'][:30],
                'status': 'REJECTED',
                'reason': '社會服務機構'
            })
            continue
        print(f"      ✓ 確認為學校（非社福機構）")
        
        # Check for special school
        job['is_special_school'] = is_special_school(job['school'])
        if job['is_special_school']:
            print(f"      🏷 特殊學校")
        
        # English subject check (lenient logic)
        is_english, english_reason = is_english_subject(job['title'], job['content'])
        print(f"      英文檢查: {english_reason}")
        
        job['is_primary'] = is_primary
        job['is_english'] = is_english
        
        if is_primary and is_english:
            print(f"      ✓✓✓ 符合條件")
            job['school_info'] = search_school_info(job['school'])
            verified.append(job)
            debug_results.append({
                'title': job_title,
                'school': job['school'][:30],
                'status': 'ACCEPTED',
                'reason': english_reason
            })
        else:
            print(f"      ✗ 非英文科 ({english_reason})")
            debug_results.append({
                'title': job_title,
                'school': job['school'][:30],
                'status': 'REJECTED',
                'reason': f'非英文科 ({english_reason})'
            })
        
        time.sleep(1)
    
    return verified, debug_results


def main():
    print("="*60)
    print("明報 JUMP 小學英文科教師職位搜尋")
    print(f"開始時間: {datetime.now()}")
    print("="*60)
    
    all_jobs = []
    
    # Fetch 10 pages
    for page in range(1, 11):
        print(f"\n📄 第 {page} 頁...")
        html = fetch_page(SEARCH_URL, {'JobAreaID[]': '10-0', 'Page': page})
        
        if html:
            jobs = parse_job_listings(html)
            print(f"   找到 {len(jobs)} 個職位")
            
            # Check for matches
            for job in jobs:
                text = f"{job['title']} {job['school']}"
                matches, kw = matches_keywords(text)

                # is_english_subject() needs (title, content), can't be used here as pre-filter.
                # Use a lightweight title-only check instead.
                title_lower = job['title'].lower()
                title_has_english_hint = any(
                    kw in title_lower for kw in [
                        'english', '英文', '英文科', '英文教師', '英文老師', 'english teacher'
                    ]
                )

                if matches or is_primary_school(text) or title_has_english_hint:
                    print(f"   ✓ 匹配: {job['title'][:40]}...")
                    all_jobs.append(job)
        
        time.sleep(2)
    
    print(f"\n📊 初步匹配 (日期篩選前): {len(all_jobs)} 個職位")
    
    # Load sent jobs to filter duplicates
    sent_jobs = load_sent_jobs()
    print(f"   已發送職位記錄: {len(sent_jobs)} 個")
    
    # Expansion logic: try 24h → 48h → 72h → 7d until we get 3+ verified jobs
    search_hours_list = [24, 48, 72, 168]  # 1d, 2d, 3d, 7d
    verified_jobs = []
    all_debug_results = []
    search_hours = 24
    
    for hours in search_hours_list:
        # Filter by date
        date_filtered = filter_jobs_by_date(all_jobs, hours)
        print(f"\n{'='*60}")
        print(f"📅 嘗試 {hours}小時窗口 ({len(date_filtered)} 個職位)")
        print(f"{'='*60}")
        
        # Verify jobs through full pipeline
        verified, debug_results = verify_jobs(date_filtered, sent_jobs, max_verify=25)
        verified_jobs = verified
        all_debug_results.extend(debug_results)
        
        print(f"\n📊 {hours}小時驗證結果: {len(verified)} 個符合條件")
        
        if len(verified) >= 3:
            search_hours = hours
            print(f"✓ 找到 {len(verified)} 個職位 (≥3)，停止擴展")
            break
        elif hours < 168:
            print(f"⚠ 只有 {len(verified)} 個職位 (<3)，繼續擴展...")
        else:
            search_hours = hours
            print(f"⚠ 已達最大範圍 (7天)，共找到 {len(verified)} 個職位")
    
    # Print debug summary
    print("\n" + "="*60)
    print("DEBUG SUMMARY - 所有職位處理結果:")
    print("="*60)
    accepted_count = sum(1 for r in all_debug_results if r['status'] == 'ACCEPTED')
    skipped_count = sum(1 for r in all_debug_results if r['status'] == 'SKIPPED')
    rejected_count = sum(1 for r in all_debug_results if r['status'] == 'REJECTED')
    print(f"總計: {len(all_debug_results)} | ✓ 接受: {accepted_count} | ⏭ 跳過: {skipped_count} | ✗ 拒絕: {rejected_count}")
    print(f"最終搜尋範圍: {search_hours}小時")
    print("-"*60)
    for r in all_debug_results[:50]:  # Show first 50
        if r['status'] == 'ACCEPTED':
            print(f"✓ {r['title'][:45]:<45} | {r['reason']}")
    print("="*60)
    
    # Deduplicate by school+title
    verified_jobs = deduplicate_jobs(verified_jobs)
    print(f"\n📊 去除重複後職位數量: {len(verified_jobs)}")
    
    all_jobs = verified_jobs
    print(f"\n📊 驗證後職位數量: {len(all_jobs)}")
    
    # Filter out already sent jobs
    new_jobs = [job for job in all_jobs if job['url'] not in sent_jobs]
    skipped = len(all_jobs) - len(new_jobs)
    if skipped > 0:
        print(f"   跳過已發送: {skipped} 個")
    print(f"   新職位: {len(new_jobs)} 個")
    
    # Rank and select top 3
    top_jobs = rank_jobs(new_jobs)
    print(f"\n📤 發送 {len(top_jobs)} 個職位...")
    
    message = format_message(top_jobs, search_hours)
    result = send_telegram_message(message)
    
    if result and result.get('ok'):
        print("✅ 發送成功!")
        # Save sent job URLs
        for job in top_jobs:
            sent_jobs.add(job['url'])
        save_sent_jobs(sent_jobs)
        print(f"   已保存 {len(top_jobs)} 個職位到記錄")
    else:
        print(f"❌ 發送失敗: {result}")
    
    print(f"\n完成時間: {datetime.now()}")
    print("="*60)


if __name__ == "__main__":
    main()
