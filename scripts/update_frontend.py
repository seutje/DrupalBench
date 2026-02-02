import json
import os
import math
import subprocess

def comb(n, k):
    """Calculate combinations nCr."""
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    if k > n // 2:
        k = n - k
    
    numerator = 1
    for i in range(k):
        numerator = numerator * (n - i) // (i + 1)
    return numerator

def calculate_pass_at_k(n, c, k):
    """
    Calculates pass@k metric.
    n: total number of samples
    c: number of correct samples
    k: k value
    """
    if n - c < k:
        return 1.0
    return 1.0 - (comb(n - c, k) / comb(n, k))

def update_frontend():
    results_path = 'results.json'
    frontend_data_path = 'frontend/src/data/mockResults.json'
    
    if not os.path.exists(results_path):
        print(f"Error: {results_path} not found.")
        return

    with open(results_path, 'r') as f:
        data = json.load(f)

    model_name = data.get('model_name', 'Unknown Model')
    tasks = data.get('tasks', [])
    total_tasks = len(tasks)
    
    # Calculate global metrics
    # In DrupalBench, we might have multiple samples per task, or just 1.
    # The frontend expects a single ModelResult which contains an array of tasks.
    
    total_samples = data.get('total_samples', 0)
    total_correct = data.get('total_correct', 0)
    
    # Calculate pass@k
    # If we have 1 sample per task, pass@1 is just accuracy.
    # If we want to be fancy and calculate it per task if multiple samples exist:
    
    pass_at_1_sum = 0
    pass_at_5_sum = 0
    
    for task in tasks:
        n = task.get('total_samples', 1)
        c = task.get('correct_samples', 0)
        
        pass_at_1_sum += calculate_pass_at_k(n, c, 1)
        pass_at_5_sum += calculate_pass_at_k(n, c, 5) if n >= 5 else calculate_pass_at_k(n, c, 1)

    pass_at_1 = pass_at_1_sum / total_tasks if total_tasks > 0 else 0
    pass_at_5 = pass_at_5_sum / total_tasks if total_tasks > 0 else 0

    transformed_tasks = []
    for task in tasks:
        # Determine quality summary
        quality_summary = "Clean"
        if not task.get('passed'):
            first_sample = task.get('samples', [{}])[0]
            error = first_sample.get('error')
            if error:
                quality_summary = error
            elif 'phpunit_output' in first_sample:
                quality_summary = "Test Failures"
            else:
                quality_summary = "Failed"

        transformed_tasks.append({
            "task_id": task.get('task_id'),
            "title": task.get('title'),
            "passed": task.get('passed'),
            "quality_summary": quality_summary,
            "domain_results": {
                "backend": {
                    "passed": task.get('passed'),
                    "output": task.get('samples', [{}])[0].get('phpunit_output', 'No output available')[:1000] # Truncate for frontend
                }
            }
        })

    model_result = {
        "model_name": model_name,
        "total_tasks": total_tasks,
        "total_samples": total_samples,
        "total_correct": total_correct,
        "pass_at_1": pass_at_1,
        "pass_at_5": pass_at_5,
        "tasks": transformed_tasks
    }

    # Load existing results if any to append/update
    existing_results = []
    if os.path.exists(frontend_data_path):
        try:
            with open(frontend_data_path, 'r') as f:
                existing_results = json.load(f)
        except:
            existing_results = []

    # Replace or add the model result
    found = False
    for i, res in enumerate(existing_results):
        if res['model_name'] == model_name:
            existing_results[i] = model_result
            found = True
            break
    
    if not found:
        # Keep gemini-3-flash-preview at the top if it's the new one, or just append
        existing_results.insert(0, model_result)

    with open(frontend_data_path, 'w') as f:
        json.dump(existing_results, f, indent=2)
    
    print(f"Successfully updated {frontend_data_path} with results from {model_name}")

    # Optional: Build the frontend
    print("Building frontend...")
    try:
        subprocess.run(["npm", "run", "build"], cwd="frontend", check=True)
        print("Frontend build successful.")
    except Exception as e:
        print(f"Warning: Frontend build failed: {e}")

if __name__ == "__main__":
    update_frontend()
