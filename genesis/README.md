# The Genesis Method

Sentinel Stratos Strategies | Forensic Apple Platform

## What This Folder Contains
- `Genesis-Method-Overview.md` - High-level architecture and intent
- `Genesis-Configuration-Guide.md` - Configuration schema and options
- `Genesis-Method-Complete-Guide.pdf` - Full guide (source of truth)

## Safe Operating Notes
This build does not change macOS security settings and does not automate kernel or SIP changes.
If you choose to adjust system protections for a specific workflow, consult official Apple documentation and proceed only if you fully understand the security impact.

## Optional Genesis Loop (Manual)
A non-destructive, user-controlled loop script is available. It will repeatedly run the full workflow and generate reports on an interval you choose.

Usage:
```bash
/Users/house/genesis/genesis/genesis_loop.sh house
# or
/Users/house/genesis/genesis/genesis_loop.sh fam
```

Stop it safely by creating the stop file:
```bash
touch /Users/house/genesis/genesis/STOP
```

Set interval (seconds) before starting:
```bash
GENESIS_INTERVAL=3600 /Users/house/genesis/genesis/genesis_loop.sh house
```
