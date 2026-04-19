"""Tests for VPS provisioner."""

from unittest.mock import patch, MagicMock

from taskfile.provisioner import (
    ProvisionConfig,
    VPSProvisioner,
    provision_vps,
)


class TestProvisionConfig:
    """Tests for ProvisionConfig dataclass."""

    def test_basic_config(self):
        """Test creating basic provision config."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22, 80, 443],
        )

        assert config.ip == "192.168.1.100"
        assert config.ssh_key == "~/.ssh/id_rsa"
        assert config.ssh_user == "deploy"
        assert config.domain == "example.com"
        assert config.ports == [22, 80, 443]
        assert config.email == "admin@example.com"  # Default
        assert config.traefik_version == "v3.0"  # Default

    def test_custom_email_and_version(self):
        """Test config with custom email and Traefik version."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22, 80, 443],
            email="admin@example.com",
            traefik_version="v2.10",
        )

        assert config.email == "admin@example.com"
        assert config.traefik_version == "v2.10"


class TestVPSProvisioner:
    """Tests for VPSProvisioner class."""

    def test_init(self):
        """Test provisioner initialization."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22, 80, 443],
        )
        provisioner = VPSProvisioner(config)

        assert provisioner.config == config
        assert "root@192.168.1.100" in provisioner.ssh_target
        assert "-i" in provisioner.ssh_opts

    def test_ssh_method(self):
        """Test SSH command execution."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22],
        )
        provisioner = VPSProvisioner(config)

        with patch("taskfile.provisioner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="output",
                stderr="",
            )

            exit_code, stdout, stderr = provisioner._ssh("echo test")

            assert exit_code == 0
            assert stdout == "output"
            mock_run.assert_called_once()
            # Verify SSH command structure
            call_args = mock_run.call_args
            assert "ssh" in call_args[0][0]

    def test_check_command_exists(self):
        """Test checking if command exists on remote."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22],
        )
        provisioner = VPSProvisioner(config)

        with patch.object(provisioner, "_ssh") as mock_ssh:
            mock_ssh.return_value = (0, "/usr/bin/podman", "")

            result = provisioner._check_command("podman")

            assert result is True
            mock_ssh.assert_called_with("which podman", timeout=10)

    def test_check_command_not_exists(self):
        """Test checking if command doesn't exist."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22],
        )
        provisioner = VPSProvisioner(config)

        with patch.object(provisioner, "_ssh") as mock_ssh:
            mock_ssh.return_value = (1, "", "not found")

            result = provisioner._check_command("nonexistent")

            assert result is False

    def test_is_provisioned_true(self):
        """Test is_provisioned when Podman is installed."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22],
        )
        provisioner = VPSProvisioner(config)

        with patch.object(provisioner, "_ssh") as mock_ssh:
            mock_ssh.return_value = (0, "podman version 4.0.0", "")

            result = provisioner.is_provisioned()

            assert result is True

    def test_is_provisioned_false(self):
        """Test is_provisioned when Podman is not installed."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22],
        )
        provisioner = VPSProvisioner(config)

        with patch.object(provisioner, "_ssh") as mock_ssh:
            mock_ssh.return_value = (1, "", "command not found")

            result = provisioner.is_provisioned()

            assert result is False


class TestVPSProvisionerSteps:
    """Tests for individual provisioning steps."""

    def test_system_update(self):
        """Test system update step."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22],
        )
        provisioner = VPSProvisioner(config)

        with patch.object(provisioner, "_ssh") as mock_ssh:
            mock_ssh.return_value = (0, "", "")

            result = provisioner._system_update()

            assert result is True
            mock_ssh.assert_called_with(
                "apt-get update -qq && apt-get upgrade -y -qq",
                timeout=180,
            )

    def test_install_podman_already_installed(self):
        """Test Podman install when already present."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22],
        )
        provisioner = VPSProvisioner(config)

        with (
            patch.object(provisioner, "_check_command") as mock_check,
            patch.object(provisioner, "_ssh") as mock_ssh,
        ):
            mock_check.return_value = True
            mock_ssh.return_value = (0, "podman version 4.0.0", "")

            result = provisioner._install_podman()

            assert result is True
            # Should check version but not install
            mock_ssh.assert_called_with("podman --version", timeout=10)

    def test_install_podman_new_install(self):
        """Test fresh Podman installation."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22],
        )
        provisioner = VPSProvisioner(config)

        with (
            patch.object(provisioner, "_check_command") as mock_check,
            patch.object(provisioner, "_ssh") as mock_ssh,
        ):
            mock_check.return_value = False
            mock_ssh.return_value = (0, "", "")

            result = provisioner._install_podman()

            assert result is True
            mock_ssh.assert_called_with(
                "apt-get install -y -qq podman podman-compose",
                timeout=120,
            )

    def test_setup_firewall(self):
        """Test firewall setup."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="deploy",
            domain="example.com",
            ports=[22, 80, 443],
        )
        provisioner = VPSProvisioner(config)

        with (
            patch.object(provisioner, "_check_command") as mock_check,
            patch.object(provisioner, "_ssh") as mock_ssh,
        ):
            mock_check.return_value = False  # UFW not installed
            mock_ssh.return_value = (0, "", "")

            result = provisioner._setup_firewall()

            assert result is True
            # Should install ufw and configure all ports
            calls = mock_ssh.call_args_list
            # First call installs ufw
            assert any("ufw" in str(call) for call in calls)

    def test_create_deploy_user(self):
        """Test deploy user creation."""
        config = ProvisionConfig(
            ip="192.168.1.100",
            ssh_key="~/.ssh/id_rsa",
            ssh_user="mydeploy",
            domain="example.com",
            ports=[22],
        )
        provisioner = VPSProvisioner(config)

        with patch.object(provisioner, "_ssh") as mock_ssh:
            mock_ssh.return_value = (0, "", "")

            result = provisioner._create_deploy_user()

            assert result is True
            calls = [str(call) for call in mock_ssh.call_args_list]
            # Should create user
            assert any("useradd" in call for call in calls)
            # Should enable linger
            assert any("loginctl enable-linger" in call for call in calls)


class TestProvisionVPS:
    """Tests for the convenience function."""

    def test_provision_vps_success(self):
        """Test successful VPS provisioning."""
        with patch("taskfile.provisioner.VPSProvisioner") as mock_class:
            mock_instance = MagicMock()
            mock_instance.is_provisioned.return_value = False
            mock_instance.provision.return_value = True
            mock_class.return_value = mock_instance

            result = provision_vps(
                ip="192.168.1.100",
                ssh_key="~/.ssh/id_rsa",
                ssh_user="deploy",
            )

            assert result is True
            mock_instance.provision.assert_called_with(dry_run=False)

    def test_provision_vps_already_provisioned(self):
        """Test provisioning when already done."""
        with patch("taskfile.provisioner.VPSProvisioner") as mock_class:
            mock_instance = MagicMock()
            mock_instance.is_provisioned.return_value = True
            mock_class.return_value = mock_instance

            result = provision_vps(
                ip="192.168.1.100",
                ssh_key="~/.ssh/id_rsa",
            )

            assert result is True
            # Should skip provisioning
            mock_instance.provision.assert_not_called()

    def test_provision_vps_dry_run(self):
        """Test dry run mode."""
        with patch("taskfile.provisioner.VPSProvisioner") as mock_class:
            mock_instance = MagicMock()
            mock_instance.is_provisioned.return_value = False
            mock_instance.provision.return_value = True
            mock_class.return_value = mock_instance

            result = provision_vps(
                ip="192.168.1.100",
                ssh_key="~/.ssh/id_rsa",
                dry_run=True,
            )

            assert result is True
            mock_instance.provision.assert_called_with(dry_run=True)
