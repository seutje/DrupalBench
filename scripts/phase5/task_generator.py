import os
import json
import requests
import re
import time
import sys
import argparse

# Add the project root to sys.path
sys.path.append(os.getcwd())

def load_env():
    env = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip()
    return env

ENV = load_env()
MODEL_PROVIDER = ENV.get("MODEL_PROVIDER", "gemini")
MODEL_NAME = ENV.get("MODEL_NAME", "gemini-3-flash-preview")
GEMINI_API_KEY = ENV.get("GEMINI_API_KEY")
OPENAI_API_KEY = ENV.get("OPENAI_API_KEY")
OPENROUTER_API_KEY = ENV.get("OPENROUTER_API_KEY")
OLLAMA_HOST = ENV.get("OLLAMA_HOST", "http://localhost:11434")
OPENROUTER_BASE_URL = ENV.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_HTTP_REFERER = ENV.get("OPENROUTER_HTTP_REFERER")
OPENROUTER_X_TITLE = ENV.get("OPENROUTER_X_TITLE")
MODEL_REQUEST_TIMEOUT = 15 * 60

def scrape_change_records(limit=5):
    url = "https://www.drupal.org/list-changes/drupal"
    headers = {"User-Agent": "DrupalBench/0.1"}
    print(f"Fetching {url}...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching change records: {e}")
        return []
    
    # Broaden regex to find links to change records
    links = re.findall(r'<td\s+class="views-field views-field-title"[^>]*>\s*<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', response.text)
    
    print(f"Regex found {len(links)} candidate links.")
    
    records = []
    for href, title in links:
        if len(records) >= limit:
            break
            
        full_url = href if href.startswith('http') else "https://www.drupal.org" + href
        print(f"Fetching change record: {full_url}...")
        
        try:
            rec_res = requests.get(full_url, headers=headers)
            rec_res.raise_for_status()
            
            # Extract body content
            body_match = re.search(r'<div class="field field-name-field-description[^>]*>(.*?)</div>\s*</div>', rec_res.text, re.DOTALL)
            if not body_match:
                body_match = re.search(r'<div class="field field-name-body[^>]*>(.*?)</div>\s*</div>', rec_res.text, re.DOTALL)
            if not body_match:
                body_match = re.search(r'<div class="field-item even" property="content:encoded">(.*?)</div>', rec_res.text, re.DOTALL)
                
            if body_match:
                content = body_match.group(1)
                content = re.sub(r'<[^>]+>', '', content).strip()
                content = re.sub(r'\s+', ' ', content)
                
                records.append({
                    "title": title.strip(),
                    "url": full_url,
                    "content": content[:3000]
                })
                print(f"  Scraped: {title.strip()}")
            else:
                print(f"  WARNING: Could not find body content for {full_url}")
        except Exception as e:
            print(f"  Error fetching {full_url}: {e}")
            
    return records

def generate_task(change_record):
    with open("scripts/phase5/task_prompt.txt", "r") as f:
        prompt_template = f.read()
    
    prompt = prompt_template.replace("{{change_record_context}}", f"Title: {change_record['title']}\nURL: {change_record['url']}\nContent: {change_record['content']}")
    
    if MODEL_PROVIDER == "gemini":
        task = generate_task_gemini(prompt)
    elif MODEL_PROVIDER == "openai":
        task = generate_task_openai(prompt)
    elif MODEL_PROVIDER == "openrouter":
        task = generate_task_openrouter(prompt)
    elif MODEL_PROVIDER == "ollama":
        task = generate_task_ollama(prompt)
    else:
        print(f"Error: Unknown model provider: {MODEL_PROVIDER}")
        return None
        
    if task and isinstance(task.get('ground_truth'), dict):
         task['ground_truth'] = "" # Fix hallucinated dict
         
    return task

def generate_task_gemini(prompt):
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found.")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 429:
                wait_time = (attempt + 1) * 5
                time.sleep(wait_time)
                continue
            if response.status_code != 200:
                print(f"  API Error {response.status_code}: {response.text}")
                return None

            result = response.json()
            if 'candidates' in result and result['candidates']:
                content_text = result['candidates'][0]['content']['parts'][0]['text']
                return json.loads(content_text)
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(2)
    return None

def generate_task_ollama(prompt):
    url = f"{OLLAMA_HOST}/api/generate"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"  Ollama Error {response.status_code}: {response.text}")
            return None
        
        result = response.json()
        content_text = result.get('response', '')
        return json.loads(content_text)
    except Exception as e:
        print(f"  Error: {e}")
        return None

def extract_openai_output_text(result):
    texts = []

    direct = result.get("output_text")
    if isinstance(direct, str) and direct.strip():
        texts.append(direct.strip())

    output_items = result.get("output")
    if not isinstance(output_items, list):
        return "\n".join(texts).strip()

    for item in output_items:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        if item_type in {"output_text", "text"}:
            value = item.get("text")
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
            continue

        if item_type != "message":
            continue

        content = item.get("content")
        if not isinstance(content, list):
            continue

        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type in {"output_text", "text"}:
                value = part.get("text")
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())

    deduped = []
    for text in texts:
        if text not in deduped:
            deduped.append(text)
    return "\n".join(deduped).strip()

def summarize_openai_response(result):
    parts = []
    response_id = result.get("id")
    status = result.get("status")
    if response_id:
        parts.append(f"id={response_id}")
    if status:
        parts.append(f"status={status}")

    output_items = result.get("output")
    if isinstance(output_items, list):
        item_types = []
        content_types = []
        refusal_text = ""
        for item in output_items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type:
                item_types.append(str(item_type))
            if item_type != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type")
                if part_type:
                    content_types.append(str(part_type))
                if not refusal_text and part_type == "refusal":
                    refusal_value = part.get("refusal")
                    if isinstance(refusal_value, str) and refusal_value.strip():
                        refusal_text = refusal_value.strip()
        if item_types:
            parts.append(f"output_types={sorted(set(item_types))}")
        if content_types:
            parts.append(f"content_types={sorted(set(content_types))}")
        if refusal_text:
            parts.append(f"refusal={refusal_text[:160]}")

    return ", ".join(parts) if parts else "no metadata"

def extract_openrouter_output_text(result):
    texts = []
    choices = result.get("choices")
    if not isinstance(choices, list):
        return ""

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            texts.append(content.strip())
            continue
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())

    deduped = []
    for text in texts:
        if text not in deduped:
            deduped.append(text)
    return "\n".join(deduped).strip()

def generate_task_openai(prompt):
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not found.")
        return None

    url = "https://api.openai.com/v1/responses"
    payload = {
        "model": MODEL_NAME,
        "input": prompt,
        "text": {
            "format": {
                "type": "json_object"
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=MODEL_REQUEST_TIMEOUT)
            if response.status_code == 429:
                wait_time = (attempt + 1) * 5
                time.sleep(wait_time)
                continue
            if response.status_code != 200:
                print(f"  OpenAI Error {response.status_code}: {response.text}")
                return None

            result = response.json()
            content_text = extract_openai_output_text(result)
            if content_text:
                return json.loads(content_text)
            print(f"  Error: OpenAI response did not include text output ({summarize_openai_response(result)})")
            return None
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(2)
    return None

def generate_task_openrouter(prompt):
    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY not found.")
        return None

    url = f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if OPENROUTER_HTTP_REFERER:
        headers["HTTP-Referer"] = OPENROUTER_HTTP_REFERER
    if OPENROUTER_X_TITLE:
        headers["X-Title"] = OPENROUTER_X_TITLE

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=MODEL_REQUEST_TIMEOUT)
            if response.status_code == 429:
                wait_time = (attempt + 1) * 5
                time.sleep(wait_time)
                continue
            if response.status_code != 200:
                print(f"  OpenRouter Error {response.status_code}: {response.text}")
                return None

            result = response.json()
            content_text = extract_openrouter_output_text(result)
            if content_text:
                return json.loads(content_text)
            print("  Error: OpenRouter response did not include text output.")
            return None
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(2)
    return None

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Drupal 11 tasks.")
    parser.add_argument("--limit", type=int, default=5, help="Number of change records to process.")
    args = parser.parse_args()

    print(f"Using Model Provider: {MODEL_PROVIDER}")
    print(f"Model Name: {MODEL_NAME}")
    
    if MODEL_PROVIDER == "gemini" and not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env")
        sys.exit(1)
    if MODEL_PROVIDER == "openai" and not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not found in .env")
        sys.exit(1)
    if MODEL_PROVIDER == "openrouter" and not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY not found in .env")
        sys.exit(1)

    print("Scraping Drupal 11 Change Records...")
    records = scrape_change_records(limit=args.limit)
    print(f"Found {len(records)} records.")
    
    output_file = "synthetic_tasks.json"
    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            try:
                synthetic_tasks = json.load(f)
            except:
                synthetic_tasks = []
    else:
        synthetic_tasks = []

    existing_urls = {t.get('source_url') for t in synthetic_tasks}
    
    new_tasks_count = 0
    for i, record in enumerate(records):
        if record['url'] in existing_urls:
            print(f"  Skipping already existing task for: {record['title']}")
            continue

        print(f"Generating task {i+1}/{len(records)} for: {record['title']}...")
        task = generate_task(record)
        if task:
            task['source_url'] = record['url']
            synthetic_tasks.append(task)
            new_tasks_count += 1
            print(f"  Successfully generated: {task['title']}")
            with open(output_file, "w") as f:
                json.dump(synthetic_tasks, f, indent=2)
        
    print(f"Added {new_tasks_count} new synthetic tasks. Total: {len(synthetic_tasks)}")

if __name__ == "__main__":
    main()
