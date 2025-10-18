"""
JUnit XML parser
"""

import os
from typing import Dict, List, Optional, cast

from lxml import etree, objectify
from lxml.etree import _Element, _ElementTree


class JUnitParser:
    junit_xml_path: str
    junit_xsd_path: str
    junit_schema_doc: Optional[_ElementTree]
    xmlschema: Optional[etree.XMLSchema]
    valid_xml: Optional[bool]
    junit_xml_doc: _ElementTree
    junit_xml_string: str
    junit_xml_object: _Element

    def __init__(self, junit_xml: str, junit_xsd: Optional[str] = None) -> None:
        self.junit_xml_path = junit_xml
        if junit_xsd is None:
            junit_xsd = os.path.join(os.path.dirname(__file__), "schemas", "JUnit.xsd")
        self.junit_xsd_path = junit_xsd

        if not os.path.exists(self.junit_xml_path):
            raise JUnitFileMissingError(
                f"The given file does not exist: {self.junit_xml_path}"
            )

        self.junit_schema_doc = None
        self.xmlschema = None
        self.valid_xml = None

        parsed: _ElementTree = etree.parse(self.junit_xml_path)
        self.junit_xml_doc = parsed
        self.junit_xml_string = etree.tostring(self.junit_xml_doc).decode()
        raw_obj = objectify.fromstring(self.junit_xml_string)
        self.junit_xml_object = cast(_Element, raw_obj)

    def validate(self) -> bool:
        self.junit_schema_doc = cast(_ElementTree, etree.parse(self.junit_xsd_path))
        self.xmlschema = etree.XMLSchema(self.junit_schema_doc)
        self.valid_xml = self.xmlschema.validate(self.junit_xml_doc)
        return bool(self.valid_xml)

    def parse(self) -> List[Dict[str, object]]:
        """
        Creates a common python list of object, no matter what information are
        supported by the parsed xml file for test results junit().

        :return: list of test suites as dictionaries
        """

        def parse_testcase(testcase: _Element) -> Dict[str, object]:
            tc_dict: Dict[str, object] = {
                "classname": str(testcase.attrib.get("classname", "unknown")),
                "file": str(testcase.attrib.get("file", "unknown")),
                "line": int(testcase.attrib.get("line", "-1")),
                "name": str(testcase.attrib.get("name", "unknown")),
                "time": float(testcase.attrib.get("time", "-1")),
            }

            # The following data is normally a subnode (e.g. skipped/failure).
            # We integrate it right into the testcase for better handling
            if hasattr(testcase, "skipped"):
                skipped = cast(_Element, testcase.skipped)
                tc_dict["result"] = "skipped"
                tc_dict["type"] = str(skipped.attrib.get("type", "unknown"))
                tc_dict["text"] = str(skipped.text or "")
                # tc_dict["text"] = re.sub(r"[\n\t]*", "", result.text)  # Removes newlines  and tabs
                # result.text can be None for pytest xfail test cases
                tc_dict["message"] = str(skipped.attrib.get("message", "unknown"))
            elif hasattr(testcase, "failure"):
                failure = cast(_Element, testcase.failure)
                tc_dict["result"] = "failure"
                tc_dict["type"] = str(failure.attrib.get("type", "unknown"))
                # tc_dict["text"] = re.sub(r"[\n\t]*", "", result.text)  # Removes newlines and tabs
                tc_dict["text"] = str(failure.text or "")
                tc_dict["message"] = ""
            else:
                tc_dict["result"] = "passed"
                tc_dict["type"] = ""
                tc_dict["text"] = ""
                tc_dict["message"] = ""

            if hasattr(testcase, "system-out"):
                sysout = cast(_Element, getattr(testcase, "system-out"))
                tc_dict["system-out"] = str(sysout.text or "")
            else:
                tc_dict["system-out"] = ""

            return tc_dict

        def parse_testsuite(testsuite: _Element) -> Dict[str, object]:
            tests = int(testsuite.attrib.get("tests", "-1"))
            errors = int(testsuite.attrib.get("errors", "-1"))
            failures = int(testsuite.attrib.get("failures", "-1"))

            # fmt: off
            skips_str = (
                testsuite.attrib.get("skips")
                or testsuite.attrib.get("skip")
                or testsuite.attrib.get("skipped")
                or "-1"
            )
            # fmt: on

            skips = int(skips_str)
            passed = max(0, tests - max(0, errors) - max(0, failures) - max(0, skips))

            ts_dict: Dict[str, object] = {
                "name": str(testsuite.attrib.get("name", "unknown")),
                "tests": tests,
                "errors": errors,
                "failures": failures,
                "skips": skips,
                "passed": passed,
                "time": float(testsuite.attrib.get("time", "-1")),
                "testcases": [],
                "testsuite_nested": [],
            }

            # add nested testsuite objects to
            if hasattr(testsuite, "testsuite"):
                nested_suites = cast(List[_Element], testsuite.testsuite)
                for ts in nested_suites:
                    # dict from inner parse
                    cast(List[Dict[str, object]], ts_dict["testsuite_nested"]).append(
                        parse_testsuite(ts)
                    )

            if hasattr(testsuite, "testcase"):
                testcases = cast(List[_Element], testsuite.testcase)
                for tc in testcases:
                    cast(List[Dict[str, object]], ts_dict["testcases"]).append(
                        parse_testcase(tc)
                    )

            return ts_dict

        # main flow starts here

        junit_dict: List[Dict[str, object]] = []

        if self.junit_xml_object.tag == "testsuites":
            if hasattr(self.junit_xml_object, "testsuite"):
                suites = cast(List[_Element], self.junit_xml_object.testsuite)
                junit_dict.extend([parse_testsuite(ts) for ts in suites])
        else:
            junit_dict.append(parse_testsuite(self.junit_xml_object))

        return junit_dict

    def docutils_table(self) -> None:
        pass


class JUnitFileMissingError(Exception):
    pass
