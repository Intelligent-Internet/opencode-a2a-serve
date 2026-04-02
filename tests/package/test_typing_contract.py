from pathlib import Path

PYPROJECT_TEXT = Path("pyproject.toml").read_text()


def test_package_declares_py_typed_marker() -> None:
    assert Path("src/opencode_a2a/py.typed").is_file()
    assert "[tool.setuptools.package-data]" in PYPROJECT_TEXT
    assert 'opencode_a2a = ["py.typed"]' in PYPROJECT_TEXT
