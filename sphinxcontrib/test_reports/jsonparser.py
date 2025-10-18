"""
A parser for test results  in JSON files.

Must be configured via config, as there is no known standard for Test data in JSON files.

API must be in sync with the JUnit parser in ``junitparser.py``.
"""

import json
import os
from typing import (
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    Union,
    cast,
)


class MappingEntry(TypedDict):
    testcase: Dict[str, Tuple[Sequence[Union[str, int]], object]]
    testsuite: Dict[str, Tuple[Sequence[Union[str, int]], object]]


def dict_get(
    root: Union[Dict[Union[str, int], object], List[object]],
    items: Sequence[Union[str, int]],
    default: Optional[object] = None,
) -> object:
    """
    Access a nested object in root by item sequence.

    Usage::
       data = {"nested": {"a_list": [{"finally": "target_data"}]}}
       value = dict_get(data, ["nested", "a_list", 0, "finally"], "Not_found")

    """
    try:
        obj: Union[Dict[Union[str, int], object], List[object]] = root
        for key in items:
            next_obj = obj[key]  # type: ignore[index]
            obj = cast(Union[Dict[Union[str, int], object], List[object]], next_obj)
        return obj
    except (KeyError, IndexError, TypeError):
        return default


class JsonParser:
    json_path: str
    json_data: List[Dict[str, object]]
    json_mapping: MappingEntry

    def __init__(
        self, json_path: str, *args: object, **kwargs: Dict[str, object]
    ) -> None:
        self.json_path = json_path

        if not os.path.exists(self.json_path):
            raise JsonFileMissingError(
                f"The given file does not exist: {self.json_path}"
            )

        with open(self.json_path, encoding="utf-8") as jfile:
            data_raw = json.load(jfile)  # type: ignore[assignment]
            data: List[Dict[str, object]] = cast(List[Dict[str, object]], data_raw)

        if not isinstance(data, list):
            raise TypeError("Expected top-level JSON to be a list of dicts")

        self.json_data = data

        mapping_fallback: MappingEntry = {"testcase": {}, "testsuite": {}}
        self.json_mapping = cast(
            MappingEntry, kwargs.get("json_mapping", mapping_fallback)
        )

    def validate(self) -> bool:
        # For JSON we validate nothing here.
        # But to be compatible with the API, we need to return True
        return True

    def parse(self) -> List[Dict[str, object]]:
        """
        Creates a common python list of object, no matter what information are
        supported by the parsed json file for test results junit().

        :return: list of test suites as dictionaries
        """

        def parse_testcase(
            json_dict: Dict[Union[str, int], object],
        ) -> Dict[str, object]:
            tc_mapping = self.json_mapping.get("testcase", {})
            return {
                k: dict_get(json_dict, path, fallback)
                for k, (path, fallback) in tc_mapping.items()
            }

        def parse_testsuite(
            json_dict: Dict[Union[str, int], object],
        ) -> Dict[str, object]:
            ts_mapping = self.json_mapping.get("testsuite", {})
            ts_dict: Dict[str, object] = {
                k: dict_get(json_dict, path, fallback)
                for k, (path, fallback) in ts_mapping.items()
                if k != "testcases"
            }

            testcases: List[Dict[str, object]] = []
            ts_dict["testcases"] = testcases
            ts_dict["testsuite_nested"] = []

            testcase_entry = ts_mapping.get("testcases")
            if testcase_entry:
                testcases_raw = dict_get(
                    json_dict, testcase_entry[0], testcase_entry[1]
                )
                if isinstance(testcases_raw, list):
                    for item in testcases_raw:
                        if isinstance(item, dict):
                            tc = parse_testcase(item)
                            testcases.append(tc)

            return ts_dict

        # main flow starts here

        suites = [ts for ts in self.json_data if isinstance(ts, dict)]
        junit_dict = [parse_testsuite(ts) for ts in suites]

        return junit_dict

    def docutils_table(self) -> None:
        pass


class JsonFileMissingError(Exception):
    pass


class JUnitFileMissingError(Exception):
    pass
