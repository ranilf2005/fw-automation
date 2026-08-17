# Testing and validation

## Golden rule
Always test in this order:
1. Validation only
2. Read-only inventory
3. Small write test against a lab or test policy
4. GUI verification
5. Functional verification
6. Rollback test

## Object automation validation
- Run `validate_objects.py`
- Confirm CSV has no errors
- Run `create_objects.py`
- Open FMC GUI and verify the objects are visible under Object Management
- Re-run the script; it should skip duplicates instead of creating them again

## Service object validation
- Run `validate_services.py`
- Run `create_services.py`
- Verify protocol and port values in FMC GUI

## Rule automation validation
- Run `validate_rules.py`
- Confirm all referenced objects and zones exist
- Run `create_rules.py`
- Verify the rules are present in the target access policy
- Deploy in FMC if needed for your environment
- Generate test traffic and check logs or hit counts

## NAT validation
- Run `validate_nat.py`
- Run `create_manual_nat.py`
- Confirm the NAT rules appear in FMC under the correct NAT policy
- Deploy in FMC if needed
- Generate traffic and verify translation behavior

## Compliance reporting validation
- Run `compliance_report.py`
- Confirm CSV and summary files exist
- Manually spot-check a few findings in the FMC GUI
