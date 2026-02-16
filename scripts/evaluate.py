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
MAX_TOKENS_K = int(ENV.get("MAX_TOKENS", "128"))
MAX_PROMPT_TOKENS = max(1, MAX_TOKENS_K) * 1000
MAX_CONTEXT_CHARS = int(ENV.get("MAX_CONTEXT_CHARS", str(MAX_PROMPT_TOKENS * 10)))
MAX_CONTEXT_FILES = int(ENV.get("MAX_CONTEXT_FILES", "30"))
CONTEXT_DEBUG = ENV.get("CONTEXT_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
MODEL_PROMPT_PREFIX = "Problem Description:\n"
MODEL_SYSTEM_INSTRUCTION = """You are an expert Drupal 11 developer. 
Solve the following problem by providing a valid git diff (patch).
The patch should be applicable to a standard Drupal 11 installation using `git apply -p1`.
Output ONLY the git diff. Do not include markdown code blocks.
Ensure your patch uses a/ and b/ prefixes (e.g., --- a/core/modules/... and +++ b/core/modules/...).
Focus on making the patch compatible with the current file contents provided in the context.
"""

def run_command(command, shell=True, timeout=None):
    try:
        result = subprocess.run(command, shell=shell, check=False, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def ensure_drupal_container_ready():
    success, container_id, stderr = run_command("docker-compose ps -q drupal")
    container_id = container_id.strip()
    if not success or not container_id:
        details = (stderr or "").strip()
        print("ERROR: Drupal container is not available. Start it before running evaluation.")
        if details:
            print(f"  Details: {details[:500]}")
        print("  Try: docker-compose up -d drupal")
        return False

    success, state_raw, state_err = run_command(f"docker inspect -f '{{{{.State.Paused}}}} {{{{.State.Status}}}}' {container_id}")
    if not success:
        details = (state_err or "").strip()
        print("ERROR: Could not inspect Drupal container state.")
        if details:
            print(f"  Details: {details[:500]}")
        return False

    state_parts = state_raw.strip().split()
    is_paused = len(state_parts) > 0 and state_parts[0].lower() == "true"
    status = state_parts[1].lower() if len(state_parts) > 1 else "unknown"

    if is_paused:
        print("ERROR: Drupal container is paused.")
        print("  docker-compose exec fails with: cannot exec in a paused container (use --ignore-paused to override)")
        print("  Unpause with: docker-compose unpause drupal")
        return False

    if status != "running":
        print(f"ERROR: Drupal container is not running (status: {status}).")
        print("  Start it with: docker-compose up -d drupal")
        return False

    return True

def call_model(prompt):
    if MODEL_PROVIDER == "gemini":
        return call_gemini(prompt, MODEL_SYSTEM_INSTRUCTION)
    elif MODEL_PROVIDER == "openai":
        return call_openai(prompt, MODEL_SYSTEM_INSTRUCTION)
    elif MODEL_PROVIDER == "ollama":
        return call_ollama(prompt, MODEL_SYSTEM_INSTRUCTION)
    else:
        return None, f"Unknown model provider: {MODEL_PROVIDER}"

def call_gemini(prompt, system_instruction):
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY not found."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    full_prompt = f"{system_instruction}\n\n{MODEL_PROMPT_PREFIX}{prompt}"
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
    full_prompt = f"{system_instruction}\n\n{MODEL_PROMPT_PREFIX}{prompt}"
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

def call_openai(prompt, system_instruction):
    if not OPENAI_API_KEY:
        return None, "OPENAI_API_KEY not found."

    url = "https://api.openai.com/v1/responses"
    payload = {
        "model": MODEL_NAME,
        "instructions": system_instruction,
        "input": f"{MODEL_PROMPT_PREFIX}{prompt}",
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
        text = extract_openai_output_text(result)
        if text:
            return clean_patch_output(text), None
        return None, f"No text output in OpenAI response ({summarize_openai_response(result)})."
    except Exception as e:
        return None, str(e)

def convert_apply_patch_to_unified(text):
    if not text:
        return text

    markers = ("*** Begin Patch", "*** Update File:", "*** Add File:", "*** Delete File:")
    if not any(marker in text for marker in markers):
        return text

    lines = text.replace('\r\n', '\n').split('\n')
    out = []
    i = 0

    def collect_block(start_index):
        block = []
        j = start_index
        while j < len(lines):
            next_line = lines[j]
            if next_line.startswith("*** "):
                break
            block.append(next_line)
            j += 1
        return block, j

    while i < len(lines):
        line = lines[i]

        if line == "*** Begin Patch":
            i += 1
            continue
        if line == "*** End Patch":
            break
        if line == "*** End of File":
            i += 1
            continue

        if line.startswith("*** Update File: "):
            path = line[len("*** Update File: "):].strip()
            block_lines, i = collect_block(i + 1)
            out.append(f"diff --git a/{path} b/{path}")
            out.append(f"--- a/{path}")
            out.append(f"+++ b/{path}")
            out.extend(block_lines)
            continue

        if line.startswith("*** Add File: "):
            path = line[len("*** Add File: "):].strip()
            block_lines, i = collect_block(i + 1)
            out.append(f"diff --git a/{path} b/{path}")
            out.append("new file mode 100644")
            out.append("--- /dev/null")
            out.append(f"+++ b/{path}")
            if not any(l.startswith("@@") for l in block_lines) and block_lines:
                out.append("@@")
            for block_line in block_lines:
                if block_line.startswith(("+", "@@", "\\")):
                    out.append(block_line)
                elif block_line == "":
                    out.append("+")
                else:
                    out.append("+" + block_line.lstrip(" "))
            continue

        if line.startswith("*** Delete File: "):
            path = line[len("*** Delete File: "):].strip()
            block_lines, i = collect_block(i + 1)
            out.append(f"diff --git a/{path} b/{path}")
            out.append("deleted file mode 100644")
            out.append(f"--- a/{path}")
            out.append("+++ /dev/null")
            if not any(l.startswith("@@") for l in block_lines) and block_lines:
                out.append("@@")
            for block_line in block_lines:
                if block_line.startswith(("-", "@@", "\\")):
                    out.append(block_line)
                elif block_line == "":
                    out.append("-")
                else:
                    out.append("-" + block_line.lstrip(" "))
            continue

        i += 1

    if not out:
        return text
    result = "\n".join(out).rstrip("\n")
    return result + "\n"

def ensure_diff_headers(text):
    if not text:
        return text

    def extract_marker_path(marker_line):
        return marker_line[4:].strip().split('\t')[0].split(' ')[0]

    def to_diff_token(path, default_prefix):
        if path == "/dev/null":
            return path
        if path.startswith("a/") or path.startswith("b/"):
            return path
        return f"{default_prefix}/{path}"

    lines = text.split('\n')
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('--- ') and i + 1 < len(lines) and lines[i + 1].startswith('+++ '):
            has_diff_header = False
            j = len(out) - 1
            while j >= 0:
                prev = out[j].strip()
                if not prev:
                    j -= 1
                    continue
                has_diff_header = prev.startswith("diff --git ")
                break
            if not has_diff_header:
                old_path = extract_marker_path(line)
                new_path = extract_marker_path(lines[i + 1])
                diff_old = to_diff_token(old_path, "a")
                diff_new = to_diff_token(new_path, "b")
                out.append(f"diff --git {diff_old} {diff_new}")
            out.append(line)
            out.append(lines[i + 1])
            i += 2
            continue
        out.append(line)
        i += 1

    result = "\n".join(out).rstrip("\n")
    return result + "\n" if result else ""

def drop_empty_diff_sections(text):
    if not text:
        return text

    lines = text.split('\n')
    out = []
    current_section = []
    in_diff_section = False
    section_has_changes = False

    def flush_section():
        nonlocal current_section, section_has_changes, in_diff_section
        if not current_section:
            return
        if not current_section[0].startswith("diff --git ") or section_has_changes:
            out.extend(current_section)
        current_section = []
        section_has_changes = False
        in_diff_section = False

    for line in lines:
        if line.startswith("diff --git "):
            flush_section()
            current_section = [line]
            in_diff_section = True
            continue

        if in_diff_section:
            current_section.append(line)
            if line.startswith("@@") or line.startswith("new file mode ") or \
               line.startswith("deleted file mode ") or line.startswith("Binary files "):
                section_has_changes = True
            continue

        out.append(line)

    flush_section()
    result = "\n".join(out).rstrip("\n")
    return result + "\n" if result else ""

def clean_patch_output(text):
    text = text.replace('\r\n', '\n')
    code_blocks = re.findall(r'```(?:\w+)?\s*(.*?)\s*```', text, re.DOTALL)
    if code_blocks:
        cleaned_text = ""
        for block in code_blocks:
            if '--- ' in block or '+++ ' in block or '@@' in block or '*** Begin Patch' in block:
                cleaned_text += block + "\n"
        if cleaned_text:
            text = cleaned_text
    
    patterns = ['*** Begin Patch', '*** Update File:', 'diff --git', '--- ', 'Index: ']
    first_idx = len(text)
    found = False
    for p in patterns:
        idx = text.find(p)
        if idx != -1 and idx < first_idx:
            first_idx = idx
            found = True
    
    if found:
        text = text[first_idx:]

    text = convert_apply_patch_to_unified(text)
    control_lines = {"*** begin patch", "*** end patch", "*** end of patch", "*** end of file"}
    filtered_lines = [line for line in text.split('\n') if line.strip().lower() not in control_lines]
    text = ensure_diff_headers("\n".join(filtered_lines))
    return text

def fix_hunk_headers(patch_text):
    if not patch_text:
        return patch_text

    def parse_diff_git_paths(diff_line):
        match = re.match(r'^diff --git\s+(\S+)\s+(\S+)', diff_line)
        if not match:
            return None, None
        return match.group(1), match.group(2)

    def parse_hunk_header(header_line):
        match = re.match(r'^@@\s*-(\d+)?(?:,(\d+))?\s+\+(\d+)?(?:,(\d+))?\s*@@(.*)$', header_line)
        if not match:
            return None
        old_start, old_len, new_start, new_len, rest = match.groups()
        if old_start is None or new_start is None:
            return None
        return int(old_start), old_len, int(new_start), new_len, rest

    def normalize_hunk_lines(raw_hunk_lines):
        normalized = []
        old_len = 0
        new_len = 0
        has_changes = False
        for h_line in raw_hunk_lines:
            if h_line.startswith('-'):
                old_len += 1
                has_changes = True
                normalized.append(h_line)
            elif h_line.startswith('+'):
                new_len += 1
                has_changes = True
                normalized.append(h_line)
            elif h_line.startswith(' '):
                old_len += 1
                new_len += 1
                normalized.append(h_line)
            elif h_line.startswith('\\'):
                normalized.append(h_line)
            elif h_line == '':
                old_len += 1
                new_len += 1
                normalized.append(' ')
            else:
                old_len += 1
                new_len += 1
                normalized.append(' ' + h_line)
        return normalized, old_len, new_len, has_changes

    def ensure_file_markers(current_old, current_new):
        markers = []
        if current_old:
            markers.append(f"--- {current_old}")
        if current_new:
            markers.append(f"+++ {current_new}")
        return markers

    lines = patch_text.split('\n')
    fixed_lines = []
    i = 0
    current_old_path = None
    current_new_path = None
    saw_old_marker = False
    saw_new_marker = False
    old_cursor = 1
    new_cursor = 1
    force_old_dev_null = False
    force_new_dev_null = False

    def maybe_emit_missing_file_markers():
        nonlocal saw_old_marker, saw_new_marker
        if not saw_old_marker or not saw_new_marker:
            fixed_lines.extend(ensure_file_markers(current_old_path, current_new_path))
            saw_old_marker = saw_old_marker or bool(current_old_path)
            saw_new_marker = saw_new_marker or bool(current_new_path)

    while i < len(lines):
        line = lines[i]
        if line.startswith('diff --git '):
            diff_old, diff_new = parse_diff_git_paths(line)
            current_old_path = diff_old
            current_new_path = diff_new
            saw_old_marker = False
            saw_new_marker = False
            old_cursor = 0 if diff_old == '/dev/null' else 1
            new_cursor = 0 if diff_new == '/dev/null' else 1
            force_old_dev_null = False
            force_new_dev_null = False
            fixed_lines.append(line)
            i += 1
            continue

        if line.startswith('new file mode '):
            force_old_dev_null = True
            current_old_path = '/dev/null'
            old_cursor = 0
            fixed_lines.append(line)
            i += 1
            continue

        if line.startswith('deleted file mode '):
            force_new_dev_null = True
            current_new_path = '/dev/null'
            new_cursor = 0
            fixed_lines.append(line)
            i += 1
            continue

        if line.startswith('--- '):
            old_marker = '/dev/null' if force_old_dev_null else line[4:].strip()
            current_old_path = old_marker
            saw_old_marker = True
            if current_old_path == '/dev/null':
                old_cursor = 0
            fixed_lines.append(f"--- {old_marker}")
            i += 1
            continue

        if line.startswith('+++ '):
            new_marker = '/dev/null' if force_new_dev_null else line[4:].strip()
            current_new_path = new_marker
            saw_new_marker = True
            if current_new_path == '/dev/null':
                new_cursor = 0
            fixed_lines.append(f"+++ {new_marker}")
            i += 1
            continue

        if line.startswith('@@'):
            maybe_emit_missing_file_markers()
            raw_hunk_lines = []
            j = i + 1
            while j < len(lines):
                h_line = lines[j]
                if h_line.startswith('@@') or h_line.startswith('diff --git') or \
                   h_line.startswith('--- ') or h_line.startswith('+++ ') or \
                   h_line.startswith('Index: ') or h_line.startswith('*** '):
                    break
                raw_hunk_lines.append(h_line)
                j += 1

            normalized_hunk_lines, actual_old_len, actual_new_len, has_changes = normalize_hunk_lines(raw_hunk_lines)
            parsed_header = parse_hunk_header(line)
            if parsed_header:
                old_start, _, new_start, _, rest = parsed_header
            else:
                old_start = old_cursor
                new_start = new_cursor
                rest = ""

            if old_start is None:
                old_start = old_cursor
            if new_start is None:
                new_start = new_cursor

            if not has_changes:
                old_cursor = old_start + actual_old_len
                new_cursor = new_start + actual_new_len
                i = j
                continue

            new_header = f"@@ -{old_start},{actual_old_len} +{new_start},{actual_new_len} @@{rest}"
            fixed_lines.append(new_header)
            fixed_lines.extend(normalized_hunk_lines)
            old_cursor = old_start + actual_old_len
            new_cursor = new_start + actual_new_len
            i = j
            continue

        fixed_lines.append(line)
        i += 1
    result = '\n'.join(fixed_lines).rstrip('\n')
    if result:
        result += '\n'
    return drop_empty_diff_sections(result)

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

def trim_text_to_token_budget(text, token_budget, suffix="\n... [truncated]"):
    if not text:
        return ""
    if token_budget <= 0:
        return ""
    max_chars = token_budget * 4
    if len(text) <= max_chars:
        return text
    keep_chars = max_chars - len(suffix)
    if keep_chars < 0:
        keep_chars = max_chars
    return text[:keep_chars].rstrip() + suffix

def get_context_for_task(task, include_stats=False, max_context_chars=None):
    context_char_budget = MAX_CONTEXT_CHARS if max_context_chars is None else max(0, int(max_context_chars))
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
        "max_context_chars": context_char_budget,
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
        if files_included >= MAX_CONTEXT_FILES or total_chars >= context_char_budget:
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
        remaining_chars = context_char_budget - total_chars
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
        if total_chars + len(file_block) > context_char_budget:
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
        "max_context_chars": context_char_budget,
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
        
        raw_prompt_text = task.get('prompt') if isinstance(task.get('prompt'), str) else str(task.get('prompt', ''))
        reserved_tokens = estimate_tokens(MODEL_SYSTEM_INSTRUCTION) + estimate_tokens(MODEL_PROMPT_PREFIX)
        prompt_token_budget = max(0, MAX_PROMPT_TOKENS - reserved_tokens)
        prompt_text = trim_text_to_token_budget(raw_prompt_text, prompt_token_budget)
        prompt_tokens = estimate_tokens(prompt_text)
        remaining_prompt_tokens = max(0, prompt_token_budget - prompt_tokens)
        context_char_budget = min(MAX_CONTEXT_CHARS, remaining_prompt_tokens * 4)
        if context_debug:
            code_context, context_stats = get_context_for_task(
                task,
                include_stats=True,
                max_context_chars=context_char_budget
            )
        else:
            code_context = get_context_for_task(task, max_context_chars=context_char_budget)
            context_stats = None
        full_prompt = prompt_text + code_context

        if context_debug and context_stats is not None:
            prompt_chars = len(prompt_text)
            prompt_was_truncated = len(prompt_text) < len(raw_prompt_text)
            full_prompt_chars = len(full_prompt)
            full_prompt_tokens = estimate_tokens(full_prompt)
            full_request_tokens = full_prompt_tokens + reserved_tokens
            print(
                "    Context debug: "
                f"files={context_stats['files_included']}/{context_stats['candidate_files']} "
                f"(missing={context_stats['files_missing']}, skipped_budget={context_stats['files_skipped_budget']}) | "
                f"snippets={context_stats['snippets_included']} "
                f"(truncated={context_stats['snippets_truncated']}) | "
                f"context={context_stats['context_chars']} chars (~{context_stats['context_tokens_estimate']} tokens) | "
                f"prompt={prompt_chars} chars (~{prompt_tokens} tokens{', truncated' if prompt_was_truncated else ''}) | "
                f"full={full_prompt_chars} chars (~{full_prompt_tokens} tokens) | "
                f"request_estimate=~{full_request_tokens} tokens | "
                f"limits(tokens={MAX_PROMPT_TOKENS}, chars={context_stats['max_context_chars']}, files={context_stats['max_context_files']}, window={context_stats['context_window_lines']})"
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
        last_apply_error = ""
        # Try git apply first with various options
        for directory in ["web", "."]:
            for p_arg in ["-p1", "-p0", "-p2"]:
                for extra in ["", "--unidiff-zero", "--3way", "--3way --unidiff-zero"]:
                    cmd = f"docker-compose exec -T drupal git apply -v {extra} --recount --whitespace=fix {p_arg} --directory={directory} /var/www/html/task.patch"
                    success, stdout, stderr = run_command(cmd)
                    if success:
                        print(f"    Patch applied with git apply {extra} {p_arg} --directory={directory}")
                        patch_applied = True
                        break
                    output = f"{stdout}{stderr}".strip()
                    if output:
                        last_apply_error = output
                if patch_applied: break
            if patch_applied: break
        
        if not patch_applied:
            # Fallback to patch utility
            for directory in ["web", "."]:
                for p_level in ["-p1", "-p0", "-p2"]:
                    cmd = f"docker-compose exec -T drupal patch {p_level} --fuzz=3 -l -t -N -d {directory} -i /var/www/html/task.patch"
                    success, stdout, stderr = run_command(cmd)
                    if success:
                        print(f"    Patch applied with patch {p_level} --fuzz in {directory}")
                        patch_applied = True
                        break
                    output = f"{stdout}{stderr}".strip()
                    if output:
                        last_apply_error = output
                if patch_applied: break
                
        if not patch_applied:
            print(f"    FAILED to apply patch.")
            failure = {"passed": False, "patch": patch, "error": "Patch application failed"}
            if last_apply_error:
                failure["apply_error"] = last_apply_error[:3000]
            sample_results.append(failure)
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

    if not ensure_drupal_container_ready():
        sys.exit(1)
    
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
