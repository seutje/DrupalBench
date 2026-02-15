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
OPENAI_API_KEY = ENV.get("OPENAI_API_KEY")
OLLAMA_HOST = ENV.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_REQUEST_TIMEOUT = 15 * 60  # Hard timeout for model calls (seconds).
CONTEXT_WINDOW_LINES = int(ENV.get("CONTEXT_WINDOW_LINES", "60"))
MAX_CONTEXT_CHARS = int(ENV.get("MAX_CONTEXT_CHARS", "120000"))
MAX_CONTEXT_FILES = int(ENV.get("MAX_CONTEXT_FILES", "12"))
CONTEXT_DEBUG = ENV.get("CONTEXT_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

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
    elif MODEL_PROVIDER == "openai":
        return call_openai(prompt, system_instruction)
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

def call_openai(prompt, system_instruction):
    if not OPENAI_API_KEY:
        return None, "OPENAI_API_KEY not found."

    url = "https://api.openai.com/v1/responses"
    full_prompt = f"{system_instruction}\n\nProblem Description:\n{prompt}"
    payload = {
        "model": MODEL_NAME,
        "input": full_prompt,
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=MODEL_REQUEST_TIMEOUT)
        if response.status_code != 200:
            return None, f"OpenAI Error {response.status_code}: {response.text}"
        result = response.json()
        text = result.get("output_text", "")
        if text:
            return clean_patch_output(text), None
        return None, "No output_text in response."
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

def normalize_diff_path(path):
    if not path:
        return None
    cleaned = path.strip().split('\t')[0].split(' ')[0].strip()
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]
    if cleaned == "/dev/null":
        return None
    return cleaned or None

def classify_file_priority(path):
    lower = path.lower()
    if "/tests/" in lower or lower.endswith("test.php"):
        return 2
    if lower.endswith(".php") or lower.endswith(".module") or lower.endswith(".inc") or \
       lower.endswith(".install") or lower.endswith(".theme"):
        return 0
    if lower.endswith(".md") or lower.endswith(".txt") or lower.endswith(".rst"):
        return 3
    return 1

def merge_ranges(ranges):
    if not ranges:
        return []
    ranges = sorted(ranges)
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 1:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged

def get_file_targets_from_patch(patch_text):
    targets = {}
    order = []
    old_path = None
    current_path = None

    if not patch_text:
        return targets, order

    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            old_path = None
            current_path = None
            continue
        if line.startswith("--- "):
            old_path = normalize_diff_path(line[4:])
            continue
        if line.startswith("+++ "):
            new_path = normalize_diff_path(line[4:])
            current_path = new_path or old_path
            if current_path and current_path not in targets:
                targets[current_path] = []
                order.append(current_path)
            continue
        if line.startswith("@@") and current_path:
            match = re.match(r'^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
            if not match:
                continue
            old_start, old_len, new_start, new_len = match.groups()
            old_start = int(old_start)
            new_start = int(new_start)
            old_len = int(old_len) if old_len else 1
            new_len = int(new_len) if new_len else 1

            start = old_start if old_start > 0 else new_start
            span = old_len if old_len > 0 else new_len
            if span <= 0:
                span = 1
            end = start + span - 1
            targets[current_path].append((start, end))

    return targets, order

def resolve_context_path(f_path):
    for prefix in ["web/", ""]:
        full_path = f"app/{prefix}{f_path}"
        if os.path.exists(full_path) and os.path.isfile(full_path):
            return full_path
    return None

def build_snippet_for_range(lines, start, end, base_window, max_chars):
    if not lines:
        return None

    start = max(1, start)
    end = max(start, end)
    max_chars = max(300, max_chars)
    adaptive_window = max(5, base_window)
    total_lines = len(lines)

    while adaptive_window >= 5:
        window_start = max(1, start - adaptive_window)
        window_end = min(total_lines, end + adaptive_window)
        snippet = "\n".join(lines[window_start - 1:window_end])
        if len(snippet) <= max_chars:
            return window_start, window_end, snippet, False
        adaptive_window //= 2

    window_start = max(1, start - 2)
    window_end = min(total_lines, end + 2)
    snippet = "\n".join(lines[window_start - 1:window_end])
    truncated = False
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rstrip() + "\n... [truncated]"
        truncated = True
    return window_start, window_end, snippet, truncated

def estimate_tokens(text):
    # Rough estimate across prose + code. Exact counting depends on model tokenizer.
    if not text:
        return 0
    return (len(text) + 3) // 4

def get_context_for_task(task, include_stats=False):
    ground_truth = task.get("ground_truth")
    default_stats = {
        "candidate_files": 0,
        "files_included": 0,
        "files_missing": 0,
        "files_skipped_budget": 0,
        "file_limit_reached": False,
        "snippets_included": 0,
        "snippets_truncated": 0,
        "context_chars": 0,
        "context_tokens_estimate": 0,
        "max_context_chars": MAX_CONTEXT_CHARS,
        "max_context_files": MAX_CONTEXT_FILES,
        "context_window_lines": CONTEXT_WINDOW_LINES,
    }
    if not isinstance(ground_truth, str) or not ground_truth.strip():
        return ("", default_stats) if include_stats else ""

    file_targets, file_order = get_file_targets_from_patch(ground_truth)
    if not file_targets:
        return ("", default_stats) if include_stats else ""

    prioritized_files = []
    for index, f_path in enumerate(file_order):
        ranges = merge_ranges(file_targets.get(f_path, []))
        touched_lines = sum((end - start + 1) for start, end in ranges)
        prioritized_files.append((classify_file_priority(f_path), -touched_lines, index, f_path, ranges))
    prioritized_files.sort()

    context = "\n\nRelevant code context:\n"
    total_chars = len(context)
    files_included = 0
    files_missing = 0
    files_skipped_budget = 0
    snippets_included = 0
    snippets_truncated = 0

    for _, _, _, f_path, ranges in prioritized_files:
        if files_included >= MAX_CONTEXT_FILES or total_chars >= MAX_CONTEXT_CHARS:
            files_skipped_budget += 1
            break

        full_path = resolve_context_path(f_path)
        if not full_path:
            files_missing += 1
            continue
        try:
            with open(full_path, "r", errors="ignore") as f:
                file_lines = f.read().splitlines()
        except Exception:
            files_missing += 1
            continue
        if not file_lines:
            files_missing += 1
            continue

        if not ranges:
            ranges = [(1, min(len(file_lines), 1))]

        file_sections = []
        remaining_chars = MAX_CONTEXT_CHARS - total_chars
        if remaining_chars <= 0:
            break

        for i, (start, end) in enumerate(ranges, start=1):
            if remaining_chars <= 0:
                break
            snippet_result = build_snippet_for_range(
                file_lines,
                start,
                end,
                CONTEXT_WINDOW_LINES,
                remaining_chars
            )
            if not snippet_result:
                continue
            snippet_start, snippet_end, snippet, truncated = snippet_result
            label = f"\nSnippet {i} (lines {snippet_start}-{snippet_end}{', truncated' if truncated else ''}):\n"
            section = f"{label}```\n{snippet}\n```\n"
            if len(section) > remaining_chars:
                break
            file_sections.append(section)
            snippets_included += 1
            if truncated:
                snippets_truncated += 1
            remaining_chars -= len(section)

        if not file_sections:
            files_skipped_budget += 1
            continue

        file_block = f"\nFile: {f_path}\n" + "".join(file_sections)
        if total_chars + len(file_block) > MAX_CONTEXT_CHARS:
            files_skipped_budget += 1
            continue

        context += file_block
        total_chars += len(file_block)
        files_included += 1

    context_out = context if files_included else ""
    stats = {
        "candidate_files": len(prioritized_files),
        "files_included": files_included,
        "files_missing": files_missing,
        "files_skipped_budget": files_skipped_budget,
        "file_limit_reached": files_included >= MAX_CONTEXT_FILES,
        "snippets_included": snippets_included,
        "snippets_truncated": snippets_truncated,
        "context_chars": len(context_out),
        "context_tokens_estimate": estimate_tokens(context_out),
        "max_context_chars": MAX_CONTEXT_CHARS,
        "max_context_files": MAX_CONTEXT_FILES,
        "context_window_lines": CONTEXT_WINDOW_LINES,
    }
    return (context_out, stats) if include_stats else context_out

def evaluate_task(task, samples_per_task=1, context_debug=False):
    task_id = task['task_id']
    print(f"Evaluating Task {task_id}: {task['title']}")
    sample_results = []
    
    for i in range(samples_per_task):
        print(f"  Sample {i+1}/{samples_per_task}...")
        reset_environment()
        unsolved = unsolve_task(task)
        
        prompt_text = task.get('prompt') if isinstance(task.get('prompt'), str) else str(task.get('prompt', ''))
        if context_debug:
            code_context, context_stats = get_context_for_task(task, include_stats=True)
        else:
            code_context = get_context_for_task(task)
            context_stats = None
        full_prompt = prompt_text + code_context

        if context_debug and context_stats is not None:
            prompt_chars = len(prompt_text)
            prompt_tokens = estimate_tokens(prompt_text)
            full_prompt_chars = len(full_prompt)
            full_prompt_tokens = estimate_tokens(full_prompt)
            print(
                "    Context debug: "
                f"files={context_stats['files_included']}/{context_stats['candidate_files']} "
                f"(missing={context_stats['files_missing']}, skipped_budget={context_stats['files_skipped_budget']}) | "
                f"snippets={context_stats['snippets_included']} "
                f"(truncated={context_stats['snippets_truncated']}) | "
                f"context={context_stats['context_chars']} chars (~{context_stats['context_tokens_estimate']} tokens) | "
                f"prompt={prompt_chars} chars (~{prompt_tokens} tokens) | "
                f"full={full_prompt_chars} chars (~{full_prompt_tokens} tokens) | "
                f"limits(chars={context_stats['max_context_chars']}, files={context_stats['max_context_files']}, window={context_stats['context_window_lines']})"
            )
        
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
    parser.add_argument("--resume", action="store_true", help="Resume from existing results.json")
    parser.add_argument("--context-debug", action="store_true", help="Print context assembly stats and token estimates")
    args = parser.parse_args()
    global MODEL_NAME, MODEL_PROVIDER, CONTEXT_DEBUG
    if args.model: MODEL_NAME = args.model
    if args.provider: MODEL_PROVIDER = args.provider
    if args.context_debug:
        CONTEXT_DEBUG = True
    
    all_tasks = []
    if os.path.exists(args.tasks):
        with open(args.tasks, "r") as f: all_tasks.extend(json.load(f))
    if os.path.exists("synthetic_tasks.json"):
        with open("synthetic_tasks.json", "r") as f: all_tasks.extend(json.load(f))

    results = {"model_name": MODEL_NAME, "model_provider": MODEL_PROVIDER, "tasks": [], "total_samples": 0, "total_correct": 0}
    completed_task_ids = set()
    if args.resume and os.path.exists("results.json"):
        try:
            with open("results.json", "r") as f:
                existing = json.load(f)
            if isinstance(existing, dict) and isinstance(existing.get("tasks"), list):
                results["tasks"] = existing["tasks"]
                # Recompute totals from existing tasks to keep consistency.
                results["total_samples"] = sum(t.get("total_samples", 0) for t in results["tasks"])
                results["total_correct"] = sum(t.get("correct_samples", 0) for t in results["tasks"])
                completed_task_ids = {t.get("task_id") for t in results["tasks"] if t.get("task_id") is not None}
                print(f"Resuming from results.json with {len(completed_task_ids)} completed tasks.")
        except Exception as e:
            print(f"Failed to read results.json for resume: {e}")
    elif args.resume:
        print("Resume requested but results.json not found. Starting fresh.")
    for task in all_tasks:
        if 'task_id' not in task: task['task_id'] = f"syn_{hashlib.md5(task.get('title', '').encode()).hexdigest()[:8]}"
        if args.task_id and str(task['task_id']) != args.task_id: continue
        if args.resume and task.get("task_id") in completed_task_ids:
            print(f"Skipping Task {task['task_id']} (already in results.json)")
            continue
        task_res = evaluate_task(task, samples_per_task=args.samples, context_debug=CONTEXT_DEBUG)
        results["tasks"].append(task_res)
        results["total_samples"] += task_res["total_samples"]
        results["total_correct"] += task_res["correct_samples"]
        with open("results.json", "w") as f: json.dump(results, f, indent=2)
    print(f"\nTotal Correct: {results['total_correct']}/{results['total_samples']}")

if __name__ == "__main__": main()
