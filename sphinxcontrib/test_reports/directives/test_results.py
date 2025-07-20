# sphinxcontrib/test_reports/directives/test_results.py

import os
from typing import List, Tuple, Dict, Union, cast
from docutils import nodes
from docutils.parsers.rst import Directive
from sphinxcontrib.test_reports.junitparser import JUnitParser
from sphinx.environment import BuildEnvironment


TestcaseDict = Dict[str, Union[str, int, float]]
TestsuiteDict = Dict[str, Union[str, int, float, List[TestcaseDict], List["TestsuiteDict"]]]


class TestResultsDirective(Directive):
    """
    Directive for showing test results.
    """

    has_content = True
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True

    header: Tuple[str, str, str, str] = ("class", "name", "status", "reason")
    colwidths: Tuple[int, int, int, int] = (1, 1, 1, 2)

    def run(self) -> List[nodes.Element]:
        xml_path = self.arguments[0]

        env = cast(BuildEnvironment, self.state.document.settings.env)
        root_path = cast(str, env.app.config.tr_rootdir)

        if not os.path.isabs(xml_path):
            xml_path = os.path.join(root_path, xml_path)

        parser = JUnitParser(xml_path)
        results = cast(List[TestsuiteDict], parser.parse())

        # Construction idea taken from http://agateau.com/2015/docutils-snippets/

        main_section: List[nodes.Element] = []

        for ts in results:
            section = nodes.section()
            section += nodes.title(text=str(ts.get("name", "unknown")))
            section += nodes.paragraph(
                text="Tests: {tests}, Failures: {failure}, Errors: {error}, Skips: {skips}".format(
                    tests=ts.get("tests", -1),
                    failure=ts.get("failures", -1),
                    error=ts.get("errors", -1),
                    skips=ts.get("skips", -1),
                )
            )
            section += nodes.paragraph(text=f"Time: {ts.get('time', -1)}")

            table = nodes.table()
            section += table

            tgroup = nodes.tgroup(cols=len(self.header))
            table += tgroup
            for colwidth in self.colwidths:
                tgroup += nodes.colspec(colwidth=colwidth)

            thead = nodes.thead()
            tgroup += thead
            thead += self._create_table_row(list(self.header))

            tbody = nodes.tbody()
            tgroup += tbody

            raw_testcases = ts.get("testcases", [])
            if isinstance(raw_testcases, list):
                for testcase in raw_testcases:
                    if isinstance(testcase, dict):
                        typed_testcase = cast(TestcaseDict, testcase)
                        tbody += self._create_testcase_row(typed_testcase)

            main_section.append(section)

        return main_section

    def _create_testcase_row(self, testcase: TestcaseDict) -> nodes.row:
        reason_parts: List[str] = []
        if testcase.get("message") and testcase["message"] != "unknown":
            reason_parts.append(str(testcase["message"]))
        if testcase.get("text"):
            reason_parts.append(str(testcase["text"]))

        row_cells: Tuple[str, str, str, str] = (
            str(testcase.get("classname", "")),
            str(testcase.get("name", "")),
            str(testcase.get("result", "")),
            "\n\n".join(reason_parts),
        )

        result_class = "tr_" + row_cells[2]
        row = nodes.row(classes=cast(List[str], [result_class]))

        for index, cell in enumerate(row_cells):
            entry = nodes.entry(classes=cast(List[str], [result_class, self.header[index]]))
            entry += nodes.paragraph(text=cell, classes=cast(List[str], [result_class]))
            row += entry

        return row

    def _create_table_row(self, row_cells: List[str]) -> nodes.row:
        row = nodes.row()
        for cell in row_cells:
            entry = nodes.entry()
            entry += nodes.paragraph(text=cell)
            row += entry
        return row
