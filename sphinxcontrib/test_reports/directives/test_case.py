from docutils import nodes
from docutils.parsers.rst import directives
from sphinx_needs.api import add_need
from sphinx_needs.utils import add_doc

from sphinxcontrib.test_reports.config import DEFAULT_OPTIONS
from sphinxcontrib.test_reports.directives.test_common import TestCommonDirective
from sphinxcontrib.test_reports.exceptions import TestReportInvalidOptionError

from typing import Dict, List, Optional, Match, Tuple, cast


class TestCase(nodes.General, nodes.Element):
    pass


class TestCaseDirective(TestCommonDirective):
    """
    Directive for showing test suites.
    """

    has_content = True
    required_arguments = 1
    optional_arguments = 0
    option_spec = {
        "id": directives.unchanged_required,
        "status": directives.unchanged_required,
        "tags": directives.unchanged_required,
        "links": directives.unchanged_required,
        "collapse": directives.unchanged_required,
        "file": directives.unchanged_required,
        "suite": directives.unchanged_required,
        "case": directives.unchanged_required,
        "classname": directives.unchanged_required,
    }

    final_argument_whitespace = True

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)

    def run(self, nested: bool = False, suite_count: int = -1, case_count: int = -1) -> List[nodes.Element]:
        self.prepare_basic_options()
        results = self.load_test_file()

        suite_name = cast(Optional[str], self.options.get("suite"))
        if suite_name is None:
            raise TestReportInvalidOptionError("Suite not given!")

        case_full_name = cast(Optional[str], self.options.get("case"))
        class_name = cast(Optional[str], self.options.get("classname"))
        if case_full_name is None and class_name is None:
            raise TestReportInvalidOptionError("Case or classname not given!")

        # Typing aliases
        TestsuiteDict = Dict[str, object]
        TestcaseDict = Dict[str, object]

        # Gather candidate suites
        candidate_suites: List[TestsuiteDict] = []
        if results is not None:
            candidate_suites = cast(List[TestsuiteDict], results)

        # Handle nested selection if requested
        selected_suite: Optional[TestsuiteDict] = None
        if nested and suite_count >= 0 and candidate_suites:
            root_suite = candidate_suites[0]
            nested_suites = cast(List[TestsuiteDict], root_suite.get("testsuites", []))
            if 0 <= suite_count < len(nested_suites):
                selected_suite = nested_suites[suite_count]

        # If not nested, search suite by name
        if selected_suite is None:
            for suite_obj in candidate_suites:
                if str(suite_obj.get("name", "")) == suite_name:
                    selected_suite = suite_obj
                    break

        if selected_suite is None:
            raise TestReportInvalidOptionError(
                f"Suite {suite_name} not found in test file {self.test_file}"
            )

        # Select testcase
        testcases = cast(List[TestcaseDict], selected_suite.get("testcases", []))
        selected_case: Optional[TestcaseDict] = None
        for case_obj in testcases:
            name = str(case_obj.get("name", ""))
            classname_val = str(case_obj.get("classname", ""))
            if name == (case_full_name or "") and class_name is None:
                selected_case = case_obj
                break
            elif (classname_val == (class_name or "") and case_full_name is None) or (
                name == (case_full_name or "") and classname_val == (class_name or "")
            ):
                selected_case = case_obj
                break

        if selected_case is None and nested and case_count >= 0 and 0 <= case_count < len(testcases):
            selected_case = testcases[case_count]

        if selected_case is None and nested and testcases:
            selected_case = testcases[0]

        if selected_case is None:
            raise TestReportInvalidOptionError(
                f"Case {case_full_name} with classname {class_name} not found in test file {self.test_file} "
                f"and testsuite {suite_name}"
            )

        result = str(selected_case.get("result", ""))
        content = self.test_content or ""
        if selected_case.get("text") is not None and isinstance(selected_case.get("text"), str) and len(cast(str, selected_case.get("text"))) > 0:
            content += """

**Text**::

   {}

""".format("\n   ".join([x.lstrip() for x in cast(str, selected_case.get("text", "")).split("\n")]))

        if selected_case.get("message") is not None and isinstance(selected_case.get("message"), str) and len(cast(str, selected_case.get("message"))) > 0:
            content += """

**Message**::

   {}

""".format("\n   ".join([x.lstrip() for x in cast(str, selected_case.get("message", "")).split("\n")]))

        if selected_case.get("system-out") is not None and isinstance(selected_case.get("system-out"), str) and len(cast(str, selected_case.get("system-out"))) > 0:
            content += """

**System-out**::

   {}

""".format("\n   ".join([x.lstrip() for x in cast(str, selected_case.get("system-out", "")).split("\n")]))

        time = float(selected_case.get("time", 0.0))
        style = "tr_" + str(selected_case.get("result", ""))

        import re

        groups: Optional[Match[str]] = re.match(r"^(?P<name>[^\[]+)($|\[(?P<param>.*)?\])", str(selected_case.get("name", "")))
        if groups is not None:
            case_name = groups["name"]
            case_parameter = groups["param"]
        else:
            case_name = case_full_name
            case_parameter = ""

        if case_parameter is None:
            case_parameter = ""

        # Set extra data, which is not part of the Sphinx-Test-Reports default options
        for key, value in selected_case.items():
            if key == "id" and value not in ["", None]:
                self.test_id = str(value)
            elif key == "status" and value not in ["", None]:
                self.test_status = str(value)
            elif key == "tags":
                self.test_tags = ",".join([self.test_tags or "", str(value)])
            elif key not in DEFAULT_OPTIONS and value not in ["", None]:
                # May overwrite globally set values
                if self.extra_options is not None:
                    self.extra_options[key] = str(value)

        docname = cast(str, self.state.document.settings.env.docname)

        main_section: List[nodes.Element] = []
        # Merge all options including extra ones
        main_section += cast(List[nodes.Element], add_need(
            self.app,
            self.state,
            docname,
            self.lineno,
            need_type=self.need_type,
            title=self.test_name,
            id=self.test_id,
            content=content,
            links=self.test_links,
            tags=self.test_tags,
            status=self.test_status,
            collapse=self.collapse,
            file=self.test_file_given,
            suite=str(selected_suite.get("name", "")),
            case=case_full_name,
            case_name=case_name,
            case_parameter=case_parameter,
            classname=class_name,
            result=result,
            time=time,
            style=style,
            **(self.extra_options or {}),
        ))

        add_doc(self.env, docname)
        return main_section
