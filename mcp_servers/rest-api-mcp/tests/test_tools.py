# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Tests for object validation and indicator matching."""

from __future__ import annotations

import pytest

from sfw_mcp_rest.fmc import matches_indicator
from sfw_mcp_rest.server import _names, _validate_object


class TestValidateObject:
    def test_accepts_a_host(self) -> None:
        assert _validate_object("APP1_HOST", "Host", "10.10.10.10") is None

    def test_accepts_a_network(self) -> None:
        assert _validate_object("APP1_NET", "Network", "10.10.20.0/24") is None

    def test_requires_a_name(self) -> None:
        assert _validate_object("", "Host", "10.10.10.10") == "name is required"

    def test_rejects_unknown_type(self) -> None:
        reason = _validate_object("X", "Range", "10.10.10.10")
        assert reason is not None
        assert "type must be one of" in reason

    def test_rejects_bad_address(self) -> None:
        reason = _validate_object("X", "Host", "not-an-ip")
        assert reason is not None
        assert "not a valid IP address" in reason

    def test_rejects_cidr_as_host(self) -> None:
        assert _validate_object("X", "Host", "10.10.20.0/24") is not None

    def test_steers_single_address_to_host_type(self) -> None:
        reason = _validate_object("X", "Network", "10.10.20.5/32")
        assert reason is not None
        assert "type Host" in reason


class TestMatchesIndicator:
    def test_substring_match(self) -> None:
        assert matches_indicator("10.10.20.0/24", "10.10.20") is True

    def test_address_inside_network(self) -> None:
        assert matches_indicator("10.10.20.0/24", "10.10.20.5") is True

    def test_address_outside_network(self) -> None:
        assert matches_indicator("10.10.20.0/24", "192.0.2.5") is False

    def test_subnet_containment(self) -> None:
        assert matches_indicator("10.10.0.0/16", "10.10.20.0/24") is True
        assert matches_indicator("10.10.20.0/24", "10.10.0.0/16") is False

    @pytest.mark.parametrize(("value", "indicator"), [("", "10.0.0.1"), ("10.0.0.1", ""), ("", "")])
    def test_empty_input_never_matches(self, value: str, indicator: str) -> None:
        assert matches_indicator(value, indicator) is False

    def test_non_ip_values_are_handled(self) -> None:
        assert matches_indicator("host.example.local", "example") is True
        assert matches_indicator("host.example.local", "10.0.0.1") is False


class TestRuleFieldNames:
    def test_extracts_object_names(self) -> None:
        rule = {"sourceNetworks": {"objects": [{"name": "APP1_HOST"}, {"name": "DB1_HOST"}]}}
        assert _names(rule, "sourceNetworks") == ["APP1_HOST", "DB1_HOST"]

    def test_absent_field_reads_as_any(self) -> None:
        assert _names({}, "sourceNetworks") == ["any"]
        assert _names({"sourceNetworks": {"objects": []}}, "sourceNetworks") == ["any"]
