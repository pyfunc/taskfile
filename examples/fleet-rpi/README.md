# Fleet RPi — Raspberry Pi Fleet Management

Zarządzanie flotą 6 kiosków (Raspberry Pi) w centrum handlowym.

## Scenariusz

```
┌─────────────────────────────────────────────────────┐
│  Centrum Handlowe "Galaxy"                          │
│                                                     │
│  🖥 kiosk-lobby          192.168.1.10  (wejście)    │
│  🖥 kiosk-cafe           192.168.1.11  (kawiarnia)  │
│  🖥 kiosk-entrance-north 192.168.1.12  (północ)    │
│  🖥 kiosk-entrance-south 192.168.1.13  (południe)  │
│  🖥 kiosk-food-court     192.168.1.14  (food court) │
│  🖥 kiosk-parking        192.168.1.15  (parking)   │
└─────────────────────────────────────────────────────┘
```

Każdy RPi uruchamia aplikację kiosk w kontenerze Podman.

## Struktura

```
fleet-rpi/
├── Taskfile.yml        # Flota: 6 RPi + 3 grupy + taski
├── Dockerfile          # Aplikacja kiosk (ARM64)
├── docker-compose.yml  # Lokalne dev
└── README.md
```

## Grupy urządzeń

| Grupa | Urządzenia | Strategia | Opis |
|-------|-----------|-----------|------|
| `all-kiosks` | 6 szt. | rolling (max 2) | Bezpieczna aktualizacja |
| `entrances` | 2 szt. | parallel | Wejścia — szybka zmiana |
| `high-traffic` | 3 szt. | canary (1 test) | Popularne — najpierw 1, potem reszta |

## Użycie

### Sprawdzenie statusu floty

```bash
# Status wszystkich urządzeń (temp, RAM, dysk, uptime)
taskfile fleet status

# Status tylko kiosków przy wejściach
taskfile fleet status --group entrances

# Lista urządzeń i grup
taskfile fleet list
```

### Deploy na flotę

```bash
# Build obrazu ARM64 + push
taskfile run build push --var TAG=v2.1.0

# Deploy na WSZYSTKIE kioski (rolling, 2 naraz)
taskfile -G all-kiosks run deploy-kiosk --var TAG=v2.1.0

# Deploy tylko na wejścia (parallel)
taskfile -G entrances run deploy-kiosk --var TAG=v2.1.0

# Deploy canary — najpierw 1 kiosk, potem reszta
taskfile -G high-traffic run deploy-kiosk --var TAG=v2.1.0

# Deploy na jeden konkretny kiosk
taskfile --env kiosk-lobby run deploy-kiosk --var TAG=v2.1.0
```

### Diagnostyka i naprawa

```bash
# 8-punktowa diagnostyka (ping, SSH, dysk, RAM, temp, podman, NTP)
taskfile fleet repair kiosk-lobby

# Automatyczna naprawa bez pytań
taskfile fleet repair kiosk-lobby --auto-fix

# Logi z konkretnego kiosku
taskfile --env kiosk-cafe run kiosk-logs

# Info o urządzeniu
taskfile --env kiosk-parking run kiosk-info
```

### Utrzymanie floty

```bash
# Czyszczenie nieużywanych obrazów (oszczędność karty SD)
taskfile -G all-kiosks run cleanup

# Aktualizacja systemu
taskfile -G all-kiosks run update-os

# Restart konkretnego kiosku
taskfile --env kiosk-food-court run restart-kiosk

# Reboot urządzenia
taskfile --env kiosk-parking run reboot-device
```

### Provisioning nowego RPi

```bash
# Pierwsza konfiguracja — instaluje Podman, włącza linger
taskfile --env kiosk-parking run provision

# Potem deploy
taskfile --env kiosk-parking run deploy-kiosk --var TAG=v2.1.0
```

## Jak to działa

### 1. Każdy RPi = environment w Taskfile.yml

```yaml
environments:
  kiosk-lobby:
    ssh_host: 192.168.1.10
    ssh_user: pi
    ssh_key: ~/.ssh/fleet_ed25519
    container_runtime: podman
    variables:
      KIOSK_ID: lobby
```

### 2. Grupy definiują strategię deploy

```yaml
environment_groups:
  all-kiosks:
    members: [kiosk-lobby, kiosk-cafe, ...]
    strategy: rolling     # 2 naraz
    max_parallel: 2
```

### 3. `-G` uruchamia task na całej grupie

```bash
taskfile -G all-kiosks run deploy-kiosk
# → deploy-kiosk na kiosk-lobby + kiosk-cafe (batch 1)
# → deploy-kiosk na kiosk-entrance-north + kiosk-entrance-south (batch 2)
# → deploy-kiosk na kiosk-food-court + kiosk-parking (batch 3)
```

## Wymagania

- SSH dostęp do każdego RPi (`ssh-copy-id pi@192.168.1.10`)
- Podman na każdym RPi (`taskfile --env <name> run provision`)
- Docker z buildx na maszynie dev (do budowania ARM64)
