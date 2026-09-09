"""The pytest plugin produces the XML shape this extension reads.

Run through ``pytester``: a small test file is executed with the plugin enabled
and the resulting JUnit XML inspected.
"""

import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from sphinxcontrib.test_reports import pytest_plugin
from sphinxcontrib.test_reports.pytest_plugin import (
    apply_test_metadata,
    clean_source_path,
    properties_mapping,
    register_property,
)

PLUGIN = "sphinxcontrib.test_reports.pytest_plugin"

DECORATED = """
from sphinxcontrib.test_reports.pytest_plugin import add_test_properties

@add_test_properties(
    partially_verifies=["REQ_1", "REQ_2"],
    test_type="requirements-based",
    derivation_technique="requirements-analysis",
    Owner="team-a",
)
def test_addition():
    assert 1 + 1 == 2


def test_plain():
    assert True
"""

RUNTIME = """
import pytest
from sphinxcontrib.test_reports.pytest_plugin import apply_test_metadata

@pytest.mark.parametrize("spec", ["a.rst", "b.rst"])
def test_driven_by_a_file(spec, record_property, record_xml_attribute):
    apply_test_metadata(
        record_property=record_property,
        metadata={"fully_verifies": ["REQ_9"], "test_type": "interface-test"},
        record_xml_attribute=record_xml_attribute,
        file=f"specs/{spec}",
        line=7,
    )
    assert spec.endswith(".rst")
"""


def _line_of(source, needle):
    """1-based line of *needle* in the file pytester writes (it strips the
    leading blank line)."""
    return next(
        index
        for index, line in enumerate(source.strip().splitlines(), start=1)
        if line.startswith(needle)
    )


# pytest points a decorated function at its first decorator line.
ADDITION_LINE = _line_of(DECORATED, "@add_test_properties(")
PLAIN_LINE = _line_of(DECORATED, "def test_plain")


def _run(pytester, source, *extra, family="xunit1"):
    pytester.makepyfile(source)
    report = pytester.path / "report.xml"
    result = pytester.runpytest(
        "-p", PLUGIN, "--junitxml", str(report), "-o", f"junit_family={family}", *extra
    )
    return result, (ET.parse(report).getroot() if report.exists() else None)


def _cases(root):
    return {case.get("name"): case for case in root.iter("testcase")}


def _properties(case):
    return {p.get("name"): p.get("value") for p in case.iter("property")}


class TestXmlShape:
    def test_every_case_carries_its_source_location(self, pytester):
        result, root = _run(pytester, DECORATED)
        result.assert_outcomes(passed=2)
        cases = _cases(root)
        for case in cases.values():
            assert case.get("file") == "test_every_case_carries_its_source_location.py"
        # pytest counts lines from 0; the attribute counts from 1 like editors.
        # A decorated function is located at its first decorator.
        assert cases["test_addition"].get("line") == str(ADDITION_LINE)
        assert cases["test_plain"].get("line") == str(PLAIN_LINE)

    def test_the_decorator_writes_properties(self, pytester):
        _, root = _run(pytester, DECORATED)
        assert _properties(_cases(root)["test_addition"]) == {
            "PartiallyVerifies": "REQ_1, REQ_2",
            "TestType": "requirements-based",
            "DerivationTechnique": "requirements-analysis",
            "Owner": "team-a",
        }
        assert _properties(_cases(root)["test_plain"]) == {}

    def test_runtime_metadata_and_location_override(self, pytester):
        result, root = _run(pytester, RUNTIME)
        result.assert_outcomes(passed=2)
        case = _cases(root)["test_driven_by_a_file[a.rst]"]
        assert _properties(case) == {
            "FullyVerifies": "REQ_9",
            "TestType": "interface-test",
        }
        assert case.get("file") == "specs/a.rst"
        assert case.get("line") == "7"

    def test_the_marker_is_registered(self, pytester):
        result, _ = _run(pytester, DECORATED, "--strict-markers")
        result.assert_outcomes(passed=2)

    def test_the_record_xml_attribute_notice_is_silenced(self, pytester):
        # pytest flags record_xml_attribute as experimental once per test; the
        # plugin exists to use it, so that notice must not reach the user.
        result, _ = _run(pytester, DECORATED)
        noisy = [
            line
            for line in result.stdout.lines
            if "record_xml_attribute is an experimental feature" in line
        ]
        assert noisy == []

    def test_xunit2_is_warned_about_at_configure_time(self, pytester):
        result, root = _run(pytester, DECORATED, family="xunit2")
        result.stdout.fnmatch_lines(["*junit_family is 'xunit2'*xunit1*"])
        assert _cases(root)["test_plain"].get("file") is None


class TestHelpers:
    def test_bazel_runfiles_prefix_is_cut(self):
        assert clean_source_path("../_main/pkg/test_x.py") == "pkg/test_x.py"
        assert clean_source_path("pkg/test_x.py") == "pkg/test_x.py"

    def test_empty_values_are_dropped(self):
        assert properties_mapping(fully_verifies=["R"], test_type="") == {
            "FullyVerifies": "R"
        }

    def test_nothing_to_record_is_an_error(self):
        with pytest.raises(ValueError, match="no test properties"):
            properties_mapping(partially_verifies=[])

    def test_the_plugin_does_not_import_sphinx(self):
        script = (
            "import sys;"
            f"import {PLUGIN};"
            "leaked = sorted(m for m in sys.modules"
            " if m == 'sphinx' or m.startswith(('sphinx.', 'sphinx_needs')));"
            "print(','.join(leaked))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True
        )
        assert result.stdout.strip() == ""


class TestPropertyValues:
    """How a keyword's value reaches the XML: declared per property, not guessed."""

    def test_a_bare_string_is_one_requirement_id(self):
        # str is a Sequence[str]; it must not be exploded character by character.
        assert properties_mapping(partially_verifies="REQ_1") == {
            "PartiallyVerifies": "REQ_1"
        }

    def test_a_list_for_a_single_valued_property_is_an_error(self):
        with pytest.raises(TypeError, match="test_type.*single value"):
            properties_mapping(test_type=["a", "b"])

    def test_a_custom_keyword_takes_a_single_value(self):
        assert properties_mapping(Owner="team-a") == {"Owner": "team-a"}

    def test_a_list_under_an_unregistered_keyword_is_an_error(self):
        # Previously written as the Python repr "['REQ_1', 'REQ_2']".
        with pytest.raises(TypeError, match="Satisfies.*register_property"):
            properties_mapping(Satisfies=["REQ_1", "REQ_2"])

    def test_a_registered_keyword_joins_its_list(self, monkeypatch):
        monkeypatch.setattr(pytest_plugin, "PROPERTIES", dict(pytest_plugin.PROPERTIES))
        register_property("satisfies", "Satisfies", multi=True)
        assert properties_mapping(satisfies=["REQ_1", "REQ_2"]) == {
            "Satisfies": "REQ_1, REQ_2"
        }
        assert properties_mapping(satisfies="REQ_1") == {"Satisfies": "REQ_1"}

    def test_the_xml_name_of_a_registered_property_works_as_keyword(self):
        assert properties_mapping(PartiallyVerifies=["REQ_1", "REQ_2"]) == {
            "PartiallyVerifies": "REQ_1, REQ_2"
        }

    def test_numbers_are_written_as_text(self):
        assert properties_mapping(Priority=3) == {"Priority": "3"}

    def test_an_unordered_collection_is_an_error(self):
        # str(set) would be written otherwise, and a set has no stable order.
        with pytest.raises(TypeError, match="partially_verifies"):
            properties_mapping(partially_verifies={"REQ_1", "REQ_2"})


class TestRuntimeMetadata:
    def test_all_empty_metadata_records_nothing(self):
        # A spec file with an empty metadata block must not fail the test.
        recorded = []
        apply_test_metadata(
            record_property=lambda name, value: recorded.append((name, value)),
            metadata={"fully_verifies": [], "test_type": ""},
        )
        assert recorded == []

    def test_the_location_is_applied_without_metadata(self):
        attributes = {}
        apply_test_metadata(
            record_property=lambda name, value: None,
            metadata={},
            record_xml_attribute=attributes.__setitem__,
            file="../_main/specs/a.rst",
            line=7,
        )
        assert attributes == {"file": "specs/a.rst", "line": "7"}


STACKED = """
from sphinxcontrib.test_reports.pytest_plugin import add_test_properties


@add_test_properties(test_type="requirements-based", Owner="team-a")
class TestThing:
    @add_test_properties(partially_verifies=["REQ_1"])
    def test_one(self):
        assert True

    @add_test_properties(partially_verifies=["REQ_2"], Owner="team-b")
    def test_two(self):
        assert True


@add_test_properties(fully_verifies=["REQ_3"])
@add_test_properties(test_type="interface-test")
def test_stacked():
    assert True
"""


class TestMarkerMerge:
    def test_class_and_method_markers_are_merged(self, pytester):
        # A classification on the class and links on each method is the natural
        # way to use the decorator; get_closest_marker kept only the innermost.
        result, root = _run(pytester, STACKED)
        result.assert_outcomes(passed=3)
        cases = _cases(root)
        assert _properties(cases["test_one"]) == {
            "PartiallyVerifies": "REQ_1",
            "TestType": "requirements-based",
            "Owner": "team-a",
        }

    def test_the_innermost_marker_wins_per_key(self, pytester):
        _, root = _run(pytester, STACKED)
        assert _properties(_cases(root)["test_two"])["Owner"] == "team-b"

    def test_stacked_decorators_on_a_function_are_merged(self, pytester):
        _, root = _run(pytester, STACKED)
        assert _properties(_cases(root)["test_stacked"]) == {
            "FullyVerifies": "REQ_3",
            "TestType": "interface-test",
        }
