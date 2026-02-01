import re
import sys
import os

def check_access_policy_implementation(content):
    violations = []
    
    # Check if the file seems to implement an Access Policy
    if 'AccessPolicyInterface' not in content and 'AccessPolicyBase' not in content:
        return []

    # Should extend AccessPolicyBase
    if 'class' in content and 'extends AccessPolicyBase' not in content:
        violations.append("Access policies should ideally extend AccessPolicyBase.")

    # Must implement calculatePermissions
    if 'function calculatePermissions' not in content:
        violations.append("Missing calculatePermissions() method.")

    # Must implement getPersistentCacheContexts
    if 'function getPersistentCacheContexts' not in content:
        violations.append("Missing getPersistentCacheContexts() method. This is critical for security and performance.")
    else:
        # Basic check to see if it returns something other than an empty array
        # This is hard with regex, but we can look for 'return [' or 'return array('
        cache_context_match = re.search(r'function getPersistentCacheContexts.*?return\s*\[(.*?)\]', content, re.DOTALL)
        if cache_context_match:
            contexts = cache_context_match.group(1).strip()
            if not contexts:
                violations.append("getPersistentCacheContexts() returns an empty array. Verify if this is intentional.")
        elif 'return [];' in content:
             violations.append("getPersistentCacheContexts() returns an empty array. Verify if this is intentional.")

    return violations

def validate_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return check_access_policy_implementation(content)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python security_validator.py <file_or_directory>")
        sys.exit(1)
    
    target = sys.argv[1]
    all_violations = {}
    
    if os.path.isfile(target):
        v = validate_file(target)
        if v:
            all_violations[target] = v
    elif os.path.isdir(target):
        for root, _, files in os.walk(target):
            for file in files:
                if file.endswith('.php'):
                    path = os.path.join(root, file)
                    v = validate_file(path)
                    if v:
                        all_violations[path] = v
    
    if all_violations:
        print("Security (Access Policy) Validation Failed:")
        for path, violations in all_violations.items():
            print(f"  {path}:")
            for v in violations:
                print(f"    - {v}")
        sys.exit(1)
    else:
        print("Security (Access Policy) Validation Passed.")
        sys.exit(0)
