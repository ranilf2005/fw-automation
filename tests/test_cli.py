# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Ranil Fernando
"""Tests for the shared command-line handling."""

from __future__ import annotations

import logging

import pytest

from common.cli import parse_args, parse_csv_args
from common.logger import get_logger, set_level


class TestParseArgs:
    def test_help_exits_cleanly(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.argv", ["prog", "--help"])

        with pytest.raises(SystemExit) as exc:
            parse_args("Do a thing.")

        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "Do a thing." in out
        assert "FMC_HOST" in out

    def test_no_arguments_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", ["prog"])
        assert parse_args("Do a thing.").log_level is None

    def test_unknown_flag_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", ["prog", "--nope"])

        with pytest.raises(SystemExit) as exc:
            parse_args("Do a thing.")

        assert exc.value.code == 2


class TestParseCsvArgs:
    def test_explicit_path_is_used(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        csv = tmp_path / "objects.csv"
        csv.write_text("name,type,value,description\n", encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["prog", str(csv)])

        assert parse_csv_args("Create objects.", "inputs/objects.csv").input == csv

    def test_default_is_the_repo_sample(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", ["prog"])

        assert parse_csv_args("Create objects.", "inputs/objects.csv").input.name == "objects.csv"

    def test_missing_file_reports_the_path(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.argv", ["prog", "/nonexistent/nope.csv"])

        with pytest.raises(SystemExit) as exc:
            parse_csv_args("Create objects.", "inputs/objects.csv")

        assert exc.value.code == 2
        assert "input CSV not found" in capsys.readouterr().err

    def test_help_lists_the_default(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.argv", ["prog", "--help"])

        with pytest.raises(SystemExit):
            parse_csv_args("Create objects.", "inputs/objects.csv")

        assert "inputs/objects.csv" in capsys.readouterr().out


class TestLogLevelOverride:
    def test_relevels_loggers_created_before_parsing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        logger = get_logger("test_cli_relevel")
        logger.setLevel(logging.INFO)
        monkeypatch.setattr("sys.argv", ["prog", "--log-level", "DEBUG"])

        parse_args("Do a thing.")

        assert logger.level == logging.DEBUG

    def test_set_level_is_idempotent(self) -> None:
        logger = get_logger("test_cli_idempotent")
        set_level("WARNING")
        set_level("WARNING")

        assert logger.level == logging.WARNING
