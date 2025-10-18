"""
A Common directive, from which all other test directives inherit the shared functions.
"""

# fmt: off
import os
import pathlib
from importlib.metadata import version
from typing import (
    Dict,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Tuple,
    Union,
    cast,
)

from docutils.parsers.rst import Directive
from sphinx.util import logging
from sphinx_needs.config import NeedsSphinxConfig  # type: ignore[import-untyped]

from sphinxcontrib.test_reports.exceptions import (
    SphinxError,
    TestReportFileNotSetError,
)
from sphinxcontrib.test_reports.jsonparser import JsonParser, MappingEntry
from sphinxcontrib.test_reports.junitparser import JUnitParser

sn_major_version = int(version("sphinx-needs").split('.')[0])

if sn_major_version >= 4:
    from sphinx_needs.api.need import _make_hashed_id  # type: ignore[import-untyped]
else:
    from sphinx_needs.api import make_hashed_id  # type: ignore[import-untyped]


# fmt: on


class _SphinxConfigProtocol(Protocol):
    tr_rootdir: str
    tr_json_mapping: Mapping[str, "MappingEntry"]  # Provided by user config
    needs_collapse_details: bool


class _SphinxAppProtocol(Protocol):
    config: _SphinxConfigProtocol
    tr_types: Mapping[str, Tuple[str, str]]
    testreport_data: MutableMapping[str, List[Dict[str, object]]]


class _SphinxEnvProtocol(Protocol):
    app: _SphinxAppProtocol
    docname: str


# Re-export type name for readability in this file
MappingEntryType = MappingEntry


class TestCommonDirective(Directive):
    """
    Common directive, which provides some shared functions to "real" directives.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.env: _SphinxEnvProtocol = cast(
            _SphinxEnvProtocol, self.state.document.settings.env
        )
        self.app: _SphinxAppProtocol = self.env.app
        if not hasattr(self.app, "testreport_data"):
            empty_store: Dict[str, List[Dict[str, object]]] = {}
            self.app.testreport_data = empty_store

        self.test_file: Optional[str] = None
        self.results: Optional[List[Dict[str, object]]] = None
        self.docname: Optional[str] = None
        self.test_name: Optional[str] = None
        self.test_id: Optional[str] = None
        self.test_content: Optional[str] = None
        self.test_file_given: Optional[str] = None
        self.test_links: Optional[str] = None
        self.test_tags: Optional[str] = None
        self.test_status: Optional[str] = None
        self.collapse: bool = True
        self.need_type: Optional[str] = None
        self.extra_options: Optional[Dict[str, object]] = None

        self.log = logging.getLogger(__name__)

    def collect_extra_options(self) -> None:
        """Collect any extra options and their values that were specified in the directive"""
        tr_extra_options = cast(
            Optional[List[str]], getattr(self.app.config, "tr_extra_options", None)
        )
        extra: Dict[str, object] = {}

        if tr_extra_options:
            for option_name in tr_extra_options:
                if option_name in self.options:
                    extra[option_name] = self.options[option_name]
        self.extra_options = extra

    def load_test_file(self) -> Optional[List[Dict[str, object]]]:
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

        testreport_data = self.app.testreport_data
        if self.test_file not in testreport_data.keys():
            parser: Union[JsonParser, JUnitParser]
            if os.path.splitext(self.test_file)[1] == ".json":
                json_mapping_all = self.app.config.tr_json_mapping
                mapping_values = list(json_mapping_all.values())
                mapping: MappingEntryType = (
                    mapping_values[0]
                    if mapping_values
                    else {"testcase": {}, "testsuite": {}}
                )
                parser = JsonParser(self.test_file, json_mapping=mapping)  # type: ignore[arg-type]
            else:
                parser = JUnitParser(self.test_file)
            testreport_data[self.test_file] = parser.parse()

        self.results = testreport_data[self.test_file]
        return self.results

    def prepare_basic_options(self) -> None:
        """
        Reads and checks the needed basic data like name, id, links, status, ...
        :return: None
        """
        # mypy: explicit type for Any
        self.docname = self.state.document.settings.env.docname  # type: ignore[misc]
        self.test_name = cast(str, self.arguments[0])
        self.test_content = "\n".join(self.content)
        if self.name != "test-report":
            self.need_type = self.app.tr_types[self.name][0]
            if sn_major_version >= 4:
                hashed_id = cast(
                    str,
                    _make_hashed_id(
                        self.need_type,
                        self.test_name,
                        self.test_content,
                        NeedsSphinxConfig(self.app.config),
                    ),
                )
            else:  # Sphinx-Needs < 4
                hashed_id = cast(
                    str,
                    make_hashed_id(
                        self.app, self.need_type, self.test_name, self.test_content
                    ),
                )

            opt_id = self.options.get("id")
            self.test_id = str(opt_id) if opt_id is not None else hashed_id
        else:
            opt_id = self.options.get("id")
            self.test_id = str(opt_id) if opt_id is not None else None

        if self.test_id is None:
            raise SphinxError("ID must be set for test-report.")

        self.test_file = cast(Optional[str], self.options.get("file"))
        self.test_file_given = (
            str(self.test_file) if self.test_file is not None else None
        )

        self.test_links = cast(str, self.options.get("links", ""))
        self.test_tags = cast(str, self.options.get("tags", ""))
        self.test_status = cast(Optional[str], self.options.get("status"))

        collapse_raw: object = self.options.get("collapse", "")

        if isinstance(collapse_raw, str) and len(collapse_raw) > 0:
            value = collapse_raw.strip().upper()
            if value in ("TRUE", "YES", "1"):
                self.collapse = True
            elif value in ("FALSE", "NO", "0"):
                self.collapse = False
            else:
                raise Exception("collapse attribute must be true or false")
        elif isinstance(collapse_raw, bool):
            self.collapse = collapse_raw
        else:
            self.collapse = bool(
                getattr(self.app.config, "needs_collapse_details", True)
            )

        # Also collect any extra options while we're at it
        self.collect_extra_options()
