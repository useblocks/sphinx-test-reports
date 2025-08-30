# fmt: off
import pathlib

from docutils import nodes
from docutils.parsers.rst import directives
from typing import List, Dict, Optional, Protocol, cast

from sphinxcontrib.test_reports.directives.test_common import TestCommonDirective
from sphinxcontrib.test_reports.exceptions import InvalidConfigurationError

# fmt: on


class TestReport(nodes.General, nodes.Element):
    pass


class TestReportDirective(TestCommonDirective):
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
    }

    final_argument_whitespace = True

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)

    class _AppConfigTR(Protocol):
        tr_report_template: str
        tr_import_encoding: str
        tr_file: List[str]
        tr_suite: List[str]
        tr_case: List[str]

    def run(self) -> List[nodes.Element]:
        self.prepare_basic_options()
        self.load_test_file()

        # if user provides a custom template, use it
        cfg = cast(TestReportDirective._AppConfigTR, self.app.config)
        tr_template = pathlib.Path(cfg.tr_report_template)

        if tr_template.is_absolute():
            template_path = tr_template
        else:
            app_confdir = cast(str, getattr(self.app, "confdir"))
            template_path = pathlib.Path(app_confdir) / tr_template

        if not template_path.is_file():
            raise InvalidConfigurationError(
                f"could not find a template file with name {template_path} in conf.py directory"
            )

        with template_path.open(encoding=cfg.tr_import_encoding) as template_file:
            template = "".join(template_file.readlines())

        if self.test_links is not None and len(self.test_links) > 0:
            links_string = f"\n   :links: {self.test_links}"
        else:
            links_string = ""

        tags_str = self.test_tags or ""
        id_str = self.test_id or ""
        tags_value = ";".join([tags_str, id_str]) if len(tags_str) > 0 else id_str

        template_data: Dict[str, object] = {
            "file": self.test_file or "",
            "id": id_str,
            "file_type": cast(List[str], cfg.tr_file)[0],
            "suite_need": cast(List[str], cfg.tr_suite)[1],
            "case_need": cast(List[str], cfg.tr_case)[1],
            "tags": tags_value,
            "links_string": links_string,
            "title": self.test_name or "",
            "content": self.content,
            "template_path": str(template_path),
        }

        template_ready = template.format(**template_data)
        src = cast(str, self.state_machine.document.attributes["source"])
        self.state_machine.insert_input(template_ready.split("\n"), src)

        return cast(List[nodes.Element], [])
