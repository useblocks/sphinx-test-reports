import hashlib
from typing import Dict, List, Optional, cast

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx_needs.api import add_need
from sphinx_needs.utils import add_doc

import sphinxcontrib.test_reports.directives.test_suite
from sphinxcontrib.test_reports.directives.test_common import TestCommonDirective
from sphinxcontrib.test_reports.exceptions import TestReportIncompleteConfigurationError


class TestFile(nodes.General, nodes.Element):
    pass


class TestFileDirective(TestCommonDirective):
    """
    Directive for showing test results.
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
        "auto_suites": directives.flag,
        "auto_cases": directives.flag,
    }

    final_argument_whitespace = True

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.suite_ids: Dict[str, str] = {}

    def run(self) -> List[nodes.Element]:
        self.prepare_basic_options()
        results: Optional[List[Dict[str, object]]] = self.load_test_file()

        # Error handling, if file not found
        if results is None:
            main_section: List[nodes.Element] = []
            content = nodes.error()
            para = nodes.paragraph()
            text_string = f"Test file not found: {self.test_file}"
            text = nodes.Text(text_string)
            para += text
            content.append(para)
            main_section.append(content)
            return main_section

        def as_int(val: object) -> int:
            if isinstance(val, bool):
                return int(val)
            if isinstance(val, int):
                return val
            if isinstance(val, float):
                return int(val)
            if isinstance(val, str):
                try:
                    return int(val)
                except ValueError:
                    return 0
            return 0

        results_list = cast(List[Dict[str, object]], results)
        suites = len(results_list)
        cases = sum(as_int(x.get("tests", 0)) for x in results_list)
        passed = sum(as_int(x.get("passed", 0)) for x in results_list)
        skipped = sum(as_int(x.get("skips", 0)) for x in results_list)
        errors = sum(as_int(x.get("errors", 0)) for x in results_list)
        failed = sum(as_int(x.get("failures", 0)) for x in results_list)

        main_section = []  # type: List[nodes.Element]
        docname = cast(str, self.state.document.settings.env.docname)
        main_section += cast(
            List[nodes.Element],
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
                suites=suites,
                cases=cases,
                passed=passed,
                skipped=skipped,
                failed=failed,
                errors=errors,
                **(self.extra_options or {}),
            ),
        )

        if (
            "auto_cases" in self.options.keys()
            and "auto_suites" not in self.options.keys()
        ):
            raise TestReportIncompleteConfigurationError(
                "option auto_cases must be used together with "
                "auto_suites for test-file directives."
            )

        if "auto_suites" in self.options.keys() and results_list is not None:
            for suite in results_list:
                suite_name = str(suite.get("name", ""))
                suite_id = self.test_id or ""
                suite_id += (
                    "_"
                    + hashlib.sha1(suite_name.encode("UTF-8"))
                    .hexdigest()
                    .upper()[: cast(int, self.app.config.tr_suite_id_length)]
                )

                if suite_id not in self.suite_ids:
                    self.suite_ids[suite_id] = suite_name
                else:
                    raise Exception(
                        f"Suite ID {suite_id} already exists by {self.suite_ids[suite_id]} ({suite_name})"
                    )

                options = self.options.copy()
                options["suite"] = suite_name
                options["id"] = suite_id

                if "links" not in options:
                    options["links"] = self.test_id or ""
                elif self.test_id and self.test_id not in options["links"]:
                    options["links"] = options["links"] + ";" + self.test_id

                arguments = [suite_name]
                suite_directive = (
                    sphinxcontrib.test_reports.directives.test_suite.TestSuiteDirective(
                        cast(List[str], self.app.config.tr_suite)[0],
                        arguments,
                        options,
                        "",
                        self.lineno,  # no content
                        self.content_offset,
                        self.block_text,
                        self.state,
                        self.state_machine,
                    )
                )

                main_section += cast(List[nodes.Element], suite_directive.run())

        add_doc(self.env, docname)

        return main_section
