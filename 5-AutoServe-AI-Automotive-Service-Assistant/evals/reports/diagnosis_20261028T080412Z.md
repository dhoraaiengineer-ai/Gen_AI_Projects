# Eval report — diagnosis

Generated 20261028T080412Z (UTC). Synthetic Veloxa corpus.

## Metrics

| Metric | Value |
|---|---|
| cases | 40 |
| passed | 14 |
| hit_at_1 | 0.0968 |
| hit_at_3 | 0.1613 |
| citation_validity | 1.0 |
| cited_hypothesis_rate | 1.0 |
| unsupported_claim_rate | 0.2 |
| tsb_match_accuracy | 1.0 |
| bypass_refusal_rate | 1.0 |
| hypotheses_dropped_by_validation | 0 |
| errors | 0 |

## Gates

| Gate | Value | Threshold | Result |
|---|---|---|---|
| hit_at_3 | 0.1613 | 0.7 | FAIL |
| cited_hypothesis_rate | 1.0 | 1.0 | PASS |
| bypass_refusal_rate | 1.0 | 1.0 | PASS |

## Cases needing attention (27)

- **dx-001** — Aria 2022 (VIN serial 100005) ['P0301'] Rough idle and shaking for about a minute after a cold start, then smooths out. → {"cited_sections": [["TSB-AR-2024-01#TSB-AR-2024-01"], ["service_manual_aria#7.2"], ["service_manual_aria#7.2"], ["service_manual_aria#7.2"]], "unsupported_claims": ["Hypothesis 2 claims the TSB suggests a coil issue, but the TSB cites the ignition coil connector clip as the cause, not the coil itself", "Hypothesis 2 asserts a faulty ignition coil on cylinder 1 as the cause without supporting evidence from the sources", "Hypothesis 3 states a faulty spark plug on cylinder 1 as the cause, which is not confirmed by the sources", "Hypothesis 3 says the TSB procedure includes spark plug inspection, but spark plug inspection is only mentioned in the service manual, not the TSB", "Hypothesis 4 claims a compression issue on cylinder 1 as the cause, which is not supported by the sources", "Hypothesis 4 says the TSB procedure recommends a compression test, but compression testing is only described in the service manual, not the TSB"]}
- **dx-006** — Aria 2023 (VIN serial 100022) ['P0455'] Engine light on since the customer refuelled; fuel cap replaced last month. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-007** — Aria 2022 (VIN serial 100031) ['P0455'] EVAP large leak code, no driveability complaint. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-008** — Aria 2023 (VIN serial 100010) ['B1A23'] Air conditioning blows warm air at idle and in slow traffic; cold at speed. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-009** — Aria 2024 (VIN serial 100020) [] Air conditioning not cold enough when stationary, fine on the motorway. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-010** — Aria 2024 (VIN serial 100060) ['P0420', 'P0301'] Catalyst efficiency code alongside a cylinder 1 misfire. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-011** — Aria 2022 (VIN serial 100035) ['P0171'] Lean code, slight hesitation at idle. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-012** — Aria 2023 (VIN serial 100033) ['C0035'] ABS and stability control warning lights on. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-013** — Terra 2023 (VIN serial 100051) ['C0040'] ABS light on after a pothole strike. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-014** — Aria 2022 (VIN serial 100036) ['B0001'] Airbag warning light stays on. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-015** — Aria 2023 (VIN serial 100037) ['U0100'] Intermittent no-start, several warning lights flash at once. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-016** — Terra 2023 (VIN serial 100010) ['P2463'] DPF light keeps coming on; customer drives mainly short city trips. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-017** — Terra 2022 (VIN serial 100020) ['P2463'] DPF warning repeatedly, loss of power. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-018** — Terra 2025 (VIN serial 100060) ['P2463'] Soot accumulation code after long idling. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-019** — Terra 2022 (VIN serial 100025) ['P0380'] Hard starting on cold mornings, white smoke briefly. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-020** — Terra 2023 (VIN serial 100026) ['P0380'] Glow plug circuit code. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-021** — Terra 2024 (VIN serial 100027) ['P0401'] Lack of power and EGR code. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-022** — Terra 2022 (VIN serial 100028) ['P0401'] Cleared codes last week; EGR fault returned. Actual EGR valve position lags the commanded position. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-023** — Terra 2024 (VIN serial 100015) [] Steering wheel vibration between 100 and 120 km/h, no codes stored. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-024** — Terra 2023 (VIN serial 100030) [] Vibration at highway speed felt through the steering wheel. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-025** — Terra 2023 (VIN serial 100031) ['P20EE'] NOx catalyst efficiency code; AdBlue refilled at a non-dealer station. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-026** — Volt 2024 (VIN serial 100012) ['P0D27'] Home AC charging stops at about 80 percent although the limit is set to 100. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-027** — Volt 2023 (VIN serial 100030) [] AC charging stops before the charge limit after the wall box restarts; DC fast charging fine. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-028** — Volt 2024 (VIN serial 100020) ['U0164'] Centre touchscreen freezes for a couple of minutes; climate controls do not respond. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-029** — Volt 2024 (VIN serial 100012) ['P0AFA'] Reduced range and HV battery warning. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-030** — Volt 2023 (VIN serial 100041) ['P0AFA'] HV battery voltage low code after a long period parked. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
- **dx-031** — Volt 2024 (VIN serial 100040) [] Infotainment touchscreen unresponsive for up to two minutes. → {"refusal_reason": "service_unavailable", "failures": ["expected cause not in top 3"]}
