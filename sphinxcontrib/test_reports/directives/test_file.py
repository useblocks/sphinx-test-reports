import hashlib

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx_needs.api import add_need
from sphinx_needs.utils import add_doc

import sphinxcontrib.test_reports.directives.test_suite
from sphinxcontrib.test_reports.directives.test_common import TestCommonDirective
from sphinxcontrib.test_reports.exceptions import TestReportIncompleteConfigurationError

from typing import Dict, List, Optional, Any


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

    def run(self) -> List[object]:
        self.prepare_basic_options()
        results: Optional[List[Dict[str, object]]] = self.load_test_file()

        # Error handling, if file not found
        if results is None:
            main_section: List[object] = []
            content = nodes.error()
            para = nodes.paragraph()
            text_string = f"Test file not found: {self.test_file}"
            text = nodes.Text(text_string)
            para += text
            content.append(para)
            main_section.append(content)
            return main_section

        suites = len(self.results) if self.results is not None else 0
        cases = sum(int(x["tests"]) for x in self.results) if self.results is not None else 0
        passed = sum(x["passed"] for x in self.results) if self.results is not None else 0
        skipped = sum(x["skips"] for x in self.results) if self.results is not None else 0
        errors = sum(x["errors"] for x in self.results) if self.results is not None else 0
        failed = sum(x["failures"] for x in self.results) if self.results is not None else 0

        main_section: List[object] = []
        docname = self.state.document.settings.env.docname
        main_section += add_need(
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
            **self.extra_options,
        )

        if (
            "auto_cases" in self.options.keys()
            and "auto_suites" not in self.options.keys()
        ):
            raise TestReportIncompleteConfigurationError(
                "option auto_cases must be used together with "
                "auto_suites for test-file directives."
            )

        if "auto_suites" in self.options.keys() and self.results is not None:
            for suite in self.results:
                suite_id = self.test_id or ""
                suite_id += (
                    "_"
                    + hashlib.sha1(suite["name"].encode("UTF-8"))
                    .hexdigest()
                    .upper()[: self.app.config.tr_suite_id_length]
                )

                if suite_id not in self.suite_ids:
                    self.suite_ids[suite_id] = suite["name"]
                else:
                    raise Exception(
                        f"Suite ID {suite_id} already exists by {self.suite_ids[suite_id]} ({suite['name']})"
                    )

                options = self.options.copy()
                options["suite"] = suite["name"]
                options["id"] = suite_id

                if "links" not in options:
                    options["links"] = self.test_id or ""
                elif self.test_id and self.test_id not in options["links"]:
                    options["links"] = options["links"] + ";" + self.test_id

                arguments = [suite["name"]]
                suite_directive = (
                    sphinxcontrib.test_reports.directives.test_suite.TestSuiteDirective(
                        self.app.config.tr_suite[0],
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

                main_section += suite_directive.run()

        add_doc(self.env, docname)

        return main_section
