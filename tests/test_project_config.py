"""Tests for the declarative configuration (``ubproject.toml``, ``[test_reports]``).

The loader validates and normalises the section, and the Sphinx build bridges
its keys onto the ``tr_*`` config values. Both must agree on which file
describes a project, or the build is configured by something other than what
the project declares.
"""

import os
from pathlib import Path
from shutil import copytree

import pytest

from sphinxcontrib.test_reports.exceptions import InvalidConfigurationError
from sphinxcontrib.test_reports.projectconfig import (
    BRIDGE_KEYS,
    DEFAULT_TOML_FILENAME,
    FOREIGN_TABLES,
    TomlConfigError,
    find_project_config,
    load_project_config,
)


def _write(tmp_path, toml_source, name=DEFAULT_TOML_FILENAME):
    config = tmp_path / name
    config.write_text(toml_source, encoding="utf-8")
    return config


class TestLoader:
    """The Sphinx-free loader: parsing, normalising, anchoring, rejecting."""

    def test_missing_file_is_none(self, tmp_path):
        assert load_project_config(tmp_path / DEFAULT_TOML_FILENAME) is None

    def test_missing_section_is_empty(self, tmp_path):
        _write(tmp_path, '[project]\nname = "x"\n')
        assert load_project_config(tmp_path / DEFAULT_TOML_FILENAME) == {}

    def test_full_section_round_trips(self, tmp_path):
        _write(
            tmp_path,
            """
            [test_reports]
            file_option = "report_file"
            source_file_option = "file"
            import_encoding = "latin1"
            deterministic_case_ids = true
            suite_id_length = 4
            extra_options = ["more_info"]
            property_link_types = { request = "req" }
            """,
        )
        config = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert config["file_option"] == "report_file"
        assert config["source_file_option"] == "file"
        assert config["import_encoding"] == "latin1"
        assert config["deterministic_case_ids"] is True
        assert config["suite_id_length"] == 4
        assert config["extra_options"] == ["more_info"]
        assert config["property_link_types"] == {"request": "req"}

    def test_foreign_sub_table_is_kept_without_a_warning(self, tmp_path):
        # [test_reports.convert] belongs to the report converter. This reader
        # must neither complain about it nor apply it to a tr_* value -- the
        # section describes the project, not just this extension.
        _write(
            tmp_path,
            """
            [test_reports]
            file_option = "report_file"

            [test_reports.convert]
            project = "demo"
            need_type = "check"
            """,
        )
        reported = []
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME, reported.append)
        assert reported == []
        assert section["convert"] == {"project": "demo", "need_type": "check"}
        assert not set(FOREIGN_TABLES) & set(BRIDGE_KEYS)

    def test_unknown_key_is_reported_but_not_fatal(self, tmp_path):
        # ubproject.toml is shared with tools on independent release cadences,
        # so a key this reader does not model must not take the build down --
        # but a typo has to be visible, and the key must not be passed on.
        _write(tmp_path, "[test_reports]\ndeterministic_id = true\n")
        reported = []
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME, reported.append)
        assert section == {}
        assert len(reported) == 1
        assert "deterministic_id" in reported[0]
        assert "deterministic_case_ids" in reported[0]  # supported keys listed

    def test_unknown_key_needs_no_reporter(self, tmp_path):
        _write(tmp_path, "[test_reports]\nnope = 1\nfile_option = 'f'\n")
        assert load_project_config(tmp_path / DEFAULT_TOML_FILENAME) == {
            "file_option": "f"
        }

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("property_link_types", '{ request = ["req"] }'),
            ("property_link_types", "{ request = 3 }"),
        ],
    )
    def test_table_values_are_type_checked(self, tmp_path, key, value):
        # Without this the value reaches the directives, which fail with a bare
        # TypeError on an unhashable field name instead of a config error.
        _write(tmp_path, f"[test_reports]\n{key} = {value}\n")
        with pytest.raises(TomlConfigError, match=key):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_json_mapping_nesting_stays_free_form(self, tmp_path):
        # It mirrors an arbitrary parser mapping, so only the outer table is
        # checked -- validating deeper would reject valid configurations.
        _write(
            tmp_path,
            "[test_reports.json_mapping.json_config.testsuite]\nname = 1\n",
        )
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert section["json_mapping"] == {"json_config": {"testsuite": {"name": 1}}}

    @pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        reason="root reads unreadable files",
    )
    def test_unreadable_file_is_a_config_error(self, tmp_path):
        # is_file() succeeding does not mean the open will; an unwrapped
        # OSError would surface as a traceback instead of a config error.
        config = _write(tmp_path, "[test_reports]\nfile_option = 'f'\n")
        config.chmod(0o000)
        try:
            with pytest.raises(TomlConfigError, match="cannot be read"):
                load_project_config(config)
        finally:
            config.chmod(0o644)

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("file_option", "42"),
            ("suite_id_length", '"four"'),  # string for int
            ("suite_id_length", "true"),  # bool must not pass for int
            ("deterministic_case_ids", '"yes"'),  # string for bool
            ("extra_options", '"more_info"'),  # a bare string is not an array
            ("property_link_types", '["a"]'),
        ],
    )
    def test_wrong_types_are_rejected(self, tmp_path, key, value):
        _write(tmp_path, f"[test_reports]\n{key} = {value}\n")
        with pytest.raises(TomlConfigError, match=key):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_invalid_toml_is_rejected(self, tmp_path):
        _write(tmp_path, "[test-reports\n")
        with pytest.raises(TomlConfigError, match="invalid TOML"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_section_must_be_a_table(self, tmp_path):
        _write(tmp_path, "test_reports = 5\n")
        with pytest.raises(TomlConfigError, match="must be a table"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_need_type_positional_list_still_works(self, tmp_path):
        # The conf.py spelling, so existing projects can copy their lists over
        # verbatim.
        _write(
            tmp_path,
            '[test_reports]\ncase = ["test-case", "testcase", "Test-Case", "TC_", "#999999", "rectangle"]\n',
        )
        config = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert config["case"] == [
            "test-case",
            "testcase",
            "Test-Case",
            "TC_",
            "#999999",
            "rectangle",
        ]

    def test_need_type_named_table(self, tmp_path):
        # Six bare strings cannot be told apart; the table spelling names them.
        _write(
            tmp_path,
            """
            [test_reports.case]
            directive = "test-case"
            type = "testcase"
            name = "Test-Case"
            prefix = "TC_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        config = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert config["case"] == [
            "test-case",
            "testcase",
            "Test-Case",
            "TC_",
            "#999999",
            "rectangle",
        ]

    def test_need_type_table_rejects_partial_and_unknown(self, tmp_path):
        _write(tmp_path, '[test_reports.case]\ndirective = "test-case"\n')
        with pytest.raises(TomlConfigError, match="missing"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        _write(
            tmp_path,
            """
            [test_reports.case]
            directive = "test-case"
            type = "testcase"
            name = "Test-Case"
            prefix = "TC_"
            color = "#999999"
            style = "rectangle"
            typo = true
            """,
        )
        with pytest.raises(TomlConfigError, match="unknown typo"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_relative_paths_anchor_to_the_toml_directory(self, tmp_path):
        # The file is self-describing: moving it as a unit keeps its relative
        # paths meaningful, and both consumers resolve them identically.
        subdir = tmp_path / "config"
        subdir.mkdir()
        _write(
            subdir,
            '[test_reports]\nrootdir = "docs"\nreport_template = "templates/report.txt"\n',
            name=subdir / DEFAULT_TOML_FILENAME,
        )
        config = load_project_config(subdir / DEFAULT_TOML_FILENAME)
        assert config["rootdir"] == str(subdir / "docs")
        assert config["report_template"] == str(subdir / "templates" / "report.txt")

    def test_absolute_paths_stay_untouched(self, tmp_path):
        _write(tmp_path, f'[test_reports]\nrootdir = "{tmp_path}"\n')
        config = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert config["rootdir"] == str(tmp_path)


class TestSphinxBridge:
    """The build reads the same section and honours the same precedence."""

    @pytest.mark.parametrize(
        "test_app",
        [{"buildername": "html", "srcdir": "doc_test/ubproject_toml"}],
        indirect=True,
    )
    def test_build_succeeds(self, test_app):
        test_app.build()
        assert test_app.statuscode == 0

    @pytest.mark.parametrize(
        "test_app",
        [{"buildername": "html", "srcdir": "doc_test/ubproject_toml"}],
        indirect=True,
    )
    def test_toml_beats_conf_py(self, test_app):
        """conf.py names one field, ubproject.toml another; TOML must win."""
        test_app.build()
        html = Path(test_app.outdir, "index.html").read_text(encoding="utf-8")
        # file_option = "report_file" (TOML) won over "confpy_report_file".
        assert "needs_report_file" in html
        # The report path lands on the renamed field, the source location on
        # file/line -- the rename took effect end to end.
        assert "gtest_data.xml" in html

    @pytest.mark.parametrize(
        "test_app",
        [{"buildername": "html", "srcdir": "doc_test/ubproject_toml"}],
        indirect=True,
    )
    def test_extra_options_from_toml_are_accepted(self, test_app):
        """:more_info: is only valid because tr_extra_options came from TOML."""
        test_app.build()
        html = Path(test_app.outdir, "index.html").read_text(encoding="utf-8")
        assert "accepted because tr_extra_options came from ubproject.toml" in html

    def test_bridge_rejects_a_broken_section(self, tmp_path):
        """A malformed section aborts the build as a configuration error.

        The bridge runs on ``config-inited``, so the error surfaces while the
        application is set up -- before any document is read.
        """
        copytree(Path(__file__).parent / "doc_test" / "basic_doc", tmp_path / "docs")
        _write(tmp_path / "docs", "[test_reports]\nsuite_id_length = 'four'\n")

        from sphinx.application import Sphinx

        docs = tmp_path / "docs"
        with pytest.raises(InvalidConfigurationError, match="suite_id_length"):
            Sphinx(
                srcdir=docs,
                confdir=docs,
                outdir=docs / "_build" / "html",
                doctreedir=docs / "_build" / "doctrees",
                buildername="html",
                freshenv=True,
            )


class TestDiscovery:
    """The upward search that lets both consumers find the same file."""

    def test_finds_the_file_in_the_starting_directory(self, tmp_path):
        config = _write(tmp_path, "[test_reports]\n")
        assert find_project_config(tmp_path) == config

    def test_walks_up_to_the_project_root(self, tmp_path):
        config = _write(tmp_path, "[test_reports]\n")
        deep = tmp_path / "docs" / "source"
        deep.mkdir(parents=True)
        assert find_project_config(deep) == config

    def test_stops_at_a_project_root_without_the_file(self, tmp_path):
        # An unrelated parent project must not have its configuration adopted.
        _write(tmp_path, "[test_reports]\n")
        inner = tmp_path / "packages" / "inner"
        inner.mkdir(parents=True)
        (inner / "pyproject.toml").write_text("", encoding="utf-8")
        assert find_project_config(inner) is None

    def test_the_file_wins_over_the_marker_in_one_directory(self, tmp_path):
        # Root markers only end a *fruitless* step; a root holding both is the
        # normal case and must be found.
        config = _write(tmp_path, "[test_reports]\n")
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
        assert find_project_config(tmp_path) == config

    def test_missing_file_is_none(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert find_project_config(tmp_path) is None


class TestPathAnchoring:
    """Relative paths resolve the same way for both consumers."""

    def test_symlinked_directories_are_preserved(self, tmp_path):
        # conf.py's spelling of tr_rootdir does not collapse symlinks, so the
        # TOML spelling must not either, or the two name different directories.
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)
        config = _write(link, "[test_reports]\nrootdir = 'reports'\n")
        section = load_project_config(config)
        assert section["rootdir"] == str(link / "reports")


def _build(srcdir, **kwargs):
    """Set up a Sphinx application, returning it with its warning output."""
    from io import StringIO

    from sphinx.application import Sphinx

    warnings = StringIO()
    app = Sphinx(
        srcdir=srcdir,
        confdir=srcdir,
        outdir=srcdir / "_build" / "html",
        doctreedir=srcdir / "_build" / "doctrees",
        buildername="html",
        freshenv=True,
        status=None,
        warning=warnings,
        **kwargs,
    )
    return app, warnings.getvalue()


def _basic_doc(tmp_path, toml=None, conf_extra=""):
    docs = tmp_path / "docs"
    copytree(Path(__file__).parent / "doc_test" / "basic_doc", docs)
    # Bound the upward search so the outcome cannot depend on the sandbox.
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    if toml is not None:
        _write(docs, toml)
    if conf_extra:
        with (docs / "conf.py").open("a", encoding="utf-8") as handle:
            handle.write("\n" + conf_extra + "\n")
    return docs


class TestBridgePrecedence:
    """``-D`` > TOML > conf.py, and the diagnostics for a file that is missing."""

    def test_command_line_override_beats_toml(self, tmp_path):
        # -D is the per-invocation escape hatch. Sphinx applies it before
        # config-inited, so the bridge has to leave those keys alone.
        docs = _basic_doc(tmp_path, "[test_reports]\nfile_option = 'from_toml'\n")
        app, _ = _build(docs, confoverrides={"tr_file_option": "from_command_line"})
        assert app.config.tr_file_option == "from_command_line"

    def test_toml_beats_conf_py_without_an_override(self, tmp_path):
        docs = _basic_doc(
            tmp_path,
            "[test_reports]\nfile_option = 'from_toml'\n",
            conf_extra="tr_file_option = 'from_conf_py'",
        )
        app, _ = _build(docs)
        assert app.config.tr_file_option == "from_toml"

    def test_disabling_toml_reading_is_not_a_type_warning(self, tmp_path):
        # The documented opt-out must not trip Sphinx's own confval check --
        # a project building with -W would fail on it.
        docs = _basic_doc(
            tmp_path,
            "[test_reports]\nfile_option = 'from_toml'\n",
            conf_extra="tr_config_from_toml = None",
        )
        app, warnings = _build(docs)
        assert "tr_config_from_toml" not in warnings
        assert app.config.tr_file_option == "file"

    def test_missing_explicit_config_warns(self, tmp_path):
        docs = _basic_doc(tmp_path, conf_extra="tr_config_from_toml = 'nope.toml'")
        _, warnings = _build(docs)
        assert "does not exist" in warnings

    def test_missing_default_config_is_silent(self, tmp_path):
        docs = _basic_doc(tmp_path)
        _, warnings = _build(docs)
        assert "ubproject.toml" not in warnings

    def test_unknown_key_warns_but_builds(self, tmp_path):
        docs = _basic_doc(
            tmp_path, "[test_reports]\nfile_option = 'ok'\nno_such_key = 1\n"
        )
        app, warnings = _build(docs)
        assert "no_such_key" in warnings
        assert app.config.tr_file_option == "ok"

    def test_walks_up_from_the_confdir(self, tmp_path):
        # ubproject.toml at the repo root, conf.py in docs/ -- the layout the
        # shared file exists for.
        docs = _basic_doc(tmp_path)
        _write(tmp_path, "[test_reports]\nfile_option = 'from_the_root'\n")
        app, _ = _build(docs)
        assert app.config.tr_file_option == "from_the_root"
