import os
import json
import subprocess
import shutil

def run_command(command, shell=True):
    try:
        result = subprocess.run(command, shell=shell, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr + e.stdout

def verify_task(task):
    print(f"Verifying task: {task['title']}")
    
    # 1. Save ground_truth to a temporary patch file
    patch_file = "temp_task.patch"
    with open(patch_file, "w") as f:
        f.write(task['ground_truth'])
    
    # 2. Try to apply the patch in the container
    # We assume the container is running and 'drupal' service is available
    
    # Copy patch to container
    apply_success, output = run_command(f"docker cp {patch_file} $(docker-compose ps -q drupal):/var/www/html/task.patch")
    if not apply_success:
        print(f"  FAILED to copy patch: {output}")
        return False

    # Apply patch
    apply_success, output = run_command("docker-compose exec -T drupal patch -p1 < task.patch")
    if not apply_success:
        print(f"  FAILED to apply patch: {output}")
        # Clean up
        run_command("docker-compose exec -T drupal rm task.patch")
        return False

    # 3. Basic functional check: can we still run a drush command?
    check_success, output = run_command("docker-compose exec -T drupal ./vendor/bin/drush status")
    if not check_success:
        print(f"  FAILED functional check (drush status): {output}")
    else:
        # 4. If it's a recipe, try to apply it? 
        # (This depends on if the task generated a recipe file)
        # For now, we'll just check if the code is valid by running lint
        lint_success, output = run_command("docker-compose exec -T drupal ./vendor/bin/phpcs --standard=Drupal web/modules/custom")
        # We don't necessarily discard if lint fails, but it's a good indicator.
        # But the plan says "if it fails to install, the task is discarded".
        
        # If there are tests in the patch, run them!
        if "tests/src" in task['ground_truth']:
            print("  Running PHPUnit tests found in patch...")
            test_success, test_output = run_command("docker-compose exec -T drupal ./vendor/bin/phpunit")
            if not test_success:
                print(f"  FAILED PHPUnit tests: {test_output}")
                check_success = False

    # 5. Revert changes for next task
    run_command("docker-compose exec -T drupal git reset --hard HEAD")
    run_command("docker-compose exec -T drupal git clean -fd")
    run_command("docker-compose exec -T drupal rm -f task.patch")
    
    if os.path.exists(patch_file):
        os.remove(patch_file)
        
    return check_success

def main():
    tasks_file = "synthetic_tasks.json"
    if not os.path.exists(tasks_file):
        print(f"Error: {tasks_file} not found. Run task_generator.py first.")
        return

    with open(tasks_file, "r") as f:
        tasks = json.load(f)

    verified_tasks = []
    for task in tasks:
        if verify_task(task):
            print(f"  SUCCESS: Task '{task['title']}' verified.")
            verified_tasks.append(task)
        else:
            print(f"  DISCARDED: Task '{task['title']}' failed verification.")

    output_file = "verified_synthetic_tasks.json"
    with open(output_file, "w") as f:
        json.dump(verified_tasks, f, indent=2)
    
    print(f"Successfully verified {len(verified_tasks)} tasks. Saved to {output_file}")

if __name__ == "__main__":
    main()
