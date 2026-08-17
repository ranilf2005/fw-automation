# SPDX-License-Identifier: MIT
# Copyright (c) 2026 secure-firewall-automation-starter contributors
"""Tests for plan parsing, sanitisation, the workspace allowlist, and the apply gate."""

from __future__ import annotations

from typing import ClassVar

import pytest

from sfw_mcp_terraform.config import (
    ConfigError,
    apply_enabled,
    discover_workspaces,
    resolve_workspace,
)
from sfw_mcp_terraform.runner import classify, summarise_plan, summarise_state
from sfw_mcp_terraform.safety import (
    ApplyDisabledError,
    ConfirmationError,
    issue_token,
    redact,
    require_apply_enabled,
    verify_token,
)


@pytest.fixture
def workspaces(tmp_path, monkeypatch: pytest.MonkeyPatch):
    alpha = tmp_path / "alpha"
    alpha.mkdir()
    (alpha / "main.tf").write_text("# empty\n", encoding="utf-8")
    beta = tmp_path / "beta"
    beta.mkdir()
    (beta / "main.tf").write_text("# empty\n", encoding="utf-8")
    monkeypatch.setenv("TF_MCP_WORKSPACES", f"alpha={alpha},beta={beta}")
    return tmp_path


class TestWorkspaceAllowlist:
    def test_discovers_named_workspaces(self, workspaces) -> None:
        assert set(discover_workspaces()) == {"alpha", "beta"}

    def test_resolves_by_name(self, workspaces) -> None:
        assert resolve_workspace("alpha").name == "alpha"

    @pytest.mark.parametrize(
        "name", ["gamma", "../../etc", "/etc", "alpha/../beta", "alpha; rm -rf /"]
    )
    def test_rejects_anything_not_allowlisted(self, workspaces, name: str) -> None:
        with pytest.raises(ConfigError, match="Unknown workspace"):
            resolve_workspace(name)

    def test_ambiguous_default_is_rejected(self, workspaces) -> None:
        with pytest.raises(ConfigError, match="pass workspace"):
            resolve_workspace(None)

    def test_directory_without_tf_files_is_rejected(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.setenv("TF_MCP_WORKSPACES", f"empty={empty}")
        with pytest.raises(ConfigError, match="no .tf files"):
            discover_workspaces()


class TestClassify:
    @pytest.mark.parametrize(
        ("actions", "expected"),
        [
            (["no-op"], "no_change"),
            (["create"], "create"),
            (["update"], "update"),
            (["delete"], "delete"),
            (["delete", "create"], "replace"),
            (["create", "delete"], "replace"),
            (["read"], "read"),
        ],
    )
    def test_known_action_sets(self, actions: list[str], expected: str) -> None:
        assert classify(actions) == expected

    def test_unknown_actions_do_not_crash(self) -> None:
        assert classify([]) == "unknown"


class TestSummarisePlan:
    PLAN: ClassVar[dict[str, object]] = {
        "format_version": "1.2",
        "terraform_version": "1.9.8",
        "resource_changes": [
            {
                "address": "fmc_network_objects.app1",
                "type": "fmc_network_objects",
                "name": "app1",
                "change": {
                    "actions": ["create"],
                    "before": None,
                    "after": {"name": "APP1_NET", "value": "10.10.20.0/24"},
                    "after_sensitive": {},
                },
            },
            {
                "address": "fmc_network_objects.old",
                "type": "fmc_network_objects",
                "name": "old",
                "change": {
                    "actions": ["delete"],
                    "before": {"name": "OLD_NET", "value": "10.10.99.0/24"},
                    "after": None,
                    "before_sensitive": {},
                },
            },
            {
                "address": "fmc_network_objects.same",
                "type": "fmc_network_objects",
                "name": "same",
                "change": {"actions": ["no-op"]},
            },
        ],
    }

    def test_counts_by_action(self) -> None:
        summary = summarise_plan(self.PLAN)["summary"]
        assert summary["create"] == 1
        assert summary["delete"] == 1
        assert summary["no_change"] == 1

    def test_flags_destructive_plans(self) -> None:
        assert summarise_plan(self.PLAN)["is_destructive"] is True

    def test_no_op_resources_are_excluded_from_changes(self) -> None:
        addresses = [c["address"] for c in summarise_plan(self.PLAN)["changes"]]
        assert "fmc_network_objects.same" not in addresses

    def test_empty_plan_is_not_destructive(self) -> None:
        summary = summarise_plan({"resource_changes": []})
        assert summary["has_changes"] is False
        assert summary["is_destructive"] is False

    def test_reports_changed_attributes(self) -> None:
        plan = {
            "resource_changes": [
                {
                    "address": "a.b",
                    "change": {
                        "actions": ["update"],
                        "before": {"name": "X", "value": "1.1.1.1"},
                        "after": {"name": "X", "value": "2.2.2.2"},
                    },
                }
            ]
        }
        assert summarise_plan(plan)["changes"][0]["changed_attributes"] == ["value"]


class TestSensitiveRedaction:
    def test_sensitive_attributes_are_masked(self) -> None:
        plan = {
            "resource_changes": [
                {
                    "address": "a.b",
                    "change": {
                        "actions": ["create"],
                        "after": {"name": "X", "password": "hunter2"},
                        "after_sensitive": {"password": True},
                    },
                }
            ]
        }
        after = summarise_plan(plan)["changes"][0]["after"]
        assert after["password"] == "<sensitive>"
        assert after["name"] == "X"

    def test_state_sensitive_values_are_masked(self) -> None:
        state = {
            "terraform_version": "1.9.8",
            "values": {
                "root_module": {
                    "resources": [
                        {
                            "address": "a.b",
                            "type": "a",
                            "name": "b",
                            "values": {"name": "X", "token": "abc123"},
                            "sensitive_values": {"token": True},
                        }
                    ]
                }
            },
        }
        summary = summarise_state(state)
        assert summary["resource_count"] == 1
        assert summary["resources"][0]["values"]["token"] == "<sensitive>"


class TestApplyGate:
    def test_apply_is_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TF_MCP_ALLOW_APPLY", raising=False)
        assert apply_enabled() is False
        with pytest.raises(ApplyDisabledError):
            require_apply_enabled()

    def test_apply_can_be_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TF_MCP_ALLOW_APPLY", "true")
        require_apply_enabled()


class TestConfirmation:
    PAYLOAD: ClassVar[dict[str, object]] = {
        "workspace": "starter",
        "summary": {"create": 1, "delete": 0},
        "is_destructive": False,
        "addresses": ["fmc_network_objects.app1"],
    }

    def test_round_trip(self) -> None:
        verify_token(self.PAYLOAD, issue_token(self.PAYLOAD)["confirmation_token"])

    def test_token_is_bound_to_the_address_list(self) -> None:
        token = issue_token(self.PAYLOAD)["confirmation_token"]
        swapped = {**self.PAYLOAD, "addresses": ["fmc_network_objects.production"]}
        with pytest.raises(ConfirmationError, match="does not authorise"):
            verify_token(swapped, token)

    def test_token_is_bound_to_the_workspace(self) -> None:
        token = issue_token(self.PAYLOAD)["confirmation_token"]
        with pytest.raises(ConfirmationError, match="does not authorise"):
            verify_token({**self.PAYLOAD, "workspace": "production"}, token)

    def test_expired_token_is_rejected(self) -> None:
        token = issue_token(self.PAYLOAD, ttl_seconds=-1)["confirmation_token"]
        with pytest.raises(ConfirmationError, match="expired"):
            verify_token(self.PAYLOAD, token)


class TestRedaction:
    def test_strips_tf_var_secrets(self) -> None:
        cleaned = redact("TF_VAR_fmc_password=hunter2")
        assert "hunter2" not in cleaned

    def test_strips_password_attributes(self) -> None:
        assert "hunter2" not in redact('fmc_password = "hunter2"')
