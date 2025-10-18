from __future__ import annotations

import hashlib
from typing import (
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    TypedDict,
    cast,
    runtime_checkable,
)

from docutils import nodes
from docutils.nodes import Node
from docutils.parsers.rst import directives
from sphinx_needs.api import add_need
from sphinx_needs.utils import add_doc

import sphinxcontrib.test_reports.directives.test_case as test_case_mod
from sphinxcontrib.test_reports.directives.test_common import TestCommonDirective
from sphinxcontrib.test_reports.exceptions import TestReportInvalidOptionError

# --------- TypedDicts for parser results ------------


class TestCaseDict(TypedDict):
    name: str
    classname: str


class TestSuiteDict(TypedDict, total=False):
    name: str
    tests: int
    passed: int
    skips: int
    errors: int
    failures: int
    testcases: List[TestCaseDict]
    testsuite_nested: List["TestSuiteDict"]
    testsuites: List["TestSuiteDict"]


# --------- Protocol for required config fields ---------


@runtime_checkable
class _SuiteConfigProtocol(Protocol):
    tr_suite_id_length: int
    tr_case_id_length: int
    tr_suite: Tuple[str, ...]
    tr_case: Tuple[str, ...]


# --------- Node class ---------


class TestSuite(nodes.General, nodes.Element):
    pass


class TestSuiteDirective(TestCommonDirective):
    """
    Directive for rendering test suites.
    """

    has_content: ClassVar[bool] = True
    required_arguments: ClassVar[int] = 1
    optional_arguments: ClassVar[int] = 0
    option_spec: ClassVar[Dict[str, Callable[[str], object]]] = {
        "id": directives.unchanged_required,
        "status": directives.unchanged_required,
        "tags": directives.unchanged_required,
        "links": directives.unchanged_required,
        "collapse": directives.unchanged_required,
        "file": directives.unchanged_required,
        "suite": directives.unchanged_required,
    }
    final_argument_whitespace: ClassVar[bool] = True

    _nested_flag: ClassVar[bool] = False
    _nested_index: ClassVar[int] = -1

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.case_ids: List[str] = []

    def _ensure_results_list(self) -> List[TestSuiteDict]:
        """Ensure that self.results is a list of TestSuiteDict."""
        if self.results is None:
            self.load_test_file()
        results_list = cast(List[Dict[str, object]], self.results)
        return cast(List[TestSuiteDict], results_list)

    def _get_cfg_suite(self) -> _SuiteConfigProtocol:
        """Cast app config to the extended Suite Protocol."""
        return cast(_SuiteConfigProtocol, self.app.config)

    def run(self, nested: bool = False, count: int = -1) -> List[Node]:
        self.prepare_basic_options()
        results: List[TestSuiteDict] = self._ensure_results_list()

        # If nested, access the first element's nested suites
        if nested:
            if not results:
                raise TestReportInvalidOptionError(
                    "No suites available for nested access."
                )
            results = results[0].get("testsuite_nested", [])

        # Get target suite by name from options
        suite_name_obj = self.options.get("suite")
        suite_name = (
            str(suite_name_obj) if isinstance(suite_name_obj, (str, bytes)) else None
        )
        if not suite_name:
            raise TestReportInvalidOptionError("Suite not given!")

        suite: Optional[TestSuiteDict] = None
        for suite_obj in results:
            if suite_obj.get("name") == suite_name:
                suite = suite_obj
                break

        # If nested, select by index if not found by name
        if suite is None and nested and 0 <= count < len(results):
            suite = results[count]

        if suite is None:
            raise TestReportInvalidOptionError(
                f"Suite {suite_name} not found in test file {self.test_file}"
            )

        # Get counts safely with default 0
        cases_count = int(suite.get("tests", 0))
        passed = int(suite.get("passed", 0))
        skipped = int(suite.get("skips", 0))
        errors = int(suite.get("errors", 0))
        failed = int(suite.get("failures", 0))

        main_section: List[Node] = []
        docname = cast(str, self.state.document.settings.env.docname)

        # Create the need node for this suite
        need_nodes = cast(
            List[Node],
            add_need(
                self.app,
                self.state,
                docname,
                self.lineno,
                need_type=self.need_type,
                title=self.test_name,
                id=self.test_id,
                content=self.test_content,
                links=self.test_links,
                tags=self.test_tags,
                status=self.test_status,
                collapse=self.collapse,
                file=self.test_file_given,
                suite=suite.get("name", ""),
                cases=cases_count,
                passed=passed,
                skipped=skipped,
                failed=failed,
                errors=errors,
                **(self.extra_options or {}),
            ),
        )
        main_section += need_nodes

        # --- Handle nested suites if current suite has no testcases ---
        testcases_list = suite.get("testcases", [])
        if not testcases_list:
            nested_suites = suite.get("testsuite_nested", [])
            if isinstance(nested_suites, list) and nested_suites:
                access_count = 0
                for nested_suite in nested_suites:
                    cfg = self._get_cfg_suite()
                    base_id = self.test_id or ""
                    derived = (
                        base_id
                        + "_"
                        + hashlib.sha1(nested_suite.get("name", "").encode("UTF-8"))
                        .hexdigest()
                        .upper()[: cfg.tr_suite_id_length]
                    )

                    nested_options: Dict[str, object] = dict(self.options)
                    nested_options["suite"] = nested_suite.get("name", "")
                    nested_options["id"] = derived

                    # Maintain links
                    if "links" not in nested_options:
                        nested_options["links"] = self.test_id or ""
                    elif isinstance(nested_options["links"], str) and self.test_id:
                        if self.test_id not in nested_options["links"]:
                            nested_options["links"] += ";" + self.test_id

                    arguments = [nested_suite.get("name", "")]
                    cfg_suite_tuple = self._get_cfg_suite().tr_suite
                    suite_directive = TestSuiteDirective(
                        cfg_suite_tuple[0],
                        arguments,
                        nested_options,
                        "",
                        self.lineno,
                        self.content_offset,
                        self.block_text,
                        self.state,
                        self.state_machine,
                    )

                    # Run nested suite directive
                    main_section += cast(
                        List[Node], suite_directive.run(nested=True, count=access_count)
                    )
                    access_count += 1

        # --- Automatically create testcase nodes if configured ---
        if (
            "auto_cases" in self.options.keys()
            and isinstance(testcases_list, list)
            and testcases_list
        ):
            case_count = 0
            for case in testcases_list:
                cfg = self._get_cfg_suite()
                base_id = self.test_id or ""
                compound = (
                    case.get("classname", "") + "\x00" + case.get("name", "")
                ).encode("UTF-8")
                case_id = (
                    base_id
                    + "_"
                    + hashlib.sha1(compound)
                    .hexdigest()
                    .upper()[: cfg.tr_case_id_length]
                )

                if case_id in self.case_ids:
                    raise Exception(f"Case ID exists: {case_id}")
                self.case_ids.append(case_id)

                case_options: Dict[str, object] = dict(self.options)
                case_options["case"] = case.get("name", "")
                case_options["classname"] = case.get("classname", "")
                case_options["id"] = case_id

                if "links" not in case_options:
                    case_options["links"] = self.test_id or ""
                elif isinstance(case_options["links"], str) and self.test_id:
                    if self.test_id not in case_options["links"]:
                        case_options["links"] += ";" + self.test_id

                arguments = [case.get("name", "")]
                cfg_case_tuple = self._get_cfg_suite().tr_case
                case_directive = test_case_mod.TestCaseDirective(
                    cfg_case_tuple[0],
                    arguments,
                    case_options,
                    "",
                    self.lineno,
                    self.content_offset,
                    self.block_text,
                    self.state,
                    self.state_machine,
                )

                is_nested = (
                    "testsuite_nested" in suite
                    and isinstance(suite.get("testsuite_nested"), list)
                    and len(cast(List[object], suite.get("testsuite_nested"))) > 0
                ) or nested

                main_section += cast(
                    List[Node], case_directive.run(is_nested, count, case_count)
                )

                if is_nested:
                    case_count += 1

        # Register document
        add_doc(self.env, docname)

        return main_section
