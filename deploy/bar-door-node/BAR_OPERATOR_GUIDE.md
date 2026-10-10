# ShadeNet Bar Door Node — Venue Operator & Bouncer Field Guide
**Zero-Knowledge Age Verification (21+) & Digital ID Camera Acceptance**
*Compliant with California Business & Professions Code § 25660 and ISO/IEC 18013-5*

---

## 1. Executive Overview

### The Problem
Traditional bar door operations suffer from three major liabilities:
1. **Fake Physical IDs**: High-quality counterfeits fool bouncers, exposing venues to ABC (Alcoholic Beverage Control) fines, license suspension, and legal prosecution.
2. **Data & Privacy Liability**: Venues using ID scanning apps that photograph patron licenses are storing unencrypted names, addresses, and birthdates, risking California Consumer Privacy Act (CCPA) violations and data breach lawsuits.
3. **Queue Bottlenecks**: Manual inspection under low lighting slows door entry to 15–30 seconds per patron.

### The ShadeNet Solution
The **ShadeNet Bar Door Node** is a lightweight edge system allowing door staff to accept digital IDs (California DMV Mobile Driver's License, Apple Wallet, Google Wallet, and ShadeNet ZK Credentials) using **any standard camera** (tablet, phone, or mounted webcam).
- **Sub-Second Validation**: Cryptographic signature checked in <500ms.
- **Zero PII (Privacy by Design)**: No patron names, home addresses, license numbers, or full birthdates are ever viewed, transmitted, or recorded. The scanner only receives a mathematically verified assertion: `age >= 21: TRUE`.
- **Statutory Safe Harbor**: Strict compliance with California BPC § 25660 bona fide defense.

---

## 2. Legal & Regulatory Compliance (California)

### California Business & Professions Code § 25660
Under California BPC § 25660, a licensee has a statutory defense against allegations of serving minors if the licensee reasonably relied upon:
> *"a document issued by a federal, state, county, or municipal government, including, but not limited to, a valid motor vehicle operator’s license... issued by the Department of Motor Vehicles."*

### ISO/IEC 18013-5 & California DMV Mobile Driver's License (mDL)
The State of California officially rolled out mDL through the CA DMV Wallet, Apple Wallet, and Google Wallet. Under ISO/IEC 18013-5:
- The Department of Motor Vehicles digitally signs the patron's age credential using ECDSA NIST P-256 (`ES256`).
- The presentation discloses strictly `age_over_21: true` and the DMV's issuing authority public certificate.
- Physical alteration is cryptographically impossible: a modified DOB invalidates the DMV mathematical signature.

### Audit & Inspection Record (`door_pass_id`)
When a patron is admitted, the Door Node logs a non-identifying cryptographic verification receipt:
- Timestamp: `YYYY-MM-DD HH:MM:SS UTC`
- Issuer: `State of California DMV` (or `zk-passport:ICAO-9303` / `shadenet:steward`)
- Proof Hash: SHA-256 fingerprint of the signature
- Door Pass ID: Ephemeral UUID (e.g., `pass_e4f910ab`)
- **Zero PII**: No name, DOB, or photo is kept on the device or server. If ABC or law enforcement requests door records, the venue provides the immutable cryptographic verification logs proving due diligence.

---

## 3. Hardware Scoping & Deployment Options

Venues do not need expensive proprietary scanners or leased hardware. The Door Node runs in any modern browser as a Progressive Web App (PWA).

| Tier | Hardware Setup | Estimated Cost | Best Suited For |
| :--- | :--- | :--- | :--- |
| **Tier 1: Dedicated Door Tablet** *(Recommended)* | 8" Android Tablet (e.g., Amazon Fire HD 8 or Onn 8" Tablet) in a rugged shockproof case with heavy-duty neck strap or gooseneck door stand | **$55 – $85** | High-volume nightlife venues, club entrances, festivals |
| **Tier 2: Bouncer Smartphone** | Door staff's existing iOS (Safari) or Android (Chrome) smartphone | **$0** (BYOD) | Neighborhood bars, lounge door staff, pop-ups |
| **Tier 3: Fixed Kiosk / Tripod Rig** | 10" Android Tablet / iPad mounted at patron eye level with continuous LED ring light | **$120 – $180** | Fast-pass lanes, high-throughput music halls, VIP lines |

### Recommended Accessories
- **High-Contrast Matte Screen Protector** ($8): Cuts glare from outdoor streetlights and neon signs.
- **Gooseneck Clamp / Hand Strap Case** ($15): Prevents drops during busy rushes.
- **Portable 10,000mAh Power Bank** ($18): Keeps the tablet running continuously for a 10-hour shift.

---

## 4. Bouncer & Door Staff Workflow

```
       [Patron Opens Phone]
   Apple Wallet / CA DMV Wallet
                 │
                 ▼
       [Displays 21+ QR Code]
                 │
                 ▼
    [Point Door Camera at QR] (Distance: 6–8 inches)
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
 🟢 GREEN SCREEN       🔴 RED SCREEN
  Double Chime          Low Sawtooth Buzz
 "21+ ADMITTED"        "ENTRY DENIED"
  Patron Enters         Ask for Physical ID / Turn Away
```

### 5-Second Scan Protocol
1. **Patron Prompts**: Patron unlocks their phone and pulls up their CA DMV Wallet, Apple Wallet, or ShadeNet Steward pass.
2. **Aim**: Staff points the Door Node camera at the patron's QR code (hold 6 to 8 inches away).
3. **Instant Signal**:
   - **🟢 GREEN (`21+ ADMITTED`)**: Audible double-beep chime plays, device vibrates twice. Staff waves patron through.
   - **🔴 RED (`ENTRY DENIED`)**: Low buzz plays, device vibrates long. Reason displays on screen (e.g., *Underage*, *Expired Signature*, *Revoked Pass*).
4. **Auto-Reset**: The screen automatically resets to standby after 3.5 seconds, ready for the next patron in line.

### Staff FAQ at the Door
- **Q: Does the patron need cell service or bar WiFi?**
  - *No.* Digital wallets (Apple Wallet, Google Wallet, ShadeNet) generate valid offline credentials and QR codes locally on the patron's device.
- **Q: What if the patron doesn't have a digital ID yet?**
  - *Fallback:* Staff checks physical plastic driver's license per normal venue policy. Staff can hand patron a small coaster/card with a QR code to download their DMV digital ID or Steward pass for faster entry next time.
- **Q: Can someone take a screenshot of a friend's 21+ QR code?**
  - *No.* Standard mDL and ShadeNet passes use dynamic ephemerality with rotating nonces and timestamps; stale screenshots fail the signature check immediately.

---

## 5. Network Architecture & Resilience

The Door Node operates with three layers of fallback:

1. **Production Mode (Online)**:
   - Scans verify against the production ShadeNet server (`https://shady.example.org/api/operator/door-verify`).
   - Synced with venue attendance tallies and operator dashboard in real time.
2. **Local Edge Micro-Node Mode (LAN / Offline)**:
   - If public internet drops, the door tablet connects directly over local bar WiFi to a $35 Raspberry Pi or mini PC behind the bar running the verification worker locally.
3. **PWA Standalone (Zero Network)**:
   - The scanner web app caches all cryptographic root certificates (CA DMV Root CA, ShadeNet Operator Key) via Service Worker. The browser itself performs the cryptographic signature check in WebAssembly/WebCrypto completely offline.

---

## 6. Setup & Installation (3 Minutes)

### Step 1: Open the Scanner URL
On the door device browser (Chrome on Android or Safari on iOS), navigate to:
```
https://shady.example.org/door-scanner
```
*(Or local door node IP `http://203.0.113.X:8088/deploy/bar-door-node/`)*

### Step 2: Install as Standalone App (PWA)
- **iOS Safari**: Tap the Share icon (square with arrow) ➜ Tap **"Add to Home Screen"**.
- **Android Chrome**: Tap the three dots menu ➜ Tap **"Install App"** or **"Add to Home Screen"**.
*(This removes the browser address bar for a full-screen, dedicated bouncer interface).*

### Step 3: Grant Camera Permission
Tap **"Start Camera"** and select **"Allow"** when prompted for camera access.

### Step 4: Ready for Service
The admission counters will show `✓ 0` and `✗ 0`. The node is now active and ready for door admission.
