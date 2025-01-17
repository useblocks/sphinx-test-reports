# fmt: off
import pathlib

from docutils import nodes
from docutils.parsers.rst import directives

from sphinxcontrib.test_reports.directives.test_common import \
    TestCommonDirective
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        self.prepare_basic_options()
        self.load_test_file()

        # if user provides a custom template, use it
        tr_template = pathlib.Path(self.app.config.tr_report_template)

        if tr_template.is_absolute():
            template_path = tr_template
        else:
            template_path = pathlib.Path(self.app.confdir) / tr_template

        if not template_path.is_file():
            raise InvalidConfigurationError(
                f"could not find a template file with name {template_path} in conf.py directory"
            )

        with template_path.open(encoding=self.app.config.tr_import_encoding) as template_file:
            template = "".join(template_file.readlines())

        if self.test_links is not None and len(self.test_links) > 0:
            links_string = f"\n   :links: {self.test_links}"
        else:
            links_string = ""

        template_data = {
            "file": self.test_file,
            "id": self.test_id,
            "file_type": self.app.config.tr_file[0],
            "suite_need": self.app.config.tr_suite[1],
            "case_need": self.app.config.tr_case[1],
            "tags": (";".join([self.test_tags, self.test_id]) if len(self.test_tags) > 0 else self.test_id),
            "links_string": links_string,
            "title": self.test_name,
            "content": self.content,
            "template_path": str(template_path),
        }

        template_ready = template.format(**template_data)
        self.state_machine.insert_input(template_ready.split("\n"), self.state_machine.document.attributes["source"])

        return []
