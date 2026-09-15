# SED-2 Real-Time Alert Escalation

SED-2 adds severity-tiered alert escalation on top of the existing CME-2
confirmation and SED-1 multi-camera stream pipeline.

## Pipeline

```text
CME-2 confirmed violation
  -> SeverityEngine
  -> EscalationManager
  -> ActionDispatcher
  -> EventStore / Dashboard / MockIoTRelay
```

## Tiers

- `INFO`: structured log only
- `WARNING`: structured log + dashboard warning/flash state
- `CRITICAL`: structured log + dashboard critical state + safe mock IoT shutdown

## Configuration

```text
SED_2_Alert_Escalation/configs/severity_rules.yaml
SED_2_Alert_Escalation/configs/action_mapping.yaml
```

Severity policy version:

```text
SED2-alert-escalation-v1
```

## Mock IoT Safety

The IoT relay is simulated only. It does not access GPIO, PLCs, network relays,
or machinery. It records software state:

```text
NORMAL -> SHUTDOWN_TRIGGERED
```

The shutdown action is idempotent per Critical event.

## Validation

```powershell
python -m unittest discover -s SED_2_Alert_Escalation\tests
```

The validation report is:

```text
SED_2_Alert_Escalation/reports/SED_2_Validation_Report.md
```

