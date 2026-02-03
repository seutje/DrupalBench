import os
import json
import requests
import subprocess
import time
import sys
import re
import argparse
import hashlib

# Add the project root to sys.path to allow importing from scripts if needed
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
OLLAMA_HOST = ENV.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_REQUEST_TIMEOUT = 15 * 60  # Hard timeout for model calls (seconds).

def run_command(command, shell=True, timeout=None):
    try:
        result = subprocess.run(command, shell=shell, check=False, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def call_model(prompt):
    system_instruction = """You are an expert Drupal 11 developer. 
Solve the following problem by providing a valid git diff (patch).
The patch should be applicable to a standard Drupal 11 installation using `git apply -p1`.
Output ONLY the git diff. Do not include markdown code blocks.
Ensure your patch uses a/ and b/ prefixes (e.g., --- a/core/modules/... and +++ b/core/modules/...).
Focus on making the patch compatible with the current file contents provided in the context.
"""
    
    if MODEL_PROVIDER == "gemini":
        return call_gemini(prompt, system_instruction)
    elif MODEL_PROVIDER == "ollama":
        return call_ollama(prompt, system_instruction)
    else:
        return None, f"Unknown model provider: {MODEL_PROVIDER}"

def call_gemini(prompt, system_instruction):
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY not found."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    full_prompt = f"{system_instruction}\n\nProblem Description:\n{prompt}"
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}

    try:
        response = requests.post(url, json=payload, timeout=MODEL_REQUEST_TIMEOUT)
        if response.status_code != 200:
            return None, f"API Error {response.status_code}: {response.text}"
        result = response.json()
        if 'candidates' in result and result['candidates']:
            text = result['candidates'][0]['content']['parts'][0]['text']
            return clean_patch_output(text), None
        return None, "No candidates in response."
    except Exception as e:
        return None, str(e)

def call_ollama(prompt, system_instruction):
    url = f"{OLLAMA_HOST}/api/generate"
    full_prompt = f"{system_instruction}\n\nProblem Description:\n{prompt}"
    payload = {"model": MODEL_NAME, "prompt": full_prompt, "stream": False}

    try:
        response = requests.post(url, json=payload, timeout=MODEL_REQUEST_TIMEOUT)
        if response.status_code != 200:
            return None, f"Ollama Error {response.status_code}: {response.text}"
        result = response.json()
        text = result.get('response', '')
        return clean_patch_output(text), None
    except Exception as e:
        return None, str(e)

def clean_patch_output(text):
    code_blocks = re.findall(r'```(?:\w+)?\s*(.*?)\s*```', text, re.DOTALL)
    if code_blocks:
        cleaned_text = ""
        for block in code_blocks:
            if '--- ' in block or '+++ ' in block or '@@ ' in block:
                cleaned_text += block + "\n"
        if cleaned_text:
            text = cleaned_text
    
    patterns = ['diff --git', '--- ', 'Index: ']
    first_idx = len(text)
    found = False
    for p in patterns:
        idx = text.find(p)
        if idx != -1 and idx < first_idx:
            first_idx = idx
            found = True
    
    if found:
        text = text[first_idx:]
    
    text = text.replace('\r\n', '\n')
    return text

def fix_hunk_headers(patch_text):
    if not patch_text:
        return patch_text
        
    lines = patch_text.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('@@'):
            match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*)', line)
            if match:
                old_start, _, new_start, _, rest = match.groups()
                actual_old_len = 0
                actual_new_len = 0
                hunk_lines = []
                j = i + 1
                while j < len(lines):
                    h_line = lines[j]
                    if h_line.startswith('@@') or h_line.startswith('diff --git') or \
                       h_line.startswith('--- ') or h_line.startswith('+++ ') or \
                       h_line.startswith('Index: '):
                        break
                    if h_line.startswith('-'):
                        actual_old_len += 1
                        hunk_lines.append(h_line)
                    elif h_line.startswith('+'):
                        actual_new_len += 1
                        hunk_lines.append(h_line)
                    elif h_line.startswith(' '):
                        actual_old_len += 1
                        actual_new_len += 1
                        hunk_lines.append(h_line)
                    elif h_line == '':
                        actual_old_len += 1
                        actual_new_len += 1
                        hunk_lines.append(' ')
                    elif h_line.startswith('\\'):
                        hunk_lines.append(h_line)
                    else:
                        actual_old_len += 1
                        actual_new_len += 1
                        hunk_lines.append(' ' + h_line)
                    j += 1
                new_header = f"@@ -{old_start},{actual_old_len} +{new_start},{actual_new_len} @@{rest}"
                fixed_lines.append(new_header)
                fixed_lines.extend(hunk_lines)
                i = j
                continue
        fixed_lines.append(line)
        i += 1
    result = '\n'.join(fixed_lines).rstrip('\n')
    if result: result += '\n'
    return result

def reset_environment():
    print("  Resetting environment...")
    run_command("docker-compose exec -T drupal git config --global --add safe.directory /var/www/html")
    run_command("docker-compose exec -T drupal git reset --hard HEAD")
    run_command("docker-compose exec -T drupal git clean -fd -e vendor/ -e web/sites/default/settings.php -e web/sites/default/files/")
    # Fix permissions for functional tests - only on sites directory for speed
    run_command("docker-compose exec -T drupal mkdir -p web/sites/simpletest/browser_output")
    run_command("docker-compose exec -T drupal chown -R www-data:www-data web/sites")
    run_command("docker-compose exec -T drupal chmod -R 777 web/sites/simpletest")

def unsolve_task(task):
    if 'ground_truth' not in task or not isinstance(task['ground_truth'], str):
        return False
    patch = task['ground_truth']
    with open("unsolve.patch", "w") as f: f.write(patch)
    success_id, container_id, _ = run_command("docker-compose ps -q drupal")
    container_id = container_id.strip()
    if not container_id: return False
    run_command(f"docker cp unsolve.patch {container_id}:/var/www/html/unsolve.patch")
    unsolved = False
    for directory in ["web", "."]:
        cmd = f"docker-compose exec -T drupal bash -c 'cd {directory} && git apply -R --recount /var/www/html/unsolve.patch'"
        if run_command(cmd)[0]:
            print(f"    Task was already solved. Reversed patch in {directory} to 'unsolve' it.")
            unsolved = True
            break
    if unsolved:
        run_command("docker-compose exec -T drupal git add .")
        run_command("docker-compose exec -T drupal git commit -m 'Unsolve task' --allow-empty")
    return unsolved

def get_context_for_task(task):
    files_to_read = []
    if 'ground_truth' in task and isinstance(task['ground_truth'], str):
        files_to_read = re.findall(r'--- a/(.*)', task['ground_truth'])
        files_to_read += re.findall(r'\+\+\+ b/(.*)', task['ground_truth'])
        files_to_read += re.findall(r'--- (.*)', task['ground_truth'])
        files_to_read += re.findall(r'\+\+\+ (.*)', task['ground_truth'])
    seen = set()
    context = "\n\nRelevant code context:\n"
    found_any = False
    for f_path in files_to_read:
        f_path = f_path.strip().split('\t')[0]
        if not f_path or f_path == '/dev/null' or f_path in seen: continue
        seen.add(f_path)
        content = ""
        for prefix in ["web/", ""]:
            full_path = f"app/{prefix}{f_path}"
            if os.path.exists(full_path) and os.path.isfile(full_path):
                try:
                    with open(full_path, "r") as f: content = f.read()
                    break
                except: pass
        if content:
            context += f"\nFile: {f_path}\n```\n{content}\n```\n"
            found_any = True
    return context if found_any else ""

def evaluate_task(task, samples_per_task=1):
    task_id = task['task_id']
    print(f"Evaluating Task {task_id}: {task['title']}")
    sample_results = []
    
    for i in range(samples_per_task):
        print(f"  Sample {i+1}/{samples_per_task}...")
        reset_environment()
        unsolved = unsolve_task(task)
        
        code_context = get_context_for_task(task)
        full_prompt = task['prompt'] + code_context
        
        if 'test_path' in task and 'test_content' in task:
            test_path = task['test_path']
            if not test_path.startswith('web/'): test_path = f"web/{test_path}"
            with open("test_file.php", "w") as f: f.write(task['test_content'])
            success_id, container_id, _ = run_command("docker-compose ps -q drupal")
            if container_id.strip():
                run_command(f"docker-compose exec -T drupal mkdir -p {os.path.dirname(test_path)}")
                run_command(f"docker cp test_file.php {container_id.strip()}:/var/www/html/{test_path}")
                print(f"    Created synthetic test at {test_path}")
        
        patch, error = call_model(full_prompt)
        if error or patch is None:
            sample_results.append({"passed": False, "error": error or "No patch"})
            continue

        patch = fix_hunk_headers(patch)
        with open("temp.patch", "w") as f: f.write(patch)
        success_id, container_id, _ = run_command("docker-compose ps -q drupal")
        if not container_id.strip(): continue
        run_command(f"docker cp temp.patch {container_id.strip()}:/var/www/html/task.patch")
        
        patch_applied = False
        # Try git apply first with various options
        for directory in ["web", "."]:
            for p_arg in ["-p1", "-p0"]:
                for extra in ["", "--3way"]:
                    cmd = f"docker-compose exec -T drupal git apply -v {extra} --recount --whitespace=fix {p_arg} --directory={directory} /var/www/html/task.patch"
                    if run_command(cmd)[0]:
                        print(f"    Patch applied with git apply {extra} {p_arg} --directory={directory}")
                        patch_applied = True
                        break
                if patch_applied: break
            if patch_applied: break
        
        if not patch_applied:
            # Fallback to patch utility
            for directory in ["web", "."]:
                for p_level in ["-p1", "-p0"]:
                    cmd = f"docker-compose exec -T drupal patch {p_level} --fuzz=3 -l -t -N -d {directory} -i /var/www/html/task.patch"
                    if run_command(cmd)[0]:
                        print(f"    Patch applied with patch {p_level} --fuzz in {directory}")
                        patch_applied = True
                        break
                if patch_applied: break
                
        if not patch_applied:
            print(f"    FAILED to apply patch.")
            sample_results.append({"passed": False, "patch": patch, "error": "Patch application failed"})
            continue

        test_files = []
        # Check for test files in the generated patch
        test_files += re.findall(r'[ab]/([^ \n\t]*tests/src/[^ \n\t]*Test\.php)', patch)
        # Check for test files in the ground truth patch
        if 'ground_truth' in task and isinstance(task['ground_truth'], str):
            test_files += re.findall(r'[ab]/([^ \n\t]*tests/src/[^ \n\t]*Test\.php)', task['ground_truth'])
        
        test_files = list(set(test_files)) # Unique
        
        test_path_to_run = ""
        if 'test_path' in task:
            test_path_to_run = task['test_path']
            if not test_path_to_run.startswith('web/'): test_path_to_run = f"web/{test_path_to_run}"
        elif test_files:
            # Run specific test files found in patches
            test_path_to_run = " ".join([f"web/core/{tf}" if tf.startswith("modules/") else f"web/{tf}" for tf in test_files])
            # Ensure paths are relative to web root and don't have double web/ or core/
            test_path_to_run = test_path_to_run.replace("web/web/", "web/").replace("web/core/core/", "web/core/")
        elif "core/modules/" in patch:
            match = re.search(r'core/modules/(\w+)', patch)
            if match: test_path_to_run = f"web/core/modules/{match.group(1)}"
        
        if test_path_to_run:
            print(f"    Running tests in {test_path_to_run}...")
            paths = test_path_to_run.split()
            all_passed = True
            combined_output = ""
            for p in paths:
                rel_p = p.replace("web/", "")
                # Skip FunctionalJavascript tests as they require WebDriver
                if "FunctionalJavascript" in rel_p:
                    print(f"      Skipping Javascript test: {rel_p}")
                    continue
                
                print(f"      Running {rel_p}...")
                # Increased timeout to 900s (15 mins) per test file
                phpunit_cmd = f"docker-compose exec -T -u www-data drupal bash -c 'cd web && timeout 900 ../vendor/bin/phpunit -c core/phpunit.xml {rel_p}'"
                success, stdout, stderr = run_command(phpunit_cmd, timeout=910)
                combined_output += f"\n--- Output for {rel_p} ---\n{stdout}{stderr}"
                
                # Check for "OK" in output as a fallback for non-zero exit codes due to deprecations
                if not success and "OK (" not in stdout:
                    print(f"      FAILED: {rel_p}")
                    all_passed = False
                else:
                    print(f"      PASSED: {rel_p}")
            
            sample_results.append({"passed": all_passed, "patch": patch, "phpunit_output": combined_output})
            print("    SUCCESS" if all_passed else "    FAILED (tests)")
        else:
            print("    No tests run.")
            sample_results.append({"passed": True, "patch": patch, "phpunit_output": "No tests"})
            print("    SUCCESS (no tests)")
        
    return {
        "task_id": task_id, "title": task['title'], "passed": any(s.get('passed') for s in sample_results),
        "samples": sample_results, "total_samples": samples_per_task, "correct_samples": sum(1 for s in sample_results if s.get('passed'))
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=str, default="tasks.json")
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--model", type=str)
    parser.add_argument("--provider", type=str)
    parser.add_argument("--task_id", type=str)
    args = parser.parse_args()
    global MODEL_NAME, MODEL_PROVIDER
    if args.model: MODEL_NAME = args.model
    if args.provider: MODEL_PROVIDER = args.provider
    
    all_tasks = []
    if os.path.exists(args.tasks):
        with open(args.tasks, "r") as f: all_tasks.extend(json.load(f))
    if os.path.exists("synthetic_tasks.json"):
        with open("synthetic_tasks.json", "r") as f: all_tasks.extend(json.load(f))

    results = {"model_name": MODEL_NAME, "model_provider": MODEL_PROVIDER, "tasks": [], "total_samples": 0, "total_correct": 0}
    for task in all_tasks:
        if 'task_id' not in task: task['task_id'] = f"syn_{hashlib.md5(task.get('title', '').encode()).hexdigest()[:8]}"
        if args.task_id and str(task['task_id']) != args.task_id: continue
        task_res = evaluate_task(task, samples_per_task=args.samples)
        results["tasks"].append(task_res)
        results["total_samples"] += task_res["total_samples"]
        results["total_correct"] += task_res["correct_samples"]
        with open("results.json", "w") as f: json.dump(results, f, indent=2)
    print(f"\nTotal Correct: {results['total_correct']}/{results['total_samples']}")

if __name__ == "__main__": main()
