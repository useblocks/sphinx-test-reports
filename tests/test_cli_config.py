"""The convert CLI reads ``[test_reports.convert]`` from ``ubproject.toml``.

Precedence is flag > TOML table > built-in default, and the file is found the
way the Sphinx build finds it -- searched for upwards to the project root -- so
the two consumers of one project never read different descriptions of it.
"""

import json
import os
from pathlib import Path

import pytest

from sphinxcontrib.test_reports.cli import _DEFAULTS, main
from sphinxcontrib.test_reports.projectconfig import (
    CONVERSION_KEYS,
    DEFAULT_TOML_FILENAME,
)

UTILS = Path(__file__).parent / "doc_test" / "utils"
PYTEST_XML = str(UTILS / "pytest_data.xml")


def _write(directory, toml_source, name=DEFAULT_TOML_FILENAME):
    config = directory / name
    config.write_text(toml_source, encoding="utf-8")
    return config


def run_convert(tmp_path, arguments, toml=None, config_name=None, subdir=None):
    """Run ``convert`` from *tmp_path* (or a subdirectory) and parse the output.

    A project-root marker bounds the upward search, so the outcome never depends
    on what happens to sit above the temporary directory.
    """
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    if toml is not None:
        _write(tmp_path, toml, name=config_name or DEFAULT_TOML_FILENAME)
    workdir = tmp_path
    if subdir is not None:
        workdir = tmp_path / subdir
        workdir.mkdir(parents=True, exist_ok=True)
    previous = os.getcwd()
    os.chdir(workdir)
    try:
        code = main(["build", "needs", PYTEST_XML, "-o", "needs.json", *arguments])
    finally:
        os.chdir(previous)
    payload = {}
    output = workdir / "needs.json"
    if output.is_file():
        payload = json.loads(output.read_text(encoding="utf-8"))
    return code, payload


def _first_need(payload):
    return next(iter(payload["versions"][payload["current_version"]]["needs"].values()))


class TestPrecedence:
    """Flag > TOML > built-in default."""

    def test_table_provides_the_conversion_settings(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            [],
            toml="""
            [test_reports.convert]
            project = "My Project"
            version = "2.0"
            tags = ["ci", "unit"]
            link_properties = { PartiallyVerifies = "partially_verifies" }
            """,
        )
        assert code == 0
        assert payload["project"] == "My Project"
        assert payload["current_version"] == "2.0"
        need = _first_need(payload)
        assert need["tags"] == ["ci", "unit"]
        assert need["partially_verifies"] == []

    def test_flag_overrides_the_table(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--version", "9.9"],
            toml="[test_reports.convert]\nversion = '2.0'\n",
        )
        assert code == 0
        assert payload["current_version"] == "9.9"

    def test_table_overrides_the_builtin_default(self, tmp_path):
        # A need type other than the default has to be the build's too -- so
        # the file also names it as the case type.
        code, payload = run_convert(
            tmp_path,
            [],
            toml="[test_reports.convert]\nneed_type = 'check'\n"
            """
            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        assert code == 0
        assert _first_need(payload)["type"] == "check"

    def test_no_file_uses_the_defaults(self, tmp_path):
        code, payload = run_convert(tmp_path, [])
        assert code == 0
        assert payload["project"] == ""
        assert payload["current_version"] == "1.0"

    def test_an_explicit_empty_flag_beats_the_table(self, tmp_path):
        # "" is a value, not "not given": the flag clears the file's tags.
        code, payload = run_convert(
            tmp_path, ["--tags", ""], toml="[test_reports.convert]\ntags = ['x']\n"
        )
        assert code == 0
        assert _first_need(payload)["tags"] == []

    def test_link_property_flag_replaces_the_table(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--link-property", "Verifies=verifies"],
            toml='[test_reports.convert]\nlink_properties = { Other = "other_field" }\n',
        )
        assert code == 0
        need = _first_need(payload)
        assert "verifies" in need
        assert "other_field" not in need

    def test_field_names_from_the_section_shape_the_output(self, tmp_path):
        # The same file configures the build. Its field-name keys are read on
        # purpose -- the output has to have the shape of the build's needs --
        # while its other bridge keys are none of the converter's business.
        code, payload = run_convert(
            tmp_path,
            [],
            toml="""
            [test_reports]
            file_option = "report_file"
            source_file_option = "file"
            source_line_option = "line"
            extra_options = ["more_info"]

            [test_reports.convert]
            project = "p"
            """,
        )
        assert code == 0
        assert payload["project"] == "p"
        need = _first_need(payload)
        assert need["report_file"].endswith("pytest_data.xml")
        assert "file" in need and "line" in need
        assert "case_file" not in need
        assert "more_info" not in need


class TestFileLookup:
    """Where the file comes from, and what happens when it does not."""

    def test_walks_up_to_the_project_root(self, tmp_path):
        # The canonical layout: ubproject.toml at the root, the converter run
        # from a build directory below it.
        code, payload = run_convert(
            tmp_path,
            [],
            toml='[test_reports.convert]\nproject = "from the root"\n',
            subdir="build/testlogs",
        )
        assert code == 0
        assert payload["project"] == "from the root"

    def test_explicit_config_by_path(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--config", "staging.toml"],
            toml='[test_reports.convert]\nproject = "staged"\n',
            config_name="staging.toml",
        )
        assert code == 0
        assert payload["project"] == "staged"

    def test_explicit_missing_config_is_an_error(self, tmp_path, capsys):
        code, _ = run_convert(tmp_path, ["--config", "other.toml"])
        assert code == 2
        assert "other.toml" in capsys.readouterr().err

    def test_no_config_ignores_the_file(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--no-config"],
            toml='[test_reports.convert]\nproject = "from toml"\n',
        )
        assert code == 0
        assert payload["project"] == ""

    def test_config_and_no_config_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            main(
                [
                    "build",
                    "needs",
                    PYTEST_XML,
                    "-o",
                    "n.json",
                    "--no-config",
                    "--config",
                    "x",
                ]
            )


class TestDiagnostics:
    """Errors name what the user wrote, and warnings do not stop the run."""

    def test_wrong_type_in_the_table_is_an_error(self, tmp_path, capsys):
        code, _ = run_convert(
            tmp_path, [], toml="[test_reports.convert]\ntags = 'ci'\n"
        )
        assert code == 2
        assert "convert.tags" in capsys.readouterr().err

    def test_wrong_type_elsewhere_in_the_section_is_an_error_too(
        self, tmp_path, capsys
    ):
        # One file, one verdict: the converter rejects what the build rejects,
        # even for a key it does not itself use.
        code, _ = run_convert(
            tmp_path, [], toml="[test_reports]\nsuite_id_length = 'four'\n"
        )
        assert code == 2
        assert "suite_id_length" in capsys.readouterr().err

    def test_unknown_key_in_the_table_warns_but_converts(self, tmp_path, capsys):
        code, payload = run_convert(
            tmp_path,
            [],
            toml='[test_reports.convert]\nproject = "p"\nno_such_key = 1\n',
        )
        assert code == 0
        assert payload["project"] == "p"
        err = capsys.readouterr().err
        assert "no_such_key" in err
        assert "[test_reports.convert]" in err

    def test_half_remote_pair_from_the_table_names_the_table(self, tmp_path, capsys):
        # The value came from the file, so naming only the flags would point at
        # options that appear nowhere in the invocation.
        code, _ = run_convert(
            tmp_path,
            [],
            toml='[test_reports.convert]\nremote_url = "https://gh.com/o/r"\n',
        )
        assert code == 2
        message = capsys.readouterr().err
        assert "remote_url and --commit" in message
        assert "[test_reports.convert]" in message
        assert DEFAULT_TOML_FILENAME in message

    def test_half_remote_pair_from_flags_names_the_flags(self, tmp_path, capsys):
        code, _ = run_convert(tmp_path, ["--commit", "abc"])
        assert code == 2
        message = capsys.readouterr().err
        assert "--remote-url and --commit" in message
        assert "[test_reports.convert]" not in message

    def test_need_type_disagreeing_with_the_case_type_is_an_error(
        self, tmp_path, capsys
    ):
        # The build takes its need type from case.type; a needs.json written
        # with another type would neither register nor cross-link there.
        code, _ = run_convert(
            tmp_path,
            [],
            toml="""
            [test_reports.convert]
            need_type = "testcase"

            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        assert code == 2
        assert "need_type" in capsys.readouterr().err

    def test_malformed_link_property_value_is_an_error(self, tmp_path, capsys):
        code, _ = run_convert(
            tmp_path,
            [],
            toml='[test_reports.convert]\nlink_properties = { Verifies = ["v"] }\n',
        )
        assert code == 2
        assert "link_properties" in capsys.readouterr().err

    def test_need_type_flag_disagreeing_with_the_case_type_is_an_error(
        self, tmp_path, capsys
    ):
        # The loader only sees the file. A flag is not in the file, so the
        # merged value has to be checked again, or the flag bypasses the rule.
        code, _ = run_convert(
            tmp_path,
            ["--need-type", "testcase"],
            toml="""
            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        assert code == 2
        message = capsys.readouterr().err
        assert "--need-type is 'testcase'" in message
        assert "'check'" in message

    def test_the_default_need_type_disagreeing_with_the_case_type_is_an_error(
        self, tmp_path, capsys
    ):
        code, _ = run_convert(
            tmp_path,
            [],
            toml="""
            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        assert code == 2
        assert "the default need_type is 'testcase'" in capsys.readouterr().err

    def test_a_matching_need_type_flag_is_fine(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--need-type", "check"],
            toml="""
            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        assert code == 0
        assert _first_need(payload)["type"] == "check"


def test_every_conversion_key_has_a_builtin_default():
    # The import-time guard says the same; this keeps saying it under -O.
    assert set(_DEFAULTS) == set(CONVERSION_KEYS)
