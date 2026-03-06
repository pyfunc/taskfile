# IaC NixOS/Nix — Reproducible Infrastructure + Markpact

**Cały projekt Nix w jednym pliku README.md — wypakuj i uruchom przez Taskfile.**

## 📋 Co to jest?

Nix/NixOS — w pełni reprodukowalne środowiska, systemy i deployments.
Deklaratywna konfiguracja, atomic upgrades/rollbacks, zintegrowane z `taskfile`.

## Features covered

- **`condition`** — nix installed check
- **`env_file`** — per-environment config
- **Flakes** — modern Nix project structure
- **Reproducible builds** — deterministic artifacts
- **NixOS deployment** — remote system management

## 🎯 Workflow

```bash
# 1. Wypakowanie projektu
markpact README.md && cd sandbox

# 2. Dev shell
taskfile run dev-shell

# 3. Build
taskfile run build

# 4. Deploy NixOS
taskfile --env prod run deploy

# 5. Rollback
taskfile --env prod run rollback

# 6. Garbage collection
taskfile run gc
```

## 🔧 Dostępne komendy

| Komenda | Opis |
|---------|------|
| `taskfile run dev-shell` | Enter Nix development shell |
| `taskfile run build` | Build Nix derivation |
| `taskfile run check` | Check flake outputs |
| `taskfile run update` | Update flake inputs |
| `taskfile run deploy` | Deploy NixOS configuration |
| `taskfile run rollback` | Rollback to previous generation |
| `taskfile run test` | Run NixOS tests in VM |
| `taskfile run fmt` | Format Nix files |
| `taskfile run gc` | Garbage collect old generations |
| `taskfile run show` | Show flake outputs |
| `taskfile run diff` | Show closure diff |
| `taskfile run clean` | Remove result symlinks |

---

## Pliki projektu (markpact)

### Taskfile.yml — konfiguracja tasków

```markpact:file path=Taskfile.yml
version: "1"
name: nix-infra
description: "Nix/NixOS: reproducible infrastructure with flakes"

variables:
  FLAKE_DIR: .
  SYSTEM: x86_64-linux

environments:
  dev:
    variables:
      TARGET: devShells.${SYSTEM}.default
      NIXOS_HOST: ""

  staging:
    env_file: .env.staging
    variables:
      NIXOS_HOST: staging.example.com
      NIXOS_USER: root
      NIXOS_CONFIG: staging

  prod:
    env_file: .env.prod
    variables:
      NIXOS_HOST: prod.example.com
      NIXOS_USER: root
      NIXOS_CONFIG: prod

tasks:

  dev-shell:
    desc: Enter Nix development shell
    cmds:
      - nix develop ${FLAKE_DIR}

  build:
    desc: Build default package
    cmds:
      - nix build ${FLAKE_DIR}

  check:
    desc: Check all flake outputs (build + tests)
    cmds:
      - nix flake check ${FLAKE_DIR}

  update:
    desc: Update flake inputs (nixpkgs, etc.)
    cmds:
      - nix flake update ${FLAKE_DIR}

  deploy:
    desc: Deploy NixOS configuration to remote host
    cmds:
      - >-
        nixos-rebuild switch
        --flake ${FLAKE_DIR}#${NIXOS_CONFIG}
        --target-host ${NIXOS_USER}@${NIXOS_HOST}
        --use-remote-sudo

  rollback:
    desc: Rollback to previous NixOS generation
    cmds:
      - ssh ${NIXOS_USER}@${NIXOS_HOST} "nixos-rebuild switch --rollback"

  test:
    desc: Run NixOS tests in VM
    cmds:
      - nix build ${FLAKE_DIR}#checks.${SYSTEM}.integration-test

  fmt:
    desc: Format Nix files
    cmds:
      - nix fmt ${FLAKE_DIR}

  gc:
    desc: Garbage collect old generations (keep last 5)
    cmds:
      - nix-collect-garbage --delete-older-than 30d
      - nix store gc

  show:
    desc: Show flake outputs
    cmds:
      - nix flake show ${FLAKE_DIR}

  diff:
    desc: Show closure size diff
    cmds:
      - nix build ${FLAKE_DIR} --out-link result-new
      - nix path-info -rSh result-new | tail -1

  clean:
    desc: Remove result symlinks
    cmds:
      - rm -f result result-*
```

### flake.nix — Nix Flake

```markpact:file path=flake.nix
{
  description = "Infrastructure managed by Nix + Taskfile";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
    in
    flake-utils.lib.eachSystem systems (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            docker
            docker-compose
            kubectl
            terraform
            ansible
            python312
            nodejs_20
          ];
          shellHook = ''
            echo "🔧 Nix dev shell loaded"
          '';
        };

        packages.default = pkgs.stdenv.mkDerivation {
          pname = "my-app";
          version = "1.0.0";
          src = ./src;
          buildInputs = with pkgs; [ python312 ];
          installPhase = ''
            mkdir -p $out/bin
            cp -r . $out/
          '';
        };
      }
    ) // {
      nixosConfigurations = {
        staging = nixpkgs.lib.nixosSystem {
          system = "x86_64-linux";
          modules = [ ./nixos/staging.nix ];
        };
        prod = nixpkgs.lib.nixosSystem {
          system = "x86_64-linux";
          modules = [ ./nixos/prod.nix ];
        };
      };
    };
}
```

### nixos/staging.nix — NixOS config

```markpact:file path=nixos/staging.nix
{ config, pkgs, ... }:
{
  networking.hostName = "staging";

  services.nginx = {
    enable = true;
    virtualHosts."staging.example.com" = {
      forceSSL = true;
      enableACME = true;
      locations."/" = {
        proxyPass = "http://localhost:8000";
      };
    };
  };

  security.acme = {
    acceptTerms = true;
    defaults.email = "admin@example.com";
  };

  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_16;
  };

  environment.systemPackages = with pkgs; [
    docker
    htop
    vim
  ];

  virtualisation.docker.enable = true;

  system.stateVersion = "24.05";
}
```

### .env.prod

```markpact:file path=.env.prod
NIXOS_HOST=prod.example.com
NIXOS_USER=root
```

---

## 📚 Dokumentacja

- [Nix Manual](https://nixos.org/manual/nix/stable/)
- [NixOS Manual](https://nixos.org/manual/nixos/stable/)
- [Nix Flakes](https://nixos.wiki/wiki/Flakes)
- [NixOS Deployment](https://nixos.wiki/wiki/NixOps)

**Licencja:** MIT
