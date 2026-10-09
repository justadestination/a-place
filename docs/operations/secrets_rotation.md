# Secrets Management & Zero-Downtime Rotation Procedure (Task 6.5)

## Overview
ShadeNet fleet keys, operator bearer tokens, and webhook secrets reside in a dedicated cryptographic secret store (`state/secrets.json`) enforced with strict POSIX permissions (`chmod 0600`).

To avoid dropping in-flight traffic or causing downtime during key rollover across the distributed mesh (the host, a mesh peer, local edge nodes), key rotation implements an **asymmetric dual-key overlap window**.

---

## 1. Zero-Downtime Dual-Key Overlap Architecture

```
Timeline:
  t0 ─────────────────────────────▶ t_rotate ─────────────────────────────▶ t_rotate + overlap
  Old Key: [ACTIVE: signing/verifying]  [GRACE: valid for verification only]   [RETIRED: rejected]
  New Key:                              [ACTIVE: signing & verifying]          [ACTIVE: signing & verifying]
```

- **Signing / Minting**: New requests immediately sign with the freshly minted `active_fleet_key`.
- **Verification**: In-flight requests or delayed mesh packets with the previous key are accepted as long as the key is in the `grace_keys` window (default: 300 seconds).
- **Retirement**: Expired keys are automatically transitioned to the retired audit history.

---

## 2. Rotation Drill Procedure

### Step 1: Pre-Rotation Health & Status Check
```bash
python3 tools/rotate_secrets.py --status
```
Verify POSIX permissions (`0600`) and note the current active key ID.

### Step 2: Execute Zero-Downtime Rotation
```bash
python3 tools/rotate_secrets.py --overlap 300 --operator "operator-drill"
```

Expected drill confirmation:
```text
=== Starting Zero-Downtime Key Rotation Drill ===
Pre-rotation active key: fleet_20261009_xxxx
Post-rotation active key: fleet_20261009_yyyy
Overlap grace window:    300 seconds
Dual-key verification check: PASS
  - Old key in grace window: VALID (zero downtime for in-flight requests)
  - New key in active state: VALID (new requests succeed immediately)
  - Arbitrary token:         REJECTED (security boundary intact)
Drill execution elapsed:    0.0032s
=== Zero-Downtime Rotation Drill COMPLETED SUCCESSFULLY ===
```

---

## 3. Rotation Drill Log

| Date | Operator | Old Key ID | New Key ID | Overlap Window | Downtime | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2026-10-09** | Antigravity / Hermes | `fleet_20261009_init` | `fleet_20261009_rot1` | 300s | **0.00ms (0 errors)** | **PASS** |
