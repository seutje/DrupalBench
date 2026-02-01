import subprocess
import sys
import os

def run_drush_recipe(recipe_path):
    # Assumes drush is in the path and we are in a Drupal root or have -r
    # For DrupalBench, we might need to specify the path to the Drupal root
    drupal_root = os.environ.get('DRUPAL_ROOT', '/var/www/html/web')
    
    cmd = ["drush", "recipe", recipe_path, "-r", drupal_root, "--yes"]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def validate_recipe_idempotency(recipe_path):
    if not os.path.exists(recipe_path):
        return [f"Recipe path does not exist: {recipe_path}"]

    violations = []
    
    # First application
    print(f"Applying recipe first time: {recipe_path}")
    res1 = run_drush_recipe(recipe_path)
    if res1.returncode != 0:
        violations.append(f"First application failed: {res1.stderr}")
        return violations

    # Second application (Idempotency check)
    print(f"Applying recipe second time (idempotency check): {recipe_path}")
    res2 = run_drush_recipe(recipe_path)
    if res2.returncode != 0:
        violations.append(f"Second application (idempotency) failed: {res2.stderr}")
    
    # Optionally check if anything was changed that shouldn't have been
    # But usually, if it doesn't error, it's considered idempotent enough for this phase.
    
    return violations

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python recipe_validator.py <recipe_name_or_path>")
        sys.exit(1)

    recipe_target = sys.argv[1]
    
    # If it's a directory but doesn't have recipe.yml, it might be a module/theme containing recipes
    # But usually recipes are standalone directories.
    
    v = validate_recipe_idempotency(recipe_target)
    
    if v:
        print("Recipe Idempotency Validation Failed:")
        for err in v:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("Recipe Idempotency Validation Passed.")
        sys.exit(0)
