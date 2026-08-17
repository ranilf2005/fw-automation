# Advanced use cases not fully coded in this starter pack

## VPN automation
Recommended beginner path:
1. Build a known-good site-to-site VPN manually in FMC
2. Export or inspect the related objects in API Explorer
3. Identify the fields that vary by site: peer IP, local networks, remote networks, tunnel name
4. Store those values in CSV or JSON
5. Build a small Python script for your exact VPN object path and payload in your FMC version
6. Validate by checking GUI, deployment state, tunnel establishment, and encrypted traffic counters

## Device onboarding
Recommended beginner path:
1. Register one lab FTD manually in FMC
2. Record each field and assignment step
3. Identify reusable assignments: device group, access policy, NAT policy, health policy
4. Build a JSON file with device-specific parameters
5. Use API Explorer to capture the exact endpoint and payload for your FMC version
6. Automate registration and assignment only in a lab first
