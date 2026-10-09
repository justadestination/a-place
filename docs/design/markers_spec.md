# Zine Print Marker Design Specification (Task 3.8)

## Overview
This specification details the visual marker system for the printed NightCal zine (Umwelt Horizons). Markers act as scannable gateways connecting print pages to digital and AR portal content (Task 3.7).

Per Spec §E, markers must be designed **into** the editorial aesthetic rather than treated as generic, utilitarian stickers. Every marker printed in the zine carries a plain-URL fallback directly alongside it so readers can navigate without camera scanning.

---

## 1. Physical Specifications & Print Tolerances

| Parameter | Specification | Notes |
| :--- | :--- | :--- |
| **Minimum Print Size** | `15mm × 15mm` | Scannable down to 15mm under dim (20–50 lux) nightlife ambient light. |
| **Quiet Zone** | `4 modules` (min. 2mm) | Must be preserved on all 4 sides; no border bleed into copy text. |
| **Error Correction** | `Level H` (30% recovery) | Withstands newsprint ink bleed, folding, smudging, and coffee stains. |
| **Contrast Ratio** | `>= 7:1` | Pure black `#121214` ink on `#FBFAF7` paper stock. |
| **Fallback Caption** | Font size `>= 6pt` | Printed directly below marker: `shady.example.org/portal/?target=...` |

---

## 2. Editorial Integration & Mosaic Grammar

1. **Embedded Geometry**:
   - Corner finder patterns are styled with clean geometric framing matching the NightCal token grid (`--nc-radius-sm`).
   - Inner data matrix uses crisp rectilinear modules without irregular warping that disrupts scanner cameras.

2. **Plain-URL Fallback Requirement**:
   - Every marker must have an accompanying text caption:
     `PORTAL: shady.example.org/portal/?target=<slug>`
   - This ensures readers on feature phones, devices with damaged cameras, or privacy-conscious readers can access the destination directly.

3. **URL Payload Schema**:
   - Notes: `https://shady.example.org/portal/?target=note:<slug>`
   - Events: `https://shady.example.org/portal/?target=event:<id>`
   - Venues: `https://shady.example.org/portal/?target=venue:<id>`
