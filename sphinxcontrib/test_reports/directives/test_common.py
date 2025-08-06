"""
A Common directive, from which all other test directives inherit the shared functions.
"""

# fmt: off
import os
import pathlib
from importlib.metadata import version
from typing import Any, Dict, Optional

from docutils.parsers.rst import Directive
from sphinx.util import logging
from sphinx_needs.config import NeedsSphinxConfig

from sphinxcontrib.test_reports.exceptions import (
    SphinxError,
    TestReportFileNotSetError,
)
from sphinxcontrib.test_reports.jsonparser import JsonParser
from sphinxcontrib.test_reports.junitparser import JUnitParser

sn_major_version = int(version("sphinx-needs").split('.')[0])

if sn_major_version >= 4:
    from sphinx_needs.api.need import _make_hashed_id
else:
    from sphinx_needs.api import make_hashed_id


# fmt: on


class TestCommonDirective(Directive):
    """
    Common directive, which provides some shared functions to "real" directives.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.env: Any = self.state.document.settings.env
        self.app: Any = self.env.app
        if not hasattr(self.app, "testreport_data"):
            self.app.testreport_data: Dict[str, Any] = {}

        self.test_file: Optional[str] = None
        self.results: Optional[Any] = None
        self.docname: Optional[str] = None
        self.test_name: Optional[str] = None
        self.test_id: Optional[str] = None
        self.test_content: Optional[str] = None
        self.test_file_given: Optional[str] = None
        self.test_links: Optional[str] = None
        self.test_tags: Optional[str] = None
        self.test_status: Optional[str] = None
        self.collapse: Optional[Any] = None
        self.need_type: Optional[str] = None
        self.extra_options: Optional[Dict[str, Any]] = None

        self.log = logging.getLogger(__name__)

    def collect_extra_options(self) -> None:
        """Collect any extra options and their values that were specified in the directive"""
        tr_extra_options = getattr(self.app.config, "tr_extra_options", [])
        self.extra_options: Dict[str, Any] = {}

        if tr_extra_options:
            for option_name in tr_extra_options:
                if option_name in self.options:
                    self.extra_options[option_name] = self.options[option_name]

    def load_test_file(self) -> Optional[Any]:
        """
        Loads the defined test_file under self.test_file.

        ``prepare_basic_options`` must be called first

        :return: None
        """
        if self.test_file is None:
            raise TestReportFileNotSetError("Option test_file must be set.")

        test_path = pathlib.Path(self.test_file)
        if not test_path.is_absolute():
            root_path = pathlib.Path(self.app.config.tr_rootdir)
            test_path = root_path / test_path
        self.test_file = str(test_path)
        if not test_path.exists():
            # raise TestReportFileInvalidException('Given test_file path invalid: {}'.format(self.test_file))
            self.log.warning(
                f"Given test_file path invalid: {self.test_file} in {self.docname} (Line: {self.lineno})"
            )
            return None

        if self.test_file not in self.app.testreport_data.keys():
            if os.path.splitext(self.test_file)[1] == ".json":
                mapping = list(self.app.config.tr_json_mapping.values())[0]
                parser = JsonParser(self.test_file, json_mapping=mapping)
            else:
                parser = JUnitParser(self.test_file)
            self.app.testreport_data[self.test_file] = parser.parse()

        self.results = self.app.testreport_data[self.test_file]
        return self.results

    def prepare_basic_options(self) -> None:
        """
        Reads and checks the needed basic data like name, id, links, status, ...
        :return: None
        """
        self.docname = self.state.document.settings.env.docname

        self.test_name = self.arguments[0]
        self.test_content = "\n".join(self.content)
        if self.name != "test-report":
            self.need_type = self.app.tr_types[self.name][0]
            if sn_major_version >= 4:
                hashed_id = _make_hashed_id(
                    self.need_type,
                    self.test_name,
                    self.test_content,
                    NeedsSphinxConfig(self.app.config),
                )
            else:  # Sphinx-Needs < 4
                hashed_id = make_hashed_id(
                    self.app, self.need_type, self.test_name, self.test_content
                )

            self.test_id = self.options.get(
                "id",
                hashed_id,
            )
        else:
            self.test_id = self.options.get("id")

        if self.test_id is None:
            raise SphinxError("ID must be set for test-report.")

        self.test_file = self.options.get("file")
        self.test_file_given = self.test_file[:]

        self.test_links = self.options.get("links", "")
        self.test_tags = self.options.get("tags", "")
        self.test_status = self.options.get("status")

        self.collapse = str(self.options.get("collapse", ""))

        if isinstance(self.collapse, str) and len(self.collapse) > 0:
            if self.collapse.upper() in ["TRUE", 1, "YES"]:
                self.collapse = True
            elif self.collapse.upper() in ["FALSE", 0, "NO"]:
                self.collapse = False
            else:
                raise Exception("collapse attribute must be true or false")
        else:
            self.collapse = getattr(self.app.config, "needs_collapse_details", True)

        # Also collect any extra options while we're at it
        self.collect_extra_options()
