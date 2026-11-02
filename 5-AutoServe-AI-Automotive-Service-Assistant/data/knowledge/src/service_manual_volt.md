---
doc_id: service_manual_volt
title: Veloxa Volt — Service Manual (excerpt, staff only)
doc_type: service_manual
model: Volt
model_year_from: 2023
model_year_to: 2026
visibility: staff
version: "2026.1"
---

## 7.1 HV system de-energisation [safety]
Certified HV technician required. Wear class 0 insulating gloves (inspected before use), safety glasses, and remove metal jewellery. Op code OP-HV-DEENERGISE.
1. Switch the vehicle off and remove the key card to at least 5 m away.
2. Disconnect the 12 V battery negative terminal.
3. Remove the HV service disconnect and store it in your pocket.
4. Wait 10 minutes for the capacitors to discharge.
5. Verify zero voltage at the HV junction box with a CAT III meter before touching any HV component.

## 7.2 HV battery coolant hose clamp inspection (recall RC-2026-02) [safety]
Certified HV technician required. Op code OP-RC2602-CLAMP. Part VLX-HV-CLAMP-11.
1. De-energise the HV system (section 7.1).
2. Inspect the coolant hose clamp at the HV battery inlet for correct position and tension.
3. Replace the clamp with part VLX-HV-CLAMP-11.
4. Refill and bleed the battery coolant circuit using the diagnostic tool routine. Check for leaks.

## 7.3 Onboard charger input voltage fault (P0D27)
Op code OP-OBC-UPDATE.
1. Confirm the customer's charging equipment and supply are within specification.
2. Read the onboard charger software version.
3. For 2023–2025 vehicles that stop AC charging below the set limit, apply TSB-VT-2025-01.

## 7.4 HV battery cell voltage imbalance (P0AFA)
Certified HV technician required. Op code OP-DIAG-BASIC.
1. Read cell voltages with the diagnostic tool.
2. If the spread between highest and lowest cell exceeds the limit in section 8.1 after a full balancing charge, open a battery case with Veloxa technical support. Do not open the HV battery in the workshop.

## 8.1 Specifications
| Item | Specification |
|---|---|
| Cell voltage spread limit (after balancing) | 50 mV |
| Wheel nut | 125 N·m |
| HV battery coolant | Veloxa Spec VS-COOL-EV1 |
