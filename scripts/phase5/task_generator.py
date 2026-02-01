import os
import json
import requests
import re

def get_api_key():
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return os.getenv("GEMINI_API_KEY")

GEMINI_API_KEY = get_api_key()
MODEL_NAME = "gemini-3-flash"

def scrape_change_records(limit=5):
    url = "https://www.drupal.org/list-changes/drupal"
    headers = {"User-Agent": "DrupalBench/0.1"}
    response = requests.get(url, headers=headers)
    
    # Simple regex to find links to change records
    # Example: <td class="views-field views-field-title" >
    #          <a href="/node/3352256">Single Directory Components is now in core</a>          </td>
    
    links = re.findall(r'<td class="views-field views-field-title"[^>]*>\s*<a href="(/node/\d+)">([^<]+)</a>', response.text)
    
    records = []
    for href, title in links[:limit]:
        full_url = "https://www.drupal.org" + href
        
        # Get the content of the change record
        rec_res = requests.get(full_url, headers=headers)
        
        # Extract body content - look for the field-name-body div
        body_match = re.search(r'<div class="field field-name-body[^>]*>(.*?)</div>\s*</div>', rec_res.text, re.DOTALL)
        if body_match:
            content = body_match.group(1)
            # Basic HTML tag removal
            content = re.sub(r'<[^>]+>', '', content).strip()
            
            records.append({
                "title": title.strip(),
                "url": full_url,
                "content": content
            })
    return records

def generate_task(change_record):
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found.")
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

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        if 'candidates' in result and result['candidates']:
            content_text = result['candidates'][0]['content']['parts'][0]['text']
            return json.loads(content_text)
        else:
            print(f"No candidates in response: {result}")
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        # response might not be defined if requests.post fails completely
            
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
