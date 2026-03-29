# Cisco Secure Firewall Automation Starter Pack

This repository is a beginner-friendly starter kit for Cisco Secure Firewall automation with FMC-managed FTD devices.

It includes:
- Python scripts for inventory, objects, services, rules, NAT, and compliance reporting
- Input CSV templates
- Ansible starter playbooks
- Terraform starter files
- Validation steps and test commands

Important:
- Test in a lab or a non-production policy first.
- Some API paths and payload details vary by FMC version. Use FMC API Explorer to confirm object fields and endpoints before production use.
- Cisco documents that the FMC API uses token-based authentication, API Explorer is available on FMC, the Ansible collection uses the FMC REST API, and the Terraform provider also communicates with FMC via REST. See docs/REFERENCES.md.

## Recommended learning order
1. Inventory export
2. Object creation
3. Service object creation
4. Access rule creation
5. NAT rule creation
6. Compliance report
7. Ansible versions of the same tasks
8. Terraform for repeatable object creation

## Repository layout
```text
secure-firewall-automation-starter/
├── docs/
├── inputs/
├── outputs/
├── python/
├── ansible/
└── terraform/
```

## 1. Install software
Install on your automation laptop or automation VM:
- Python 3.11+
- VS Code
- Git
- Postman
- Ansible
- Terraform

## 2. Create and activate Python virtual environment
### Linux/macOS
```bash
cd secure-firewall-automation-starter
python3 -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
```

### Windows PowerShell
```powershell
cd secure-firewall-automation-starter
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r python\requirements.txt
```

## 3. Configure environment
Copy the example file and update it with your FMC values.

### Linux/macOS
```bash
cp python/.env.example python/.env
```

### Windows PowerShell
```powershell
Copy-Item python\.env.example python\.env
```

Then edit `python/.env` and set:
- `FMC_HOST`
- `FMC_USERNAME`
- `FMC_PASSWORD`
- `FMC_DOMAIN_UUID` if you already know it, otherwise leave blank and discover it with the inventory script
- `VERIFY_SSL` true or false
- `ACCESS_POLICY_ID`
- `NAT_POLICY_ID`

## 4. First tests
### 4.1 Inventory export
```bash
python python/inventory/get_inventory.py
```
Verify files were created under `outputs/reports/`.

### 4.2 Validate objects input
```bash
python python/objects/validate_objects.py inputs/objects.csv
```

### 4.3 Create objects
```bash
python python/objects/create_objects.py inputs/objects.csv
```

### 4.4 Validate services
```bash
python python/services/validate_services.py inputs/services.csv
```

### 4.5 Create service objects
```bash
python python/services/create_services.py inputs/services.csv
```

### 4.6 Validate rules
```bash
python python/policy/validate_rules.py inputs/rules.csv
```

### 4.7 Create access rules
```bash
python python/policy/create_rules.py inputs/rules.csv
```

### 4.8 Validate NAT input
```bash
python python/nat/validate_nat.py inputs/nat.csv
```

### 4.9 Create NAT rules
```bash
python python/nat/create_manual_nat.py inputs/nat.csv
```

### 4.10 Compliance report
```bash
python python/reports/compliance_report.py
```

## 5. Verification checklist for every use case
For each use case, verify in three places:
1. Script output and CSV/JSON report
2. API GET result from a follow-up script or Postman
3. FMC GUI in the correct section

For policy and NAT changes, also verify:
4. Deployment state in FMC
5. Functional behavior on the target FTD device

## 6. Ansible
Install the collection:
```bash
ansible-galaxy collection install cisco.fmcansible
```

Edit `ansible/group_vars/all.yml` with FMC details, then run:
```bash
ansible-playbook -i ansible/inventory.yml ansible/playbooks/get_domain.yml
ansible-playbook -i ansible/inventory.yml ansible/playbooks/get_network_objects.yml
ansible-playbook -i ansible/inventory.yml ansible/playbooks/create_network_objects.yml
```

## 7. Terraform
Terraform resource support depends on FMC version. Start with provider init and use a single object resource only after confirming the exact resource names your provider version supports.

```bash
cd terraform
terraform init
terraform validate
terraform plan -var="fmc_url=https://YOUR-FMC" -var="fmc_username=apiuser" -var="fmc_password=changeme"
```

## 8. Rollback approach
- Objects: delete only the newly created test objects
- Rules: delete the newly created test rules, then deploy
- NAT: delete the newly created NAT rules, then deploy
- Reports: no rollback needed because read-only

## 9. Known limits of this starter pack
- Deployment APIs differ across versions and workflows; use API Explorer to confirm deploy task payloads in your FMC version.
- VPN and device onboarding vary more by release and design, so they are documented as guided steps in `docs/ADVANCED_USE_CASES.md` rather than fully coded here.
- Terraform resource names and supported resources depend on provider and FMC version.
