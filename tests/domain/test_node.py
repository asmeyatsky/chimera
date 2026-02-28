"""Tests for Node value object."""

import pytest
from chimera.domain.value_objects.node import Node


class TestNode:
    def test_default_values(self):
        node = Node(host="example.com")
        assert node.user == "root"
        assert node.port == 22

    def test_custom_values(self):
        node = Node(host="10.0.0.1", user="deploy", port=2222)
        assert node.host == "10.0.0.1"
        assert node.user == "deploy"
        assert node.port == 2222

    def test_str(self):
        node = Node(host="web1.example.com", user="admin", port=22)
        assert str(node) == "admin@web1.example.com:22"

    def test_frozen(self):
        node = Node(host="example.com")
        with pytest.raises(AttributeError):
            node.host = "other.com"

    def test_equality(self):
        a = Node(host="example.com", user="root", port=22)
        b = Node(host="example.com", user="root", port=22)
        assert a == b

    def test_inequality(self):
        a = Node(host="a.com", user="root", port=22)
        b = Node(host="b.com", user="root", port=22)
        assert a != b


class TestNodeValidation:
    def test_empty_host_rejected(self):
        with pytest.raises(ValueError, match="Invalid hostname"):
            Node(host="")

    def test_empty_user_rejected(self):
        with pytest.raises(ValueError, match="user cannot be empty"):
            Node(host="example.com", user="")

    def test_port_too_low(self):
        with pytest.raises(ValueError, match="Port must be"):
            Node(host="example.com", port=0)

    def test_port_too_high(self):
        with pytest.raises(ValueError, match="Port must be"):
            Node(host="example.com", port=70000)

    def test_valid_ipv4(self):
        node = Node(host="192.168.1.1")
        assert node.host == "192.168.1.1"

    def test_valid_ipv6(self):
        node = Node(host="::1")
        assert node.host == "::1"

    def test_valid_dns(self):
        node = Node(host="web-1.prod.example.com")
        assert node.host == "web-1.prod.example.com"


class TestNodeParse:
    def test_simple_host(self):
        node = Node.parse("example.com")
        assert node.host == "example.com"
        assert node.user == "root"
        assert node.port == 22

    def test_user_at_host(self):
        node = Node.parse("deploy@10.0.0.1")
        assert node.user == "deploy"
        assert node.host == "10.0.0.1"
        assert node.port == 22

    def test_user_at_host_port(self):
        node = Node.parse("admin@web1.example.com:2222")
        assert node.user == "admin"
        assert node.host == "web1.example.com"
        assert node.port == 2222

    def test_host_port(self):
        node = Node.parse("10.0.0.1:2222")
        assert node.host == "10.0.0.1"
        assert node.port == 2222

    def test_ipv6_bracket(self):
        node = Node.parse("root@[::1]:2222")
        assert node.host == "::1"
        assert node.user == "root"
        assert node.port == 2222

    def test_ipv6_bracket_no_port(self):
        node = Node.parse("[::1]")
        assert node.host == "::1"
        assert node.port == 22

    def test_unterminated_bracket(self):
        with pytest.raises(ValueError, match="Unterminated"):
            Node.parse("[::1")

    def test_whitespace_trimmed(self):
        node = Node.parse("  example.com  ")
        assert node.host == "example.com"
