import re
import sys
import os

def check_phpunit_attributes(content):
    violations = []
    # Check for @dataProvider
    if re.search(r'@dataProvider\s+\w+', content):
        violations.append("Use #[DataProvider('methodName')] attribute instead of @dataProvider annotation.")
    
    # Check for @depends
    if re.search(r'@depends\s+\w+', content):
        violations.append("Use #[Depends('methodName')] attribute instead of @depends annotation.")

    # Check for expectError()
    if re.search(r'\$this->expectError\(', content):
        violations.append("expectError() is deprecated in PHPUnit 10. Use expectException() or attributes.")

    return violations

def check_static_data_providers(content):
    violations = []
    # Find all data provider methods from attributes or annotations
    # (Simplified check: looks for methods that are likely data providers but not static)
    
    # First, find names of data providers
    providers = re.findall(r"#[\\DataProvider\s]*\(['\"](\w+)['\"]\)", content)
    providers += re.findall(r"@dataProvider\s+(\w+)", content)
    
    for provider in set(providers):
        # Look for the method definition and check if it's static
        # This regex is a bit loose but should catch most cases
        method_pattern = rf'public\s+function\s+{provider}\s*\('
        if re.search(method_pattern, content) and not re.search(rf'public\s+static\s+function\s+{provider}', content):
            violations.append(f"Data provider method '{provider}' must be static in PHPUnit 10.")
            
    return violations

def check_drupal_attributes(content):
    violations = []
    # In Drupal 11, many plugins should use attributes.
    # Common ones: @Block, @ContentEntityType, @ConfigEntityType
    legacy_annotations = [
        'Block', 'ContentEntityType', 'ConfigEntityType', 'Action', 'Condition', 
        'Constraint', 'FieldFormatter', 'FieldType', 'FieldWidget', 'Filter', 
        'MigrateSource', 'MigrateProcess', 'MigrateDestination', 'RestResource',
        'QueueWorker', 'EntityType'
    ]
    
    for annot in legacy_annotations:
        if re.search(rf'\*\s+@{annot}', content):
            violations.append(f"Use #[{annot}] attribute instead of @{annot} annotation.")
            
    return violations

def validate_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    violations = []
    if file_path.endswith('.php'):
        violations.extend(check_phpunit_attributes(content))
        violations.extend(check_static_data_providers(content))
        violations.extend(check_drupal_attributes(content))
        
    return violations

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend_validator.py <file_or_directory>")
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
                if file.endswith('.php') or file.endswith('.module') or file.endswith('.inc'):
                    path = os.path.join(root, file)
                    v = validate_file(path)
                    if v:
                        all_violations[path] = v
    
    if all_violations:
        print("Backend Validation Failed:")
        for path, violations in all_violations.items():
            print(f"  {path}:")
            for v in violations:
                print(f"    - {v}")
        sys.exit(1)
    else:
        print("Backend Validation Passed.")
        sys.exit(0)
