# SED-2 Validation Report

## Architecture

```text
Confirmed CME-2 violation
  -> SeverityEngine
  -> EscalationManager state machine
  -> ActionDispatcher
  -> EventStore + dashboard state + MockIoTRelay
```

SED-2 is downstream of CME-2 confirmation. It does not retrain or alter the
detector, confidence thresholds, or temporal confirmation policy.

## Severity Rules

| Hazard | Initial Tier | Warning Rule | Critical Rule | Geofence Overrides |
| ------ | ------------ | ------------ | ------------- | ------------------ |
| fire | warning | n/a | after 3.0s | `response_zone -> critical` |
| smoke | info | after 2.0s | after 8.0s | `smoke_zone -> warning` |
| water leak | info | after 5.0s | none by default | `leak_zone -> warning` |
| chemical hazard | warning | n/a | after 3.0s | `response_zone/leak_zone -> critical` |
| no helmet | warning | n/a | after 10.0s | `ppe_zone -> warning` |

The repository class is `chemical hazard`, so SED-2 uses that class name as the
source of truth.

## Action Mapping

| Tier | Log | Dashboard | Mock IoT |
| ---- | --- | --------- | -------- |
| info | yes | none | no |
| warning | yes | warning flash/state | no |
| critical | yes | critical state | shutdown simulation |

## State Machine

```text
INACTIVE
  -> INFO / WARNING / CRITICAL on confirmed violation
  -> WARNING when configured persistence or geofence rule requires it
  -> CRITICAL when configured persistence or geofence rule requires it
  -> RESOLVED after configured clear duration
```

Escalation is monotonic during one event. A resolved recurrence creates a new
event ID.

## Deterministic Three-Tier Scenario

The unit tests simulate:

| Camera | Hazard | Tier | Actions |
| ------ | ------ | ---- | ------- |
| cam_01 | smoke | info | log |
| cam_02 | no helmet | warning | log + dashboard flash |
| cam_03 | fire in `response_zone` | critical | log + dashboard critical + mock IoT shutdown |

The mock IoT relay trigger count is verified as `1` for a single Critical event,
even when additional Critical frames arrive.

## Validation

Command:

```powershell
python -m unittest discover -s SED_2_Alert_Escalation\tests
```

Result:

```text
Ran 15 tests
OK
```

## Definition Of Done

```text
3 severity tiers implemented: PASS
Per-hazard severity rules implemented: PASS
Rules externalized/configurable: PASS
Escalation state machine implemented: PASS
INFO -> log action verified: PASS
WARNING -> log + dashboard action verified: PASS
CRITICAL -> log + dashboard + mock IoT verified: PASS
Critical IoT trigger idempotency verified: PASS
Per-camera alert isolation verified: PASS
Geofence severity overrides supported: PASS
Resolution/reset behavior verified: PASS
Existing CME-2 confirmation preserved: PASS
Existing SED-1 multi-camera pipeline preserved: PASS
SED-2 OVERALL: PASS
```

