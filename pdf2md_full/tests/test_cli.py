"""Tests for the ``pdf2md-full`` command-line entry point."""
import shutil
import subprocess
import sys

import pytest

from pdf2md_full import convert_pdf_to_markdown
from pdf2md_full import cli


def test_main_writes_markdown_to_stdout(monkeypatch, capsys, sample_pdf):
    monkeypatch.setattr(cli, "convert_pdf_to_markdown", lambda path: "# output")

    assert cli.main([sample_pdf]) == 0
    captured = capsys.readouterr()
    assert captured.out == "# output"
    assert captured.err == ""


def test_main_writes_utf8_markdown_to_output_file(tmp_path, monkeypatch, sample_pdf):
    monkeypatch.setattr(cli, "convert_pdf_to_markdown", lambda path: "中文\n")
    output = tmp_path / "result.md"

    assert cli.main([sample_pdf, "-o", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == "中文\n"


def test_main_reports_missing_input_on_stderr(capsys, tmp_path):
    missing = tmp_path / "missing.pdf"

    assert cli.main([str(missing)]) == 1
    captured = capsys.readouterr()
    assert "pdf2md-full:" in captured.err
    assert str(missing) in captured.err
    assert captured.out == ""


def test_module_cli_output_matches_library(sample_pdf, capsys):
    expected = convert_pdf_to_markdown(sample_pdf)

    assert cli.main([sample_pdf]) == 0
    assert capsys.readouterr().out == expected


def test_installed_script_generates_output(sample_pdf):
    executable = shutil.which("pdf2md-full")
    if executable is None:
        pytest.skip("pdf2md-full console script is not installed")

    result = subprocess.run(
        [executable, sample_pdf],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == convert_pdf_to_markdown(sample_pdf)
    assert result.stderr == ""
