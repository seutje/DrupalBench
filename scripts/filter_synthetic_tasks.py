import json
import os
import subprocess
import re

def run_command(command, shell=True):
    try:
        result = subprocess.run(command, shell=shell, check=False, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def reset_environment():
    run_command("docker-compose exec -T drupal git reset --hard HEAD")
    run_command("docker-compose exec -T drupal git clean -fd")

def check_patch(patch):
    with open("filter_temp.patch", "w") as f:
        f.write(patch)
    
    success_id, container_id, _ = run_command("docker-compose ps -q drupal")
    container_id = container_id.strip()
    if not container_id:
        return False, "No container"
        
    run_command(f"docker cp filter_temp.patch {container_id}:/var/www/html/filter_temp.patch")
    
    # Try git apply --check
    for directory in ["web", "."]:
        success, stdout, stderr = run_command(f"docker-compose exec -T drupal git apply --check --recount --whitespace=fix --directory={directory} /var/www/html/filter_temp.patch")
        if success:
            return True, f"Applies in {directory}"
            
    return False, "Does not apply"

def main():
    tasks_file = "synthetic_tasks.json"
    if not os.path.exists(tasks_file):
        print("Tasks file not found.")
        return

    with open(tasks_file, "r") as f:
        tasks = json.load(f)

    print(f"Total synthetic tasks: {len(tasks)}")
    filtered_tasks = []
    
    for i, task in enumerate(tasks):
        print(f"Checking synthetic task {i+1}/{len(tasks)}: {task['title']}...")
        reset_environment()
        applies, msg = check_patch(task['ground_truth'])
        if applies:
            print(f"  OK: {msg}")
            filtered_tasks.append(task)
        else:
            print(f"  REMOVED: {msg}")

    with open("synthetic_tasks_filtered.json", "w") as f:
        json.dump(filtered_tasks, f, indent=2)

    print(f"Filtering complete. {len(filtered_tasks)} synthetic tasks remain.")

if __name__ == "__main__":
    main()
