from __future__ import annotations

from unittest import mock

import pytest

from opencode_a2a_server import __version__, cli


def test_cli_help_does_not_require_runtime_settings(capsys: pytest.CaptureFixture[str]) -> None:
    with mock.patch("opencode_a2a_server.cli.serve_main") as serve_mock:
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["--help"])

    assert excinfo.value.code == 0
    assert "serve" in capsys.readouterr().out
    serve_mock.assert_not_called()


def test_cli_version_does_not_require_runtime_settings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with mock.patch("opencode_a2a_server.cli.serve_main") as serve_mock:
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["--version"])

    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out
    serve_mock.assert_not_called()


def test_cli_defaults_to_serve_when_no_subcommand() -> None:
    with mock.patch("opencode_a2a_server.cli.serve_main") as serve_mock:
        assert cli.main([]) == 0

    serve_mock.assert_called_once_with()


def test_cli_serve_subcommand_invokes_runtime() -> None:
    with mock.patch("opencode_a2a_server.cli.serve_main") as serve_mock:
        assert cli.main(["serve"]) == 0

    serve_mock.assert_called_once_with()
