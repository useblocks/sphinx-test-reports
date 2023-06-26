"""
A parser for test results  in JSON files.

Must be configured via config, as there is no known standard for Test data in JSON files.

API must be in sync with the JUnit parser in ``junitparser.py``.
"""
import json
import operator
import os

from functools import reduce


def dict_get(root, items, default=None):
    """
    Access a nested object in root by item sequence.

    Usage::
       data = {"nested": {"a_list": [{"finally": "target_data"}]}}
       value = dict_get(data, ["nested", "a_list", 0, "finally"], "Not_found")

    """
    try:
        value = reduce(operator.getitem, items, root)
    except (KeyError, IndexError, TypeError):
        return default
    return value


class JsonParser:
    def __init__(self, json_path, *args, **kwargs):
        self.json_path = json_path

        if not os.path.exists(self.json_path):
            raise JsonFileMissing(f"The given file does not exist: {self.json_path}")

        self.json_data = []
        with open(self.json_path) as jfile:
            self.json_data = json.load(jfile)

    def validate(self):
        # For JSON we validate nothing here.
        # But to be compatible with the API, we need to return True
        return True

    def parse(self):
        """
        Creates a common python list of object, no matter what information are
        supported by the parsed json file for test results junit().

        :return: list of test suites as dictionaries
        """

        def parse_testcase(json_dict):
            # testcase = json_dict

            # ToDo: Replace dict-keys by values from conf.py
            tc_dict = {
                "classname": dict_get(json_dict, ["classname"], "unknown"),
                "file": dict_get(json_dict, ["test", "file"], "unknown"),
                "line": dict_get(json_dict, ["line"], -1),
                "name": dict_get(json_dict, ["name"], "unknown"),
                "time": dict_get(json_dict, ["time"], -1),
                "result": dict_get(json_dict, ["result"], "unknown"),
                "type": dict_get(json_dict, ["type"], "unknown"),
                "text": dict_get(json_dict, ["text"], "unknown"),
                "message": dict_get(json_dict, ["message"], "unknown"),
                "system-out": dict_get(json_dict, ["system-out"], "unknown"),
            }
            return tc_dict

        def parse_testsuite(json_dict):
            # testsuite = json_dict

            ts_dict = {
                "name": dict_get(json_dict, ["name"], "unknown"),
                "tests": dict_get(json_dict, ["tests"], -1),
                "errors": dict_get(json_dict, ["errors"], -1),
                "failures": dict_get(json_dict, ["failures"], -1),
                "skips": dict_get(json_dict, ["skips"], -1),
                "passed": dict_get(json_dict, ["passed"], -1),
                "time": dict_get(json_dict, ["time"], -1),
                "testcases": [],
                "testsuite_nested": [],
            }

            testcases = dict_get(json_dict, ["testcase"], [])
            for tc in testcases:
                new_testcase = parse_testcase(tc)
                ts_dict["testcases"].append(new_testcase)

            return ts_dict

        # main flow starts here

        result_data = []

        for testsuite_data in self.json_data:
            complete_testsuite = parse_testsuite(testsuite_data)
            result_data.append(complete_testsuite)

        return result_data

    def docutils_table(self):
        pass


class JsonFileMissing(BaseException):
    pass
