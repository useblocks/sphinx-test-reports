# fmt: off
import os

import sphinx
from docutils.parsers.rst import directives
from packaging.version import Version
from sphinx.application import Sphinx
from sphinx.config import Config

# from docutils import nodes
from sphinx_needs.api import add_dynamic_function, add_extra_option, add_need_type

from sphinxcontrib.test_reports.directives.test_case import TestCase, TestCaseDirective
from sphinxcontrib.test_reports.directives.test_env import EnvReport, EnvReportDirective
from sphinxcontrib.test_reports.directives.test_file import TestFile, TestFileDirective
from sphinxcontrib.test_reports.directives.test_report import (
    TestReport,
    TestReportDirective,
)
from sphinxcontrib.test_reports.directives.test_results import (
    TestResults,
    TestResultsDirective,
)
from sphinxcontrib.test_reports.directives.test_suite import (
    TestSuite,
    TestSuiteDirective,
)
from sphinxcontrib.test_reports.environment import install_styles_static_files
from sphinxcontrib.test_reports.functions import tr_link

from typing import Any, Dict, List, Optional, Protocol, cast

class LoggerProtocol(Protocol):
    def debug(self, msg: str) -> object: ...
    def info(self, msg: str) -> object: ...
    def warning(self, msg: str) -> object: ...
    def error(self, msg: str) -> object: ...

sphinx_version = sphinx.__version__
if Version(sphinx_version) >= Version("1.6"):
    from sphinx.util import logging as sphinx_logging
    logger: LoggerProtocol = cast(LoggerProtocol, sphinx_logging.getLogger(__name__))
else:
    import logging as std_logging
    std_logging.basicConfig()
    logger: LoggerProtocol = cast(LoggerProtocol, std_logging.getLogger(__name__))

# fmt: on

VERSION = "1.1.1"


def setup(app: Sphinx) -> dict[str, object]:
    """
    Setup following directives:
    * test_results
    * test_env
    * test_report
    """

    log = logger
    log.info("Setting up sphinx-test-reports extension")

    # configurations
    app.add_config_value("tr_rootdir", cast(str, app.confdir), "html")
    app.add_config_value(
        "tr_file",
        cast(List[str], ["test-file", "testfile", "Test-File", "TF_", "#ffffff", "node"]),
        "html",
    )
    app.add_config_value(
        "tr_suite",
        cast(List[str], ["test-suite", "testsuite", "Test-Suite", "TS_", "#cccccc", "folder"]),
        "html",
    )
    app.add_config_value(
        "tr_case",
        cast(List[str], ["test-case", "testcase", "Test-Case", "TC_", "#999999", "rectangle"]),
        "html",
    )

    # adds option for custom template
    template_dir = os.path.join(
        os.path.dirname(__file__), "directives/test_report_template.txt"
    )
    app.add_config_value("tr_report_template", template_dir, "html")

    app.add_config_value("tr_suite_id_length", 3, "html")
    app.add_config_value("tr_case_id_length", 5, "html")
    app.add_config_value("tr_import_encoding", "utf8", "html")
    app.add_config_value("tr_extra_options", cast(List[str], []), "env")

    json_mapping = {
        "json_config": {
            "testsuite": {
                "name": (["name"], "unknown"),
                "tests": (["tests"], "unknown"),
                "errors": (["errors"], "unknown"),
                "failures": (["failures"], "unknown"),
                "skips": (["skips"], "unknown"),
                "passed": (["passed"], "unknown"),
                "time": (["time"], "unknown"),
                "testcases": (["testcase"], "unknown"),
            },
            "testcase": {
                "name": (["name"], "unknown"),
                "classname": (["classname"], "unknown"),
                "file": (["file"], "unknown"),
                "line": (["line"], "unknown"),
                "time": (["time"], "unknown"),
                "result": (["result"], "unknown"),
                "type": (["type"], "unknown"),
                "text": (["text"], "unknown"),
                "message": (["message"], "unknown"),
                "system-out": (["system-out"], "unknown"),
            },
        }
    }

    app.add_config_value("tr_json_mapping", json_mapping, "html", types=[dict])

    # nodes
    cast(object, app.add_node(TestResults))
    cast(object, app.add_node(TestFile))
    cast(object, app.add_node(TestSuite))
    cast(object, app.add_node(TestCase))
    cast(object, app.add_node(TestReport))
    cast(object, app.add_node(EnvReport))

    # directives
    cast(object, app.add_directive("test-results", TestResultsDirective))
    cast(object, app.add_directive("test-env", EnvReportDirective))
    cast(object, app.add_directive("test-report", TestReportDirective))

    # events
    cast(object, app.connect("env-updated", install_styles_static_files))
    cast(object, app.connect("config-inited", tr_preparation))
    cast(object, app.connect("config-inited", sphinx_needs_update))

    cast(object, app.connect("builder-inited", register_tr_extra_options))

    return {
        "version": VERSION,  # identifies the version of our extension
        "parallel_read_safe": True,  # support parallel modes
        "parallel_write_safe": True,
    }


def register_tr_extra_options(app: Sphinx) -> None:
    """Register extra options with directives."""

    log = logger
    tr_extra_options = cast(List[str], getattr(app.config, "tr_extra_options", []))
    log.debug(f"tr_extra_options = {tr_extra_options}")

    if tr_extra_options:
        for direc in [TestSuiteDirective, TestFileDirective, TestCaseDirective]:
            for option_name in tr_extra_options:
                opt_spec = cast(Dict[str, object], direc.option_spec)
                opt_spec[option_name] = directives.unchanged
                log.debug(f"Registered {option_name} with {direc}")
                log.debug(
                    f"{direc}.option_spec now has keys: {list(cast(Dict[str, object], direc.option_spec).keys())}"
                )


def tr_preparation(app: Sphinx, *args: object) -> None:
    """
    Prepares needed vars in the app context.
    """
    if not hasattr(app, "tr_types"):
        setattr(app, "tr_types", {})

    # Collects the configured test-report node types
    tr_types = cast(Dict[str, List[str]], getattr(app, "tr_types"))
    tr_file = cast(List[str], app.config.tr_file)
    tr_suite = cast(List[str], app.config.tr_suite)
    tr_case = cast(List[str], app.config.tr_case)
    tr_types[tr_file[0]] = tr_file[1:]
    tr_types[tr_suite[0]] = tr_suite[1:]
    tr_types[tr_case[0]] = tr_case[1:]

    cast(object, app.add_directive(tr_file[0], TestFileDirective))
    cast(object, app.add_directive(tr_suite[0], TestSuiteDirective))
    cast(object, app.add_directive(tr_case[0], TestCaseDirective))


def sphinx_needs_update(app: Sphinx, config: Config) -> None:
    """
    sphinx-needs configuration
    """

    # Extra options
    # For details read
    # https://sphinx-needs.readthedocs.io/en/latest/api.html#sphinx_needs.api.configuration.add_extra_option

    cast(object, add_extra_option(app, "file"))
    cast(object, add_extra_option(app, "suite"))
    cast(object, add_extra_option(app, "case"))
    cast(object, add_extra_option(app, "case_name"))
    cast(object, add_extra_option(app, "case_parameter"))
    cast(object, add_extra_option(app, "classname"))
    cast(object, add_extra_option(app, "time"))

    cast(object, add_extra_option(app, "suites"))
    cast(object, add_extra_option(app, "cases"))

    cast(object, add_extra_option(app, "passed"))
    cast(object, add_extra_option(app, "skipped"))
    cast(object, add_extra_option(app, "failed"))
    cast(object, add_extra_option(app, "errors"))
    cast(object, add_extra_option(app, "result"))  # used by test cases only

    # Extra dynamic functions
    # For details about usage read
    # https://sphinx-needs.readthedocs.io/en/latest/api.html#sphinx_needs.api.configuration.add_dynamic_function
    cast(object, add_dynamic_function(app, tr_link))

    # Extra need types
    # For details about usage read
    # https://sphinx-needs.readthedocs.io/en/latest/api.html#sphinx_needs.api.configuration.add_need_type
    tr_file = cast(List[str], app.config.tr_file)
    tr_suite = cast(List[str], app.config.tr_suite)
    tr_case = cast(List[str], app.config.tr_case)
    cast(object, add_need_type(app, *tr_file[1:]))
    cast(object, add_need_type(app, *tr_suite[1:]))
    cast(object, add_need_type(app, *tr_case[1:]))
