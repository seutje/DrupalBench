import yaml
import sys
import os
import glob

def validate_sdc_directory(directory):
    violations = []
    
    # SDC components must have a .component.yml file
    yml_files = glob.glob(os.path.join(directory, "*.component.yml"))
    if not yml_files:
        violations.append(f"Missing .component.yml file in SDC directory: {directory}")
        return violations

    for yml_path in yml_files:
        component_name = os.path.basename(yml_path).replace(".component.yml", "")
        
        # Must have a .twig file matching the component name
        twig_path = os.path.join(directory, f"{component_name}.twig")
        if not os.path.exists(twig_path):
            violations.append(f"Missing {component_name}.twig for component {component_name}")

        # Validate component.yml content
        try:
            with open(yml_path, 'r') as f:
                data = yaml.safe_load(f)
                
            if not data:
                violations.append(f"Empty or invalid YAML in {yml_path}")
                continue

            # Check for props and slots
            if 'props' in data:
                if not isinstance(data['props'], dict) or 'type' not in str(data['props']):
                    violations.append(f"Props in {yml_path} should define types (JSON schema style).")
            
            # SDC encourages distinguishing slots
            if 'slots' in data:
                if not isinstance(data['slots'], dict):
                    violations.append(f"Slots in {yml_path} should be a dictionary.")

        except Exception as e:
            violations.append(f"Error parsing {yml_path}: {str(e)}")

    return violations

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python frontend_validator.py <sdc_directory_or_parent>")
        sys.exit(1)

    target = sys.argv[1]
    all_violations = {}

    # Check if target is itself an SDC dir (has .component.yml) or parent of them
    if any(f.endswith(".component.yml") for f in os.listdir(target) if os.path.isfile(os.path.join(target, f))):
        v = validate_sdc_directory(target)
        if v:
            all_violations[target] = v
    else:
        # Search for subdirectories that look like SDC components
        for root, dirs, files in os.walk(target):
            if any(f.endswith(".component.yml") for f in files):
                v = validate_sdc_directory(root)
                if v:
                    all_violations[root] = v

    if all_violations:
        print("Frontend (SDC) Validation Failed:")
        for path, violations in all_violations.items():
            print(f"  {path}:")
            for v in violations:
                print(f"    - {v}")
        sys.exit(1)
    else:
        print("Frontend (SDC) Validation Passed.")
        sys.exit(0)
