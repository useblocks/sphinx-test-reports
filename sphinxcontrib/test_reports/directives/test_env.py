from __future__ import annotations

import copy
import json
import os
from typing import List, Optional, Tuple, Dict, Iterable, Protocol, cast

import sphinx
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from packaging.version import Version
from sphinx.environment import BuildEnvironment

# ---------- Typing ----------

class LoggerProtocol(Protocol):
    def debug(self, msg: str) -> object: ...
    def info(self, msg: str) -> object: ...
    def warning(self, msg: str) -> object: ...
    def error(self, msg: str) -> object: ...

class _AppConfigProtocol(Protocol):
    tr_rootdir: str

class _AppProtocol(Protocol):
    config: _AppConfigProtocol

# ---------- Logger ----------

sphinx_version = sphinx.__version__
logger: LoggerProtocol
if Version(sphinx_version) >= Version("1.6"):
    from sphinx.util import logging as sphinx_logging
    logger = cast(LoggerProtocol, sphinx_logging.getLogger(__name__))
else:
    import logging as std_logging
    std_logging.basicConfig()
    logger = cast(LoggerProtocol, std_logging.getLogger(__name__))

# ---------- Nodes & Directive ----------

class EnvReport(nodes.General, nodes.Element):
    pass


class EnvReportDirective(Directive):
    """
    Directive for showing test results.
    """

    has_content = True
    required_arguments = 1
    optional_arguments = 0
    option_spec = {
        "env": directives.unchanged_required,
        "data": directives.unchanged_required,
        "raw": directives.flag,
    }

    final_argument_whitespace = True

    header: Tuple[str, str] = ("Variable", "Data")
    colwidths: Tuple[int, int] = (1, 1)

    # Initialized in run()
    req_env_list: Optional[List[str]]
    data_option_list: Optional[List[str]]

    def run(self) -> List[nodes.Node]:
        # Prepare options
        data_option = cast(Optional[str], self.options.get("data"))
        environments = cast(Optional[str], self.options.get("env"))

        if environments is not None:
            req_env_list_cpy: List[str] = environments.split(",")
            self.req_env_list = []
            for element in req_env_list_cpy:
                if len(element) != 0:
                    self.req_env_list.append(element.lstrip().rstrip())
        else:
            self.req_env_list = None

        if data_option is not None:
            data_option_list_cpy: List[str] = data_option.split(",")
            self.data_option_list = []
            for element in data_option_list_cpy:
                if len(element) != 0:
                    self.data_option_list.append(element.rstrip().lstrip())
        else:
            self.data_option_list = None

        env = cast(BuildEnvironment, self.state.document.settings.env)

        json_path = self.arguments[0]
        app_typed: _AppProtocol = cast(_AppProtocol, env.app)
        cfg: _AppConfigProtocol = app_typed.config
        root_path = cfg.tr_rootdir  # str

        if not os.path.isabs(json_path):
            json_path = os.path.join(root_path, json_path)

        if not os.path.exists(json_path):
            raise JsonFileNotFound(f"The given file does not exist: {json_path}")

        with open(json_path) as fp_json:
            try:
                results: Dict[str, Dict[str, object]] = json.load(fp_json)
            except ValueError as exc:
                raise InvalidJsonFile(
                    "The given file {} is not a valid JSON".format(
                        json_path.split("/")[-1]
                    )
                ) from exc

        # check to see if environment is present in JSON or not
        if self.req_env_list is not None:
            not_present_env = [
                req_env for req_env in self.req_env_list if req_env not in results
            ]
            for not_env in not_present_env:
                self.req_env_list.remove(not_env)
                logger.warning(f"environment '{not_env}' is not present in JSON file")
            del not_present_env

        # Construction idea taken from http://agateau.com/2015/docutils-snippets/
        main_section: List[nodes.Node] = []

        if self.req_env_list is None and "raw" not in self.options:
            for enviro in results:
                main_section += self._crete_table_b(enviro=enviro, results=results)

        elif "raw" not in self.options and self.req_env_list is not None:
            for req_env in self.req_env_list:
                main_section += self._crete_table_b(enviro=req_env, results=results)

        elif "raw" in self.options and self.req_env_list is None:
            for enviro in results:
                # data option handling
                temp_dict = copy.deepcopy(results)
                temp_dict2 = copy.deepcopy(results)
                if self.data_option_list is not None:
                    for opt in temp_dict[enviro]:
                        if opt not in self.data_option_list:
                            del temp_dict2[enviro][opt]
                    # option check
                    for opt in self.data_option_list:
                        if opt not in temp_dict2[enviro]:
                            logger.warning(
                                f"option '{opt}' is not present in JSON file"
                            )

                del temp_dict

                section = nodes.section()
                section += nodes.title(text=enviro)
                results_string = json.dumps(temp_dict2[enviro], indent=4)
                code_block = nodes.literal_block(results_string, results_string)
                code_block["language"] = "json"
                section += code_block  # nodes.literal_block(results, results)
                main_section.append(section)  # nodes.literal_block(enviro, results[enviro])
                del temp_dict2

        elif "raw" in self.options and self.req_env_list is not None:
            for enviro in self.req_env_list:
                # data option handling
                temp_dict = copy.deepcopy(results)
                temp_dict2 = copy.deepcopy(results)
                if self.data_option_list is not None:
                    for opt in temp_dict[enviro]:
                        if opt not in self.data_option_list:
                            del temp_dict2[enviro][opt]

                # option check
                for opt in self.data_option_list or []:
                    if opt not in temp_dict2[enviro]:
                        logger.warning(
                            f"option '{opt}' is not present in '{enviro}' environment file"
                        )

                del temp_dict

                section = nodes.section()
                section += nodes.title(text=enviro)
                results_string = json.dumps(temp_dict2[enviro], indent=4)
                code_block = nodes.literal_block(results_string, results_string)
                code_block["language"] = "json"
                section += code_block
                main_section.append(section)
                del temp_dict2

        return main_section

    def _crete_table_b(self, enviro: str, results: Dict[str, Dict[str, object]]) -> List[nodes.Node]:
        main_section: List[nodes.Node] = []
        section = nodes.section()
        section += nodes.title(text=enviro)

        table = nodes.table()
        section += table

        tgroup = nodes.tgroup(cols=len(self.header))
        table += tgroup
        for colwidth in self.colwidths:
            tgroup += nodes.colspec(colwidth=colwidth)

        thead = nodes.thead()
        tgroup += thead
        thead += self._create_rows(self.header)

        tbody = nodes.tbody()
        tgroup += tbody
        all_data = results[enviro]

        data_option = copy.deepcopy(self.data_option_list)
        for data in all_data:
            if data_option is not None:
                if data in data_option:
                    data_option.remove(data)
                    tbody += self._create_rows((data, all_data[data]))
            else:
                tbody += self._create_rows((data, all_data[data]))

        main_section += section

        # data option check
        if data_option is not None:
            if len(data_option) != 0:
                for opt in data_option:
                    logger.warning(f"option '{opt}' is not present in JSON file")
            del data_option

        return main_section

    def _create_rows(self, row_cells: Iterable[object]) -> nodes.row:
        row = nodes.row()
        for cell in row_cells:
            entry = nodes.entry()
            row += entry
            if isinstance(cell, (list, dict)):
                results_string = json.dumps(cell, indent=4)
                code_block = nodes.literal_block(results_string, results_string)
                code_block["language"] = "json"
                entry += code_block
            else:
                entry += nodes.paragraph(text=cast(str, cell))
        return row


class InvalidJsonFile(Exception):
    pass


class JsonFileNotFound(Exception):
    pass


class InvalidEnvRequested(Exception):
    pass
