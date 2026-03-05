# Edge IoT — Sensor Gateways, All 3 Group Strategies

Zarządzanie flotą bramek IoT: fabryka, magazyn, biuro — rolling, parallel, canary.

## Features covered

- **`ssh_port: 2200`** — non-standard SSH port for IoT devices
- **`environment_defaults`** — shared ssh_user, ssh_key, ssh_port, container_runtime, MQTT vars
- **`env_file`** — per-location `.env.factory`, `.env.warehouse`, `.env.office`
- **All 3 group strategies:**
  - `rolling` (max_parallel: 2) — all-gateways
  - `parallel` — factory (during maintenance window)
  - `canary` (canary_count: 1) — warehouse (test on 1, then rest)
- **`condition`** — mqtt-test only if `SENSOR_PROTOCOL=mqtt`
- **`ignore_errors`** — sensor-check continues on failure
- **`@remote`** — all device operations over SSH

## Usage

```bash
# Build ARM64 image
taskfile run build --var TAG=v2.0.0

# Deploy to all gateways (rolling, 2 at a time)
taskfile -G all-gateways run deploy --var TAG=v2.0.0

# Deploy factory only (parallel — both at once)
taskfile -G factory run deploy --var TAG=v2.0.0

# Deploy warehouse (canary — test on 1 first)
taskfile -G warehouse run deploy --var TAG=v2.0.0

# Deploy single gateway
taskfile --env gw-factory-1 run deploy --var TAG=v2.0.0

# Monitoring
taskfile --env gw-factory-1 run status
taskfile --env gw-factory-1 run logs
taskfile --env gw-warehouse-1 run sensor-check
taskfile --env gw-warehouse-1 run mqtt-test

# Fleet maintenance
taskfile -G all-gateways run update-os
taskfile -G all-gateways run cleanup

# Provision new gateway
taskfile --env gw-office-1 run provision
taskfile --env gw-office-1 run configure-firewall
```

## Architecture

```
┌─── Factory ────────────────┐  ┌─── Warehouse ─────────────┐  ┌─── Office ──────┐
│ gw-factory-1  10.0.1.10   │  │ gw-warehouse-1  10.0.2.10 │  │ gw-office-1     │
│ gw-factory-2  10.0.1.11   │  │ gw-warehouse-2  10.0.2.11 │  │   10.0.3.10     │
│ protocol: modbus           │  │ protocol: mqtt             │  │ protocol: zigbee│
│ strategy: parallel         │  │ strategy: canary           │  └─────────────────┘
└────────────────────────────┘  └────────────────────────────┘
         ↓                               ↓                            ↓
    ┌────────────────────────────────────────────────────────────────────┐
    │                    MQTT Broker (mqtt.example.com)                  │
    └────────────────────────────────────────────────────────────────────┘
```
