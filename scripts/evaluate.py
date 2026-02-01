import os
import json
import requests
import subprocess
import time
import sys
import re

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

def run_command(command, shell=True):
    try:
        result = subprocess.run(command, shell=shell, check=False, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def call_model(prompt):
    system_instruction = """You are an expert Drupal 11 developer. 
Solve the following problem by providing a valid git diff (patch).
The patch should be applicable to a standard Drupal 11 installation using `patch -p1`.
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
    # Extract diff if wrapped in markdown
    if "```" in text:
        match = re.search(r'```(?:diff|patch|php)?\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)
    
    # Remove any leading text before 'diff --git'
    if 'diff --git' in text:
        text = text[text.find('diff --git'):]
    
    return text.strip()

def reset_environment():
    print("  Resetting environment...")
    run_command("docker-compose exec -T drupal git reset --hard HEAD")
    run_command("docker-compose exec -T drupal git clean -fd")

def evaluate_task(task, samples_per_task=1):
    task_id = task['task_id']
    print(f"Evaluating Task {task_id}: {task['title']}")
    
    sample_results = []
    
    for i in range(samples_per_task):
        print(f"  Sample {i+1}/{samples_per_task}...")
        reset_environment()
        
        patch, error = call_model(task['prompt'])
        if error or patch is None:
            print(f"    Error calling model: {error or 'No patch returned'}")
            sample_results.append({"passed": False, "error": error or "No patch returned"})
            continue

        # Save patch and copy to container
        with open("temp.patch", "w") as f:
            f.write(patch)
        
        run_command("docker cp temp.patch $(docker-compose ps -q drupal):/var/www/html/task.patch")
        
        # Apply patch
        success, stdout, stderr = run_command(f"docker-compose exec -T drupal patch -p1 < temp.patch")
        if not success:
            print(f"    FAILED to apply patch: {stderr or stdout}")
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
                    v_success, v_stdout, v_stderr = run_command(f"python3 {v_path} app/web/modules/custom")
                    domain_results[name] = {"passed": v_success, "output": v_stdout + v_stderr}

        # Run PHPUnit
        test_success, test_stdout, test_stderr = run_command("docker-compose exec -T drupal ./vendor/bin/phpunit")
        
        passed = test_success # Correctness is primarily defined by tests passing
        
        sample_results.append({
            "passed": passed,
            "domain_results": domain_results,
            "phpunit_output": test_stdout + test_stderr,
            "patch": patch
        })
        
        if passed:
            print("    SUCCESS: All tests passed.")
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
    print(f"Using Model Provider: {MODEL_PROVIDER}")
    print(f"Model Name: {MODEL_NAME}")
    
    if MODEL_PROVIDER == "gemini" and not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env")
        sys.exit(1)

    tasks_path = "tasks.json"
    if len(sys.argv) > 1:
        tasks_path = sys.argv[1]

    if not os.path.exists(tasks_path):
        print(f"Error: Tasks file not found: {tasks_path}")
        sys.exit(1)

    with open(tasks_path, "r") as f:
        tasks = json.load(f)

    # For testing, limit to first 1 tasks
    test_limit = 1
    tasks_to_run = tasks[:test_limit]
    
    results = {
        "model_name": MODEL_NAME,
        "model_provider": MODEL_PROVIDER,
        "total_tasks": len(tasks_to_run),
        "total_samples": 0,
        "total_correct": 0,
        "tasks": []
    }

    for task in tasks_to_run:
        task_res = evaluate_task(task, samples_per_task=1)
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
