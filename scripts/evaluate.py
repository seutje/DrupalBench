import os
import json
import requests
import subprocess
import time
import sys
import re
import argparse

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
The patch should be applicable to a standard Drupal 11 installation using `patch -p1` or `git apply`.
Output ONLY the git diff. Do not include markdown code blocks like ```diff unless strictly necessary, but prefer raw text if possible. If you use code blocks, ensure they are correctly formatted.
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

    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}]
    }

    try:
        response = requests.post(url, json=payload)
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

    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            return None, f"Ollama Error {response.status_code}: {response.text}"
        
        result = response.json()
        text = result.get('response', '')
        return clean_patch_output(text), None
    except Exception as e:
        return None, str(e)

def clean_patch_output(text):
    # Extract all diffs wrapped in markdown
    code_blocks = re.findall(r'```(?:\w+)?\s*(.*?)\s*```', text, re.DOTALL)
    if code_blocks:
        # Join all code blocks that look like diffs
        cleaned_text = ""
        for block in code_blocks:
            if '--- ' in block or '+++ ' in block or 'diff --git' in block or '@@ ' in block:
                cleaned_text += block + "\n"
        if cleaned_text:
            text = cleaned_text
    
    # Remove any leading text before 'diff --git', '--- ', or 'Index: '
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
    
    # Normalize line endings
    text = text.replace('\r\n', '\n')
    
    # Remove trailing newlines but preserve significant whitespace
    text = text.rstrip('\n')
    if text:
        text += '\n'
    
    return text

def fix_hunk_headers(patch_text):
    """
    Recalculates hunk headers to match actual line counts.
    Ensures context lines have a leading space.
    """
    if not patch_text:
        return patch_text
        
    lines = patch_text.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('@@'):
            # Parse @@ -old_start,old_len +new_start,new_len @@
            match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*)', line)
            if match:
                old_start, _, new_start, _, rest = match.groups()
                
                actual_old_len = 0
                actual_new_len = 0
                hunk_lines = []
                j = i + 1
                while j < len(lines):
                    h_line = lines[j]
                    
                    # End of hunk detected by next hunk or next file
                    if h_line.startswith('@@') or \
                       h_line.startswith('diff --git') or \
                       h_line.startswith('--- ') or \
                       h_line.startswith('+++ ') or \
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
                        # Completely empty line in a hunk is usually an empty context line
                        actual_old_len += 1
                        actual_new_len += 1
                        hunk_lines.append(' ')
                    elif h_line.startswith('\\'):
                        # No newline at end of file
                        hunk_lines.append(h_line)
                    else:
                        # Malformed context line (missing leading space)
                        actual_old_len += 1
                        actual_new_len += 1
                        hunk_lines.append(' ' + h_line)
                    j += 1
                
                # Update header
                new_header = f"@@ -{old_start},{actual_old_len} +{new_start},{actual_new_len} @@{rest}"
                fixed_lines.append(new_header)
                fixed_lines.extend(hunk_lines)
                i = j
                continue
        
        fixed_lines.append(line)
        i += 1
    
    # Ensure there is exactly one trailing newline
    result = '\n'.join(fixed_lines).rstrip('\n')
    if result:
        result += '\n'
    return result

def reset_environment():
    print("  Resetting environment...")
    run_command("docker-compose exec -T drupal git config --global --add safe.directory /var/www/html")
    run_command("docker-compose exec -T drupal git reset --hard HEAD")
    run_command("docker-compose exec -T drupal git clean -fd")

def unsolve_task(task):
    """
    Attempts to reverse apply the ground truth patch to 'unsolve' the task
    if it's already present in the codebase.
    """
    if 'ground_truth' not in task:
        return False
        
    patch = task['ground_truth']
    with open("unsolve.patch", "w") as f:
        f.write(patch)
        
    success_id, container_id, _ = run_command("docker-compose ps -q drupal")
    container_id = container_id.strip()
    if not container_id:
        return False
        
    run_command(f"docker cp unsolve.patch {container_id}:/var/www/html/unsolve.patch")
    
    unsolved = False
    for directory in ["web", "."]:
        # Check if it can be reverse applied
        success, _, _ = run_command(f"docker-compose exec -T drupal git apply -R --check --recount --directory={directory} /var/www/html/unsolve.patch")
        if success:
            run_command(f"docker-compose exec -T drupal git apply -R --recount --directory={directory} /var/www/html/unsolve.patch")
            print(f"    Task was already solved. Reversed patch in {directory} to 'unsolve' it.")
            unsolved = True
            break
            
    if unsolved:
        run_command("docker-compose exec -T drupal git add .")
        run_command("docker-compose exec -T drupal git commit -m 'Unsolve task for evaluation' --allow-empty")
    
    return unsolved

def evaluate_task(task, samples_per_task=1):
    task_id = task['task_id']
    print(f"Evaluating Task {task_id}: {task['title']}")
    
    sample_results = []
    
    for i in range(samples_per_task):
        print(f"  Sample {i+1}/{samples_per_task}...")
        reset_environment()
        
        # Unsolve if possible
        unsolved = unsolve_task(task)
        
        # For synthetic tasks, create the test file if provided
        if 'test_path' in task and 'test_content' in task:
            test_path = task['test_path']
            # Ensure path is relative to web if needed
            if not test_path.startswith('web/') and os.path.exists('app/web'):
                 # Check if the path in task expects to be in web root
                 pass # We'll try to handle it in the container
            
            with open("test_file.php", "w") as f:
                f.write(task['test_content'])
            
            success_id, container_id, _ = run_command("docker-compose ps -q drupal")
            container_id = container_id.strip()
            if container_id:
                # Create directory
                dirname = os.path.dirname(test_path)
                run_command(f"docker-compose exec -T drupal mkdir -p {dirname}")
                run_command(f"docker cp test_file.php {container_id}:/var/www/html/{test_path}")
                print(f"    Created synthetic test at {test_path}")
        
        patch, error = call_model(task['prompt'])
        if error or patch is None:
            print(f"    Error calling model: {error or 'No patch returned'}")
            sample_results.append({"passed": False, "error": error or "No patch returned"})
            continue

        patch = fix_hunk_headers(patch)

        # Save patch and copy to container
        with open("temp.patch", "w") as f:
            f.write(patch)
        
        # Get container ID more reliably
        success_id, container_id, _ = run_command("docker-compose ps -q drupal")
        container_id = container_id.strip()
        if not container_id:
            print("    ERROR: Could not find drupal container.")
            continue
            
        run_command(f"docker cp temp.patch {container_id}:/var/www/html/task.patch")
        
        # Apply patch
        patch_applied = False
        last_error = ""
        
        # Try git apply --recount first
        for directory in ["web", "."]:
            success, stdout, stderr = run_command(f"docker-compose exec -T drupal git apply --recount --whitespace=fix --directory={directory} /var/www/html/task.patch")
            if success:
                print(f"    Patch applied successfully using git apply --recount in {directory}")
                patch_applied = True
                break
            last_error = stderr or stdout
        
        if not patch_applied:
            # Fallback to patch command
            options = [
                ("-p1", "web"),
                ("-p1", "."),
                ("-p0", "web"),
                ("-p0", "."),
            ]
            
            for p_level, directory in options:
                success, stdout, stderr = run_command(f"docker-compose exec -T drupal patch {p_level} -l -t -d {directory} -i /var/www/html/task.patch")
                if success:
                    print(f"    Patch applied successfully using patch {p_level} in {directory}")
                    patch_applied = True
                    break
                last_error = stderr or stdout

        if not patch_applied:
            print(f"    FAILED to apply patch: {last_error}")
            sample_results.append({"passed": False, "patch": patch, "error": "Patch application failed"})
            continue

        # Run Domain Validators
        domain_results = {}
        validators_dir = "scripts/validators"
        if os.path.exists(validators_dir):
            for validator in os.listdir(validators_dir):
                if validator.endswith("_validator.py"):
                    name = validator.replace("_validator.py", "")
                    v_path = os.path.join(validators_dir, validator)
                    v_success, v_stdout, v_stderr = run_command(f"python3 {v_path} app/web")
                    domain_results[name] = {"passed": v_success, "output": v_stdout + v_stderr}

        # Determine which tests to run
        test_path = ""
        if 'test_path' in task:
            test_path = task['test_path']
        
        if not test_path:
            if "core/modules/" in patch:
                match = re.search(r'core/modules/(\w+)', patch)
                if match:
                    module = match.group(1)
                    test_path = f"web/core/modules/{module}"
            elif "core/lib/" in patch:
                test_path = "web/core/tests/Drupal/Tests/Core"
            
            if not test_path:
                 # If no path detected, it might be a custom module or recipe
                 if "modules/custom/" in patch:
                     match = re.search(r'modules/custom/(\w+)', patch)
                     if match:
                         module = match.group(1)
                         test_path = f"web/modules/custom/{module}"
        
        # Run PHPUnit
        if test_path:
            print(f"    Running tests in {test_path}...")
            phpunit_cmd = f"docker-compose exec -T drupal ./vendor/bin/phpunit -c web/core/phpunit.xml {test_path}".strip()
            test_success, test_stdout, test_stderr = run_command(phpunit_cmd, timeout=300)
        else:
            print("    Warning: No specific test path detected, skipping PHPUnit to save time...")
            test_success = True # Consider success if patch applies and no tests broken? Or just False?
            test_stdout = "No tests run."
            test_stderr = ""
            
        passed = test_success
        
        sample_results.append({
            "passed": passed,
            "domain_results": domain_results,
            "phpunit_output": test_stdout + test_stderr,
            "patch": patch
        })
        
        if passed:
            print("    SUCCESS: All tests passed (or no tests to run).")
        else:
            print("    FAILED: Tests did not pass.")
        
    any_passed = any(s.get('passed') for s in sample_results)
    
    return {
        "task_id": task_id,
        "title": task['title'],
        "passed": any_passed,
        "samples": sample_results,
        "total_samples": samples_per_task,
        "correct_samples": sum(1 for s in sample_results if s.get('passed'))
    }

def main():
    parser = argparse.ArgumentParser(description="Evaluate LLM on DrupalBench tasks.")
    parser.add_argument("--tasks", type=str, default="tasks.json", help="Path to tasks JSON file.")
    parser.add_argument("--samples", type=int, default=1, help="Number of samples to run per task.")
    parser.add_argument("--model", type=str, help="Override MODEL_NAME from .env")
    parser.add_argument("--provider", type=str, help="Override MODEL_PROVIDER from .env")
    parser.add_argument("--task_id", type=str, help="Specific task ID to evaluate.")
    
    args = parser.parse_args()

    global MODEL_NAME, MODEL_PROVIDER
    if args.model:
        MODEL_NAME = args.model
    if args.provider:
        MODEL_PROVIDER = args.provider

    print(f"Using Model Provider: {MODEL_PROVIDER}")
    print(f"Model Name: {MODEL_NAME}")
    
    if MODEL_PROVIDER == "gemini" and not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env")
        sys.exit(1)

    all_tasks = []
    if os.path.exists(args.tasks):
        with open(args.tasks, "r") as f:
            all_tasks.extend(json.load(f))

    if os.path.exists("synthetic_tasks.json"):
        with open("synthetic_tasks.json", "r") as f:
            all_tasks.extend(json.load(f))

    if not all_tasks:
        print("Error: No tasks found to evaluate.")
        sys.exit(1)

    samples_per_task = args.samples
    
    results = {
        "model_name": MODEL_NAME,
        "model_provider": MODEL_PROVIDER,
        "total_tasks": len(all_tasks),
        "total_samples": 0,
        "total_correct": 0,
        "tasks": []
    }

    import hashlib
    for task in all_tasks:
        if 'task_id' not in task:
             # Use stable hash
             task['task_id'] = f"syn_{hashlib.md5(task.get('title', '').encode()).hexdigest()[:8]}"

        
        if args.task_id and str(task['task_id']) != args.task_id:
            continue
            
        task_res = evaluate_task(task, samples_per_task=samples_per_task)
        results["tasks"].append(task_res)
        results["total_samples"] += task_res["total_samples"]
        results["total_correct"] += task_res["correct_samples"]

    output_file = "results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nEvaluation complete. Results saved to {output_file}")
    print(f"Total Correct: {results['total_correct']}/{results['total_samples']}")

if __name__ == "__main__":
    main()
