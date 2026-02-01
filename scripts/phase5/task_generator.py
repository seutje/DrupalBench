import os
import json
import requests
import re
import time

def get_api_key():
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return os.getenv("GEMINI_API_KEY")

GEMINI_API_KEY = get_api_key()
MODEL_NAME = "gemini-3-flash-preview"


def scrape_change_records(limit=5):
    url = "https://www.drupal.org/list-changes/drupal"
    headers = {"User-Agent": "DrupalBench/0.1"}
    print(f"Fetching {url}...")
    response = requests.get(url, headers=headers)
    
    # Broaden regex to find links to change records
    links = re.findall(r'<td\s+class="views-field views-field-title"[^>]*>\s*<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', response.text)
    
    print(f"Regex found {len(links)} candidate links.")
    
    records = []
    for href, title in links:
        if len(records) >= limit:
            break
            
        full_url = href if href.startswith('http') else "https://www.drupal.org" + href
        print(f"Fetching change record: {full_url}...")
        
        # Get the content of the change record
        rec_res = requests.get(full_url, headers=headers)
        
        # Extract body content - Drupal 7 site uses field-name-field-description
        body_match = re.search(r'<div class="field field-name-field-description[^>]*>(.*?)</div>\s*</div>', rec_res.text, re.DOTALL)
        if not body_match:
            # Fallback for older or different structure
            body_match = re.search(r'<div class="field field-name-body[^>]*>(.*?)</div>\s*</div>', rec_res.text, re.DOTALL)
        if not body_match:
            # Another fallback
            body_match = re.search(r'<div class="field-item even" property="content:encoded">(.*?)</div>', rec_res.text, re.DOTALL)
            
        if body_match:
            content = body_match.group(1)
            # Basic HTML tag removal
            content = re.sub(r'<[^>]+>', '', content).strip()
            # Clean up whitespace
            content = re.sub(r'\s+', ' ', content)
            
            records.append({
                "title": title.strip(),
                "url": full_url,
                "content": content[:3000] # Slightly larger limit for more context
            })
            print(f"  Scraped: {title.strip()}")
        else:
            print(f"  WARNING: Could not find body content for {full_url}")
            
    return records

def generate_task(change_record):
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env or environment.")
        return None

    with open("scripts/phase5/task_prompt.txt", "r") as f:
        prompt_template = f.read()
    
    prompt = prompt_template.replace("{{change_record_context}}", f"Title: {change_record['title']}\nURL: {change_record['url']}\nContent: {change_record['content']}")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
        }
    }

    # Add retry logic for API calls
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 429: # Rate limit
                wait_time = (attempt + 1) * 5
                print(f"  Rate limit hit, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
                
            if response.status_code != 200:
                print(f"  API Error {response.status_code}: {response.text}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(5)
                continue

            result = response.json()
            
            if 'candidates' in result and result['candidates']:
                content_text = result['candidates'][0]['content']['parts'][0]['text']
                return json.loads(content_text)
            else:
                print(f"  No candidates in response: {result}")
                return None
        except Exception as e:
            print(f"  Error on attempt {attempt+1}: {e}")
            if attempt == max_retries - 1:
                return None
            time.sleep(2)
            
    return None

def main():
    print("Scraping Drupal 11 Change Records...")
    records = scrape_change_records(limit=3)
    print(f"Found {len(records)} records.")
    
    synthetic_tasks = []
    for i, record in enumerate(records):
        print(f"Generating task {i+1}/{len(records)} for: {record['title']}...")
        task = generate_task(record)
        if task:
            task['source_url'] = record['url']
            synthetic_tasks.append(task)
            print(f"  Successfully generated: {task['title']}")
        
    if synthetic_tasks:
        output_file = "synthetic_tasks.json"
        with open(output_file, "w") as f:
            json.dump(synthetic_tasks, f, indent=2)
        print(f"Saved {len(synthetic_tasks)} synthetic tasks to {output_file}")

if __name__ == "__main__":
    main()
