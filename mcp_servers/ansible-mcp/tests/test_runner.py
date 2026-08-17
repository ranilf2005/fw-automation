# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Tests for the playbook allowlist, variable validation, and output parsing."""

from __future__ import annotations

from typing import ClassVar

import pytest

from sfw_mcp_ansible.config import ConfigError, discover_playbooks, resolve_playbook, run_enabled
from sfw_mcp_ansible.runner import changed_tasks, parse_recap, validate_extra_vars
from sfw_mcp_ansible.safety import (
    ConfirmationError,
    RunsDisabledError,
    issue_token,
    redact,
    require_runs_enabled,
    verify_token,
)


@pytest.fixture
def project(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """A minimal repo layout the config module will accept."""
    playbooks = tmp_path / "ansible" / "playbooks"
    playbooks.mkdir(parents=True)
    (tmp_path / "ansible" / "inventory.yml").write_text("all:\n  hosts:\n", encoding="utf-8")
    (playbooks / "get_domain.yml").write_text(
        "---\n- name: Get FMC domains\n  hosts: localhost\n  tasks: []\n", encoding="utf-8"
    )
    (playbooks / "create_network_objects.yml").write_text(
        "---\n- name: Create objects\n  hosts: localhost\n  tasks: []\n", encoding="utf-8"
    )
    monkeypatch.setenv("ANSIBLE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("ANSIBLE_PLAYBOOK_ALLOWLIST", raising=False)
    return tmp_path


class TestAllowlist:
    def test_discovers_playbooks(self, project) -> None:
        assert set(discover_playbooks()) == {"get_domain", "create_network_objects"}

    def test_flags_mutating_playbooks(self, project) -> None:
        playbooks = discover_playbooks()
        assert playbooks["create_network_objects"].mutates is True
        assert playbooks["get_domain"].mutates is False

    def test_uses_the_play_name_as_description(self, project) -> None:
        assert discover_playbooks()["get_domain"].description == "Get FMC domains"

    def test_explicit_allowlist_narrows_the_set(
        self, project, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANSIBLE_PLAYBOOK_ALLOWLIST", "get_domain")
        assert set(discover_playbooks()) == {"get_domain"}

    @pytest.mark.parametrize(
        "name",
        [
            "../../../etc/passwd",
            "/etc/passwd",
            "get_domain; rm -rf /",
            "get_domain.yml",
            "..\\..\\windows\\system32",
            "",
        ],
    )
    def test_rejects_paths_outside_the_allowlist(self, project, name: str) -> None:
        with pytest.raises(ConfigError, match="Unknown playbook"):
            resolve_playbook(name)

    def test_resolves_an_allowlisted_playbook(self, project) -> None:
        assert resolve_playbook("get_domain").path.is_file()

    def test_missing_ansible_dir_is_rejected(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANSIBLE_PROJECT_DIR", str(tmp_path))
        with pytest.raises(ConfigError, match="No 'ansible' directory"):
            discover_playbooks()


class TestExtraVars:
    def test_empty_is_fine(self) -> None:
        assert validate_extra_vars(None) == {}
        assert validate_extra_vars({}) == {}

    def test_allowlisted_variable_passes(self) -> None:
        assert validate_extra_vars({"domain_uuid": "abc"}) == {"domain_uuid": "abc"}

    @pytest.mark.parametrize(
        "name",
        [
            "ansible_httpapi_pass",
            "ansible_user",
            "fmc_password",
        ],
    )
    def test_credential_and_connection_vars_are_refused(self, name: str) -> None:
        with pytest.raises(ConfigError, match="not permitted"):
            validate_extra_vars({name: "x"})

    @pytest.mark.parametrize(
        "name",
        [
            "ANSIBLE_CONFIG",
            "ANSIBLE_VAULT_PASSWORD_FILE",
            "bad-name",
            "1var",
            "var name",
            "../x",
            "$(id)",
        ],
    )
    def test_malformed_names_are_refused(self, name: str) -> None:
        with pytest.raises(ConfigError, match="Invalid variable name"):
            validate_extra_vars({name: "x"})

    def test_unsupported_types_are_refused(self) -> None:
        with pytest.raises(ConfigError, match="unsupported value type"):
            validate_extra_vars({"domain_uuid": {1, 2}})


class TestOutputParsing:
    RECAP = (
        "PLAY RECAP *********************************************************\n"
        "localhost                  : ok=3    changed=1    unreachable=0    failed=0    "
        "skipped=0    rescued=0    ignored=0\n"
    )

    def test_parses_recap_counters(self) -> None:
        assert parse_recap(self.RECAP) == {
            "localhost": {"ok": 3, "changed": 1, "unreachable": 0, "failed": 0}
        }

    def test_no_recap_yields_empty(self) -> None:
        assert parse_recap("nothing useful here") == {}

    def test_extracts_changed_task_names(self) -> None:
        stdout = (
            "TASK [Assert credentials are present] ***\n"
            "ok: [localhost]\n"
            "TASK [Create objects] ***\n"
            "changed: [localhost]\n"
        )
        assert changed_tasks(stdout) == ["Create objects"]

    def test_no_changes_yields_empty(self) -> None:
        assert changed_tasks("TASK [Get domains] ***\nok: [localhost]\n") == []


class TestRunGate:
    def test_runs_are_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANSIBLE_MCP_ALLOW_RUN", raising=False)
        assert run_enabled() is False
        with pytest.raises(RunsDisabledError):
            require_runs_enabled()

    def test_runs_can_be_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANSIBLE_MCP_ALLOW_RUN", "true")
        require_runs_enabled()


class TestConfirmation:
    PLAN: ClassVar[dict[str, object]] = {
        "playbook": "create_network_objects",
        "extra_vars": {},
        "would_change": ["Create objects"],
    }

    def test_round_trip(self) -> None:
        verify_token(self.PLAN, issue_token(self.PLAN)["confirmation_token"])

    def test_token_is_bound_to_the_playbook(self) -> None:
        token = issue_token(self.PLAN)["confirmation_token"]
        swapped = {**self.PLAN, "playbook": "delete_everything"}
        with pytest.raises(ConfirmationError, match="does not authorise"):
            verify_token(swapped, token)

    def test_token_is_bound_to_the_variables(self) -> None:
        token = issue_token(self.PLAN)["confirmation_token"]
        swapped = {**self.PLAN, "extra_vars": {"domain_uuid": "other"}}
        with pytest.raises(ConfirmationError, match="does not authorise"):
            verify_token(swapped, token)

    def test_expired_token_is_rejected(self) -> None:
        token = issue_token(self.PLAN, ttl_seconds=-1)["confirmation_token"]
        with pytest.raises(ConfirmationError, match="expired"):
            verify_token(self.PLAN, token)


class TestRedaction:
    def test_strips_ansible_credentials(self) -> None:
        cleaned = redact('ansible_httpapi_pass: "hunter2"')
        assert "hunter2" not in cleaned
        assert "<redacted>" in cleaned

    def test_strips_vault_blobs(self) -> None:
        cleaned = redact("$ANSIBLE_VAULT;1.1;AES256\n3462316164653...\n")
        assert "3462316164653" not in cleaned
