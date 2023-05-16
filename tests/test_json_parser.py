import os

json_path = os.path.join(os.path.dirname(__file__), "doc_test/utils", "json_data.json")

def test_init_json_parser():
    from sphinxcontrib.test_reports.jsonparser import JsonParser

    parser = JsonParser(json_path)
    assert parser is not None


def test_parse_json_data():
    from sphinxcontrib.test_reports.jsonparser import JsonParser

    parser = JsonParser(json_path)
    results = parser.parse()
    assert results is not None
    assert len(results) == 1
    assert len(results[0]["testcases"]) == 3
    assert results[0]["testcases"][1]["result"] == "passed"
