# CI/CD, Staging Mirror & Feature Flags Runbook (Task 6.6)

## Overview
ShadeNet implements a single-command automated deployment pipeline (`tools/deploy.py`) and a dynamic feature flag subsystem (`shadenet/flags.py`). Changes validate against a staging mirror before promotion to production, while risky changes remain hidden behind feature toggles and canary rollout percentages.

---

## 1. Single-Command Deployment Workflow

```
[Developer / Agent Commit]
           │
           ▼
[Stage 1: Pre-Flight Check]
  • Database integrity check (PRAGMA integrity_check)
  • Static schema verification
           │
           ▼
[Stage 2: Staging Mirror Probe]
  • Subsystem diagnostic health probe (/healthz)
  • Feature flag state synchronization
           │
           ▼
[Stage 3: Promotion & Flag Verification]
  • Single command promotion to Production
  • Live feature flag toggling verified in real-time
           │
           ▼
[Stage 4: Rollback Guard]
  • Automated halt and rollback preservation if any stage fails
```

### Deployment Commands
```bash
# Standard Promotion: Staging -> Verified -> Prod
python3 tools/deploy.py --target prod

# Canary Branch Deployment with live flag flip
python3 tools/deploy.py --target prod --canary --flag-flip canary_release
```

---

## 2. Dynamic Feature Flags (`shadenet/flags.py`)

Flags support live toggles without server restarts:
- **Boolean Gates**: Global on/off switches for features.
- **Canary Rollouts**: Percentage-based hash bucketing (`0..100%`) for incremental traffic exposure.
- **Cohort Overrides**: Dedicated allowlists for stewards (`internal_stewards`).

```bash
# Check status of all flags
python3 -m shadenet.flags --list

# Toggle a flag live in production
python3 -m shadenet.flags --set canary_release --enable --percentage 50
```

---

## 3. Verified Deployments & Canary Evidence

| Date | Deployment ID | Target | Canary | Flag Flips | Health Gate | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2026-10-09** | `deploy_20261009_0617` | `PROD` | Yes | `canary_release=true` | `healthy` | **PROD_LIVE** |
