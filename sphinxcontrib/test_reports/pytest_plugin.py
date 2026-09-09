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

import re
import warnings
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import pytest

#: Name of the marker :func:`add_test_properties` attaches. Registered in
#: :func:`pytest_configure` so ``--strict-markers`` accepts it.
MARKER = "test_properties"

#: Property names written to the XML, matching S-CORE's metamodel spelling so
#: a ``property_link_types = { PartiallyVerifies = "partially_verifies" }`` in
#: ``ubproject.toml`` maps them without translation.
PARTIALLY_VERIFIES = "PartiallyVerifies"
FULLY_VERIFIES = "FullyVerifies"
TEST_TYPE = "TestType"
DERIVATION_TECHNIQUE = "DerivationTechnique"

#: The vocabularies of S-CORE's verification concept ("Verification Methods"
#: in its process description): the identifiers of the verification methods,
#: for ``TestType``, and of the derivation techniques, for
#: ``DerivationTechnique``. Documented, not enforced -- S-CORE's own metamodel
#: accepts any string for both fields, and a project with a different metamodel
#: is free to write other values.
TEST_TYPES = (
    "control-flow-analysis",
    "data-flow-analysis",
    "fault-injection",
    "inspection",
    "interface-test",
    "requirements-based",
    "resource-usage",
    "static-code-analysis",
    "structural-statement-coverage",
    "structural-branch-coverage",
    "walkthrough",
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

#: Bazel runs a test from a runfiles tree in which the workspace is the
#: directory ``_main``: ``../_main/pkg/test_x.py`` names ``pkg/test_x.py``. Only
#: a whole path component counts -- ``app_main/`` is somebody's directory -- and
#: the last one wins, since under bzlmod the execroot's workspace directory is
#: ``_main`` as well.
_RUNFILES_PREFIX = re.compile(r"^(?:.*[\\/])?_main[\\/]")

Recorder = Callable[[str, str], None]

#: What a property keyword accepts: one value, or -- for a multi-valued
#: property -- a sequence of values. ``None`` and empty values are not written.
Value = str | Sequence[str] | None


@dataclass(frozen=True)
class Property:
    """How one keyword of :func:`add_test_properties` reaches the XML."""

    #: The ``<property name="...">`` written.
    name: str
    #: Multi-valued: a sequence of values is joined with ``", "``, which
    #: ``tr_property_link_types`` splits again on the build side; a bare string
    #: counts as one value. A single-valued property takes one value, and a
    #: sequence is an error rather than a silent join.
    multi: bool = False


#: Keyword -> how it is written. S-CORE's four are pre-registered; a project
#: adds its own with :func:`register_property`. A keyword not found here is
#: written under its own name and takes a single value only.
PROPERTIES: dict[str, Property] = {
    "partially_verifies": Property(PARTIALLY_VERIFIES, multi=True),
    "fully_verifies": Property(FULLY_VERIFIES, multi=True),
    "test_type": Property(TEST_TYPE),
    "derivation_technique": Property(DERIVATION_TECHNIQUE),
}


def register_property(
    keyword: str, name: str | None = None, *, multi: bool = False
) -> Property:
    """Teach :func:`add_test_properties` and :func:`apply_test_metadata` *keyword*.

    *name* is the ``<property>`` name written to the XML (default: the keyword
    itself); a *multi*-valued property takes a sequence of values and writes
    them ``", "``-joined, the shape ``tr_property_link_types`` reads. Call it
    once, before the tests are collected -- a ``conftest.py`` is the place::

        register_property("satisfies", "Satisfies", multi=True)

    lets a test write ``@add_test_properties(satisfies=["REQ_1", "REQ_2"])``.
    """
    registered = Property(name or keyword, multi=multi)
    PROPERTIES[keyword] = registered
    return registered


def _lookup(keyword: str) -> Property | None:
    """The registered property for *keyword*, also when given by its XML name."""
    registered = PROPERTIES.get(keyword)
    if registered is not None:
        return registered
    return next((p for p in PROPERTIES.values() if p.name == keyword), None)


def _serialise(keyword: str, registered: Property | None, value: object) -> str | None:
    """The text written for *value*, or ``None`` when there is nothing to write."""
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        return str(value) or None
    if isinstance(value, Sequence):
        if registered is None:
            raise TypeError(
                f"{keyword!r} is not a registered property and takes a single "
                f"value; register_property({keyword!r}, multi=True) lets it "
                "write a list"
            )
        if not registered.multi:
            raise TypeError(f"{keyword!r} takes a single value, not a sequence")
        return ", ".join(str(item) for item in value if item not in (None, "")) or None
    raise TypeError(
        f"{keyword!r} takes a string"
        + (" or a list of strings" if registered and registered.multi else "")
        + f", not {type(value).__name__}"
    )


def _normalise(properties: Mapping[str, object]) -> dict[str, str]:
    """The XML properties for keyword/value pairs; empty values dropped."""
    written: dict[str, str] = {}
    for keyword, value in properties.items():
        registered = _lookup(keyword)
        text = _serialise(keyword, registered, value)
        if text is not None:
            written[registered.name if registered else keyword] = text
    return written


def properties_mapping(
    *,
    partially_verifies: Value = None,
    fully_verifies: Value = None,
    test_type: str | None = None,
    derivation_technique: str | None = None,
    **properties: Value,
) -> dict[str, str]:
    """The property mapping that ends up in the XML, empty values dropped.

    Single source of truth for the decorator and the runtime helper. How a
    value is written is decided by :data:`PROPERTIES`, not by the keyword it
    arrived under: the four named parameters are sugar over the same mechanism
    that serves every registered keyword.
    """
    cleaned = _normalise(
        {
            "partially_verifies": partially_verifies,
            "fully_verifies": fully_verifies,
            "test_type": test_type,
            "derivation_technique": derivation_technique,
            **properties,
        }
    )
    if not cleaned:
        raise ValueError(
            "no test properties given: at least one of partially_verifies, "
            "fully_verifies, test_type, derivation_technique or a registered "
            "property is needed"
        )
    return cleaned


def add_test_properties(
    *,
    partially_verifies: Value = None,
    fully_verifies: Value = None,
    test_type: str | None = None,
    derivation_technique: str | None = None,
    **properties: Value,
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

    Further keyword arguments are written under their own names with a single
    value each; :func:`register_property` gives a project's own link fields the
    list handling of ``partially_verifies``.
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
    metadata: Mapping[str, object],
    record_xml_attribute: Recorder | None = None,
    file: str | None = None,
    line: int | None = None,
) -> None:
    """Runtime equivalent of :func:`add_test_properties`.

    For tests whose metadata is only known inside the test body -- typically a
    parameterised test driven by files that carry their own metadata. Call it
    *early*, before any assertion, so the properties are attached even when the
    test then fails. *metadata* uses the decorator's argument names as keys;
    metadata without a value -- absent, or with nothing but empty entries --
    writes no properties and is not an error.

    With *record_xml_attribute*, *file* and *line* override the location the
    plugin's fixture recorded, so a case can point at the file that drove it
    rather than at the test function.
    """
    for name, value in _normalise(metadata).items():
        record_property(name, value)

    if record_xml_attribute is not None:
        if file is not None:
            record_xml_attribute("file", clean_source_path(file))
        if line is not None:
            record_xml_attribute("line", str(line))


def clean_source_path(path: str) -> str:
    """The workspace-relative source path of a test.

    pytest reports locations relative to its rootdir already; under Bazel the
    rootdir sits inside a runfiles tree, so the path leads through ``_main``,
    the workspace directory of that tree -- as does an absolute path handed to
    :func:`apply_test_metadata`. Everything up to and including the last
    ``_main/`` component is cut.
    """
    return _RUNFILES_PREFIX.sub("", path, count=1)


class TestReportsConfigWarning(pytest.PytestWarning):
    """A run configured such that the plugin cannot write the full XML shape.

    Issued once at start-up. Where the project turns warnings into errors
    (``filterwarnings = error``, ``-W error``) it becomes a clean usage error
    rather than a traceback;
    ``ignore::sphinxcontrib.test_reports.pytest_plugin.TestReportsConfigWarning``
    silences it.
    """


def _report_family(config: pytest.Config) -> str | None:
    """The ``junit_family`` of the report this run writes, ``None`` without one.

    ``legacy`` is pytest's alias of ``xunit1``. The option does not exist under
    ``-p no:junitxml``.
    """
    if not getattr(config.option, "xmlpath", None):
        return None
    family = str(config.getini("junit_family"))
    return "xunit1" if family == "legacy" else family


def _notify(config: pytest.Config, message: str) -> None:
    """Issue *message* as :class:`TestReportsConfigWarning` at configure time."""
    warning = TestReportsConfigWarning(
        f"sphinxcontrib.test_reports.pytest_plugin: {message}"
    )
    try:
        config.issue_config_time_warning(warning, stacklevel=3)
    except TestReportsConfigWarning as error:
        # The project's filters make warnings errors; raised out of
        # pytest_configure this would be an INTERNALERROR traceback.
        raise pytest.UsageError(str(error)) from None


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        f"{MARKER}(properties): properties written to the JUnit XML of the "
        "test; attached by sphinxcontrib.test_reports.pytest_plugin.add_test_properties",
    )
    family = _report_family(config)
    if family is None:
        return
    if family != "xunit1":
        _notify(
            config,
            f"junit_family is {family!r}, but pytest writes the file/line "
            "attributes of a <testcase> only under 'xunit1'. Set junit_family = "
            "xunit1, or the test cases will have no source location.",
        )
    if getattr(config.option, "dist", "no") != "no" and not hasattr(
        config, "workerinput"
    ):
        _notify(
            config,
            "pytest-xdist runs the tests on workers, where record_xml_attribute "
            "is a no-op: the test cases will carry pytest's stock file/line "
            "(counted from 0, runfiles prefix intact) instead of the plugin's. "
            "Write the report without -n.",
        )


@pytest.fixture(autouse=True)
def _test_reports_xml_shape(request: pytest.FixtureRequest) -> None:
    """Record the source location and the markers' properties for every test.

    Runs at setup, so a test that fails still carries both. The location is
    the test function's -- for a decorated function, the line of its first
    decorator, which is where pytest points too; :func:`apply_test_metadata`
    may override it later.
    """
    node: pytest.Item = request.node
    if _report_family(request.config) == "xunit1":
        # record_xml_attribute announces itself as experimental once per test;
        # this plugin exists to use it, so the notice is dropped here, in
        # process, where no warning policy of the project turns it into an
        # error. Under any other family pytest would drop the attributes again
        # and warn per test; the start-up notice covers that once.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", pytest.PytestExperimentalApiWarning)
            record_xml_attribute: Recorder = request.getfixturevalue(
                "record_xml_attribute"
            )
        path, line_number, _domain = node.location
        record_xml_attribute("file", clean_source_path(path))
        if line_number is not None:
            # pytest's line numbers are 0-based; editors and the report count
            # from 1.
            record_xml_attribute("line", str(line_number + 1))

    # What the record_property fixture does -- but that fixture belongs to the
    # junitxml plugin (gone under -p no:junitxml) and warns per test under
    # xunit2, which the start-up notice already covers.
    node.user_properties.extend(_marked_properties(node).items())


def _marked_properties(node: pytest.Item) -> dict[str, str]:
    """The properties of every ``test_properties`` marker on *node*, merged.

    A marker on the class or the module counts as much as one on the function;
    where two set the same property, the one closest to the function wins.
    """
    merged: dict[str, str] = {}
    for marker in node.iter_markers(MARKER):  # closest first
        arguments: tuple[object, ...] = marker.args
        if not arguments or not isinstance(arguments[0], Mapping):
            raise pytest.UsageError(
                f"marker '{MARKER}' on {node.name} carries no property mapping; "
                "attach it with add_test_properties(...)"
            )
        properties: Mapping[object, object] = arguments[0]
        for name, value in properties.items():
            merged.setdefault(str(name), str(value))
    return merged
