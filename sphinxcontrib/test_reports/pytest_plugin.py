"""pytest plugin: shape the JUnit XML the way this extension reads it.

Enable it with ``-p sphinxcontrib.test_reports.pytest_plugin`` (or in
``addopts``) and write the report with ``--junitxml`` under
``junit_family = xunit1``. Two things then happen to every ``<testcase>``:

* it carries ``file`` and ``line`` attributes -- the source location that the
  directives put into ``tr_source_file_option``/``tr_source_line_option`` and
  that a deterministic case ID is derived from. pytest only writes these under
  ``xunit1``, and only through the ``record_xml_attribute`` fixture; nothing in
  a stock run produces them;
* the metadata given with :func:`add_test_properties` (or, for parameterised
  tests, :func:`apply_test_metadata`) is written as ``<properties>``, which the
  directives turn into need fields (``tr_extra_options``) and link fields
  (``tr_property_link_types``) pointing at the requirements a test verifies.

Ported from the ``score_pytest`` attribute plugin of S-CORE's docs-as-code, so
the XML is shaped identically and tests written against that plugin keep
working when they import from here instead. Two deliberate differences: the
``TestType``/``DerivationTechnique`` vocabularies are documented, not enforced,
and a test does not have to carry a docstring -- both are process rules of that
project, not of this tool.

This module imports pytest and nothing else from the package's Sphinx side; it
is only ever loaded by pytest.
"""

from __future__ import annotations

from typing import Callable, Mapping, Sequence

import pytest

#: Name of the marker :func:`add_test_properties` attaches. Registered in
#: :func:`pytest_configure` so ``--strict-markers`` accepts it.
MARKER = "test_properties"

#: Property names written to the XML, matching S-CORE's metamodel spelling so
#: a ``link_properties = { PartiallyVerifies = "partially_verifies" }`` in
#: ``ubproject.toml`` maps them without translation.
PARTIALLY_VERIFIES = "PartiallyVerifies"
FULLY_VERIFIES = "FullyVerifies"
TEST_TYPE = "TestType"
DERIVATION_TECHNIQUE = "DerivationTechnique"

#: The vocabularies S-CORE uses. Documented, not enforced: a project with a
#: different metamodel is free to write other values.
TEST_TYPES = (
    "fault-injection",
    "interface-test",
    "requirements-based",
    "resource-usage",
)
DERIVATION_TECHNIQUES = (
    "requirements-analysis",
    "design-analysis",
    "boundary-values",
    "equivalence-classes",
    "fuzz-testing",
    "error-guessing",
    "explorative-testing",
)

#: Bazel runs tests from a runfiles tree where the workspace appears as
#: ``_main``; a location such as ``../_main/pkg/test_x.py`` names the source
#: file ``pkg/test_x.py``.
_RUNFILES_MARKER = "_main/"

Recorder = Callable[[str, str], None]


def properties_mapping(
    *,
    partially_verifies: Sequence[str] | None = None,
    fully_verifies: Sequence[str] | None = None,
    test_type: str | None = None,
    derivation_technique: str | None = None,
    **properties: str,
) -> dict[str, str]:
    """The property mapping that ends up in the XML, empty values dropped.

    Single source of truth for the decorator and the runtime helper. Lists are
    joined with ``", "``, which is what ``tr_property_link_types``
    splits on again.
    """
    mapping = {
        PARTIALLY_VERIFIES: ", ".join(partially_verifies or ()),
        FULLY_VERIFIES: ", ".join(fully_verifies or ()),
        TEST_TYPE: test_type or "",
        DERIVATION_TECHNIQUE: derivation_technique or "",
        **properties,
    }
    cleaned = {name: value for name, value in mapping.items() if value}
    if not cleaned:
        raise ValueError(
            "no test properties given: at least one of partially_verifies, "
            "fully_verifies, test_type, derivation_technique or a custom "
            "property is needed"
        )
    return cleaned


def add_test_properties(
    *,
    partially_verifies: Sequence[str] | None = None,
    fully_verifies: Sequence[str] | None = None,
    test_type: str | None = None,
    derivation_technique: str | None = None,
    **properties: str,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Decorator recording requirement links and classification for a test.

    ::

        @add_test_properties(
            partially_verifies=["REQ_1", "REQ_2"],
            test_type="requirements-based",
            derivation_technique="requirements-analysis",
        )
        def test_addition():
            ...

    Extra keyword arguments become properties under their own names, for
    metamodels with fields this plugin does not know.
    """
    mapping = properties_mapping(
        partially_verifies=partially_verifies,
        fully_verifies=fully_verifies,
        test_type=test_type,
        derivation_technique=derivation_technique,
        **properties,
    )
    marker = getattr(pytest.mark, MARKER)

    def decorator(function: Callable[..., object]) -> Callable[..., object]:
        decorated: Callable[..., object] = marker(mapping)(function)
        return decorated

    return decorator


def apply_test_metadata(
    *,
    record_property: Recorder,
    metadata: Mapping[str, Sequence[str] | str | None],
    record_xml_attribute: Recorder | None = None,
    file: str | None = None,
    line: int | None = None,
) -> None:
    """Runtime equivalent of :func:`add_test_properties`.

    For tests whose metadata is only known inside the test body -- typically a
    parameterised test driven by files that carry their own metadata. Call it
    *early*, before any assertion, so the properties are attached even when the
    test then fails. *metadata* uses the decorator's argument names as keys.

    With *record_xml_attribute*, *file* and *line* override the location the
    plugin's fixture recorded, so a case can point at the file that drove it
    rather than at the test function.
    """
    if not metadata:
        return
    properties = {
        name: str(value)
        for name, value in metadata.items()
        if name
        not in (
            "partially_verifies",
            "fully_verifies",
            "test_type",
            "derivation_technique",
        )
        and value
    }
    mapping = properties_mapping(
        partially_verifies=_as_list(metadata.get("partially_verifies")),
        fully_verifies=_as_list(metadata.get("fully_verifies")),
        test_type=_as_str(metadata.get("test_type")),
        derivation_technique=_as_str(metadata.get("derivation_technique")),
        **properties,
    )
    for name, value in mapping.items():
        record_property(name, value)

    if record_xml_attribute is not None:
        if file is not None:
            record_xml_attribute("file", clean_source_path(file))
        if line is not None:
            record_xml_attribute("line", str(line))


def _as_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [str(item) for item in value]
    return [str(value)]


def _as_str(value: object) -> str | None:
    return None if value is None else str(value)


def clean_source_path(path: str) -> str:
    """The workspace-relative source path of a test.

    pytest reports locations relative to its rootdir already; under Bazel the
    rootdir sits inside a runfiles tree, so the path starts with ``../_main/``
    and has to be cut down to the workspace path.
    """
    if _RUNFILES_MARKER in path:
        return path.rsplit(_RUNFILES_MARKER, 1)[-1]
    return path


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        f"{MARKER}(properties): properties written to the JUnit XML of the "
        "test; attached by sphinxcontrib.test_reports.pytest_plugin.add_test_properties",
    )
    # record_xml_attribute is marked experimental and says so once per test;
    # this plugin exists to use it, so the notice is noise here.
    config.addinivalue_line(
        "filterwarnings",
        "ignore:record_xml_attribute is an experimental feature:"
        "pytest.PytestExperimentalApiWarning",
    )
    xmlpath: object = config.option.xmlpath
    family: object = config.getini("junit_family")
    if xmlpath and family != "xunit1":
        config.issue_config_time_warning(
            pytest.PytestConfigWarning(
                "sphinxcontrib.test_reports.pytest_plugin: junit_family is "
                f"{family!r}, but pytest writes the file/line attributes of a "
                "<testcase> only under 'xunit1'. Set junit_family = xunit1, or the "
                "test cases will have no source location."
            ),
            stacklevel=2,
        )


@pytest.fixture(autouse=True)
def _test_reports_xml_shape(
    request: pytest.FixtureRequest,
    record_property: Recorder,
    record_xml_attribute: Recorder,
) -> None:
    """Record the source location and the marker's properties for every test.

    Runs at setup, so a test that fails still carries both. The location is
    the test function's -- for a decorated function, the line of its first
    decorator, which is where pytest points too; :func:`apply_test_metadata`
    may override it later.
    """
    node: pytest.Item = request.node
    location: tuple[str, int | None, str] = node.location
    path, line_number, _domain = location
    record_xml_attribute("file", clean_source_path(path))
    if line_number is not None:
        # pytest's line numbers are 0-based; editors and the report count
        # from 1.
        record_xml_attribute("line", str(line_number + 1))

    marker: pytest.Mark | None = node.get_closest_marker(MARKER)
    if marker is None:
        return
    arguments: tuple[object, ...] = marker.args
    if not arguments or not isinstance(arguments[0], Mapping):
        raise pytest.UsageError(
            f"marker '{MARKER}' on {node.name} carries no property mapping; "
            "attach it with add_test_properties(...)"
        )
    properties: Mapping[object, object] = arguments[0]
    for name, value in properties.items():
        record_property(str(name), str(value))
