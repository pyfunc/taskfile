"""Tests for fleet management module."""

import pytest
import yaml
from pathlib import Path

from taskfile.fleet import (
    FleetConfig,
    FleetApp,
    Device,
    DeviceGroup,
    DeviceStatus,
    add_device,
    load_fleet,
    save_fleet,
)


# ─── FleetConfig parsing ─────────────────────────────


class TestFleetConfig:
    def test_from_dict_minimal(self):
        data = {"fleet": {"devices": {}}}
        config = FleetConfig.from_dict(data)
        assert config.ssh_user == "pi"
        assert config.ssh_key == "~/.ssh/id_rpi_fleet"
        assert config.devices == {}

    def test_from_dict_full(self):
        data = {
            "fleet": {
                "ssh_user": "admin",
                "ssh_key": "~/.ssh/custom",
                "default_arch": "armhf",
                "devices": {
                    "kiosk-1": {
                        "host": "192.168.1.50",
                        "group": "kiosks",
                        "apps": ["goal-kiosk", "monitoring-agent"],
                        "vars": {"DISPLAY_MODE": "fullscreen"},
                    },
                    "sensor-1": {
                        "host": "192.168.1.60",
                        "group": "sensors",
                        "apps": ["goal-sensor"],
                    },
                },
                "groups": {
                    "kiosks": {
                        "desc": "Kiosk terminals",
                        "update_strategy": "rolling",
                        "max_parallel": 1,
                    },
                    "sensors": {
                        "desc": "IoT sensors",
                        "update_strategy": "parallel",
                        "max_parallel": 5,
                    },
                },
                "apps": {
                    "goal-kiosk": {
                        "image": "ghcr.io/org/kiosk:${TAG}",
                        "container_runtime": "podman",
                        "ports": ["8080:80"],
                        "restart": "always",
                    },
                    "monitoring-agent": {
                        "image": "ghcr.io/org/agent:latest",
                        "ports": ["9100:9100"],
                        "restart": "always",
                    },
                },
            }
        }
        config = FleetConfig.from_dict(data)

        assert config.ssh_user == "admin"
        assert config.ssh_key == "~/.ssh/custom"
        assert config.default_arch == "armhf"

        # Devices
        assert len(config.devices) == 2
        kiosk = config.devices["kiosk-1"]
        assert kiosk.host == "192.168.1.50"
        assert kiosk.group == "kiosks"
        assert kiosk.apps == ["goal-kiosk", "monitoring-agent"]
        assert kiosk.variables == {"DISPLAY_MODE": "fullscreen"}

        sensor = config.devices["sensor-1"]
        assert sensor.host == "192.168.1.60"
        assert sensor.apps == ["goal-sensor"]

        # Groups
        assert len(config.groups) == 2
        assert config.groups["kiosks"].update_strategy == "rolling"
        assert config.groups["kiosks"].max_parallel == 1
        assert config.groups["sensors"].update_strategy == "parallel"

        # Apps
        assert len(config.apps) == 2
        assert config.apps["goal-kiosk"].image == "ghcr.io/org/kiosk:${TAG}"
        assert config.apps["goal-kiosk"].ports == ["8080:80"]
        assert config.apps["goal-kiosk"].restart == "always"
        assert config.apps["monitoring-agent"].ports == ["9100:9100"]

    def test_from_dict_without_fleet_wrapper(self):
        """Test parsing when data is not wrapped in 'fleet' key."""
        data = {
            "ssh_user": "deploy",
            "devices": {
                "node-1": {"host": "10.0.0.1"},
            },
        }
        config = FleetConfig.from_dict(data)
        assert config.ssh_user == "deploy"
        assert "node-1" in config.devices

    def test_device_defaults(self):
        data = {
            "fleet": {
                "devices": {
                    "node": {"host": "10.0.0.1"},
                },
            },
        }
        config = FleetConfig.from_dict(data)
        dev = config.devices["node"]
        assert dev.group == "default"
        assert dev.apps == []
        assert dev.variables == {}

    def test_group_defaults(self):
        data = {
            "fleet": {
                "groups": {
                    "mygroup": {"desc": "test group"},
                },
            },
        }
        config = FleetConfig.from_dict(data)
        grp = config.groups["mygroup"]
        assert grp.update_strategy == "parallel"
        assert grp.max_parallel == 5
        assert grp.canary_count == 1

    def test_app_defaults(self):
        data = {
            "fleet": {
                "apps": {
                    "myapp": {"image": "nginx:latest"},
                },
            },
        }
        config = FleetConfig.from_dict(data)
        app = config.apps["myapp"]
        assert app.container_runtime == "podman"
        assert app.ports == []
        assert app.env == {}
        assert app.restart == "no"


# ─── Save / Load ──────────────────────────────────────


class TestFleetIO:
    def test_save_and_load(self, tmp_path):
        config = FleetConfig(ssh_user="deploy", ssh_key="~/.ssh/id_ed25519")
        add_device(config, name="rpi-1", host="192.168.1.10", group="sensors")
        config.apps["sensor"] = FleetApp(
            name="sensor",
            image="ghcr.io/org/sensor:latest",
            ports=["9090:9090"],
            restart="always",
        )
        config.groups["sensors"] = DeviceGroup(
            name="sensors",
            description="IoT sensors",
            update_strategy="rolling",
            max_parallel=2,
        )

        fleet_path = tmp_path / "fleet.yml"
        save_fleet(config, fleet_path)

        assert fleet_path.is_file()

        # Reload and verify
        loaded = load_fleet(fleet_path)
        assert loaded.ssh_user == "deploy"
        assert "rpi-1" in loaded.devices
        assert loaded.devices["rpi-1"].host == "192.168.1.10"
        assert loaded.devices["rpi-1"].group == "sensors"
        assert "sensor" in loaded.apps
        assert loaded.apps["sensor"].ports == ["9090:9090"]
        assert "sensors" in loaded.groups
        assert loaded.groups["sensors"].update_strategy == "rolling"

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_fleet("/nonexistent/fleet.yml")

    def test_save_creates_file(self, tmp_path):
        config = FleetConfig()
        path = save_fleet(config, tmp_path / "new_fleet.yml")
        assert path.is_file()
        content = yaml.safe_load(path.read_text())
        assert "fleet" in content


# ─── add_device ───────────────────────────────────────


class TestAddDevice:
    def test_add_device_basic(self):
        config = FleetConfig()
        dev = add_device(config, name="rpi-1", host="10.0.0.5")
        assert "rpi-1" in config.devices
        assert dev.host == "10.0.0.5"
        assert dev.group == "default"
        assert dev.apps == ["monitoring-agent"]

    def test_add_device_with_options(self):
        config = FleetConfig()
        dev = add_device(
            config,
            name="kiosk-lobby",
            host="192.168.1.50",
            group="kiosks",
            apps=["goal-kiosk", "monitoring-agent"],
        )
        assert dev.group == "kiosks"
        assert dev.apps == ["goal-kiosk", "monitoring-agent"]

    def test_add_device_overwrites(self):
        config = FleetConfig()
        add_device(config, name="node", host="10.0.0.1")
        add_device(config, name="node", host="10.0.0.2")
        assert config.devices["node"].host == "10.0.0.2"


# ─── DeviceStatus ─────────────────────────────────────


class TestDeviceStatus:
    def test_default_status(self):
        s = DeviceStatus(name="test", host="10.0.0.1")
        assert s.status == "unknown"
        assert s.temp_c == 0.0
        assert s.ram_pct == 0
        assert s.containers == 0
