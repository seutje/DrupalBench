import requests
import json
import re
import time
import os

DRUPAL_NODE_API = "https://www.drupal.org/api-d7/node"
GITLAB_PROJECT_ID = "59858"
GITLAB_API = f"https://git.drupalcode.org/api/v4/projects/{GITLAB_PROJECT_ID}/merge_requests"
DRUPAL_GIT_BASE = "https://git.drupalcode.org/project/drupal/-/merge_requests/"

HEADERS = {
    "User-Agent": "DrupalBench/0.1 (Benchmark for LLMs; contact: user@example.com)"
}

def search_gitlab_mr(nid):
    params = {
        "scope": "all",
        "search": str(nid)
    }
    try:
        response = requests.get(GITLAB_API, params=params, headers=HEADERS)
        if response.status_code == 200:
            mrs = response.json()
            # Prefer merged MRs, then opened ones
            merged = [m for m in mrs if m.get("state") == "merged"]
            if merged:
                return merged[0].get("iid")
            opened = [m for m in mrs if m.get("state") == "opened"]
            if opened:
                return opened[0].get("iid")
    except Exception as e:
        print(f"Error searching GitLab for {nid}: {e}")
    return None

def has_phpunit_tests(diff_text):
    test_patterns = [
        r'tests/src/Unit',
        r'tests/src/Kernel',
        r'tests/src/Functional',
        r'tests/src/ExistingSite'
    ]
    for pattern in test_patterns:
        if re.search(pattern, diff_text):
            return True
    return False

def get_mr_diff(iid):
    diff_url = f"{DRUPAL_GIT_BASE}{iid}.diff"
    try:
        response = requests.get(diff_url, headers=HEADERS)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"Error fetching diff for MR !{iid}: {e}")
    return None

def main():
    tasks_file = "tasks.json"
    if os.path.exists(tasks_file):
        with open(tasks_file, "r") as f:
            try:
                tasks = json.load(f)
            except:
                tasks = []
    else:
        tasks = []
        
    print(f"Loaded {len(tasks)} existing tasks.")
    target_tasks = 300
    
    
    # Drupal.org project IDs to mine, only Core for now.
    projects = ["3060"]
    for project in projects:
        if len(tasks) >= target_tasks:
            break
        print(f"Checking project {project}...")
        # Statuses: RTBC(14), Fixed(2), Closed(fixed)(7)
        for status in ["2", "7", "14"]:
            if len(tasks) >= target_tasks:
                break
                
            print(f"  Checking status {status} for project {project}...")
            page = 0
            while len(tasks) < target_tasks and page < 20:
                print(f"    Fetching page {page} for status {status}...")
                url = f"{DRUPAL_NODE_API}.json"
                params = {
                    "type": "project_issue",
                    "field_project": project,
                    "field_issue_status": status,
                    "limit": 50,
                    "page": page,
                    "sort": "changed",
                    "direction": "DESC"
                }
                try:
                    response = requests.get(url, params=params, headers=HEADERS)
                    if response.status_code == 429:
                        print("Rate limit hit, sleeping...")
                        time.sleep(30)
                        continue
                    response.raise_for_status()
                    issues = response.json().get("list", [])
                except Exception as e:
                    print(f"Error fetching issues: {e}")
                    break
                    
                if not issues:
                    break
                    
                for issue in issues:
                    nid = issue.get("nid")
                    title = issue.get("title")
                    version = issue.get("field_issue_version")
                    
                    if not version or not any(v in version for v in ["main", "11.", "10.4", "10.3"]):
                        continue
                        
                    if any(t['task_id'] == nid for t in tasks):
                        continue

                    print(f"Searching MR for Issue #{nid}: {title}")
                    mr_id = search_gitlab_mr(nid)

                    
                    if not mr_id:
                        continue

                    print(f"  Found MR !{mr_id}. Checking diff...")
                    diff = get_mr_diff(mr_id)
                    if diff and has_phpunit_tests(diff):
                        print(f"    Found PHPUnit tests. Adding to tasks ({len(tasks)+1}/{target_tasks}).")
                        tasks.append({
                            "task_id": nid,
                            "title": title,
                            "version": version,
                            "prompt": issue.get("body", {}).get("value", ""),
                            "ground_truth": diff,
                            "mr_id": mr_id,
                            "url": f"https://www.drupal.org/i/{nid}"
                        })
                        with open(tasks_file, "w") as f:
                            json.dump(tasks, f, indent=2)
                    
                    if len(tasks) >= target_tasks:
                        break
                        
                    time.sleep(0.5)
                    
                page += 1
                time.sleep(2)
            
    print(f"Successfully mined {len(tasks)} tasks and saved to tasks.json")

if __name__ == "__main__":
    main()
