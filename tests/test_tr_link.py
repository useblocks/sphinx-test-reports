from sphinxcontrib.test_reports.functions import tr_link


def test_tr_link_option_not_in_need():
    """
    Return an empty string when the specified test option is missing from the need.
    """
    assert (
        tr_link(app=None, need={}, needs={}, test_option="a", target_option="b") == ""
    )


def test_tr_link_no_target_option_in_needs():
    """
    Return an empty list when the target option is missing in all items of needs.
    """
    assert (
        tr_link(
            app=None,
            need={"id": "1", "a": "1"},
            needs={"x": {"id": "123"}},
            test_option="a",
            target_option="b",
        )
        == []
    )


def test_tr_link_no_match():
    """
    Returns an empty list when no matching value for the test option is found
    in any of the target options within needs.
    """
    assert (
        tr_link(
            app=None,
            need={"id": "1", "a": "1"},
            needs={"x": {"b": "2", "id": "123"}},
            test_option="a",
            target_option="b",
        )
        == []
    )


def test_tr_link_match():
    """
    Returns a list of ids when there is a matching value in both need and needs.
    """
    assert tr_link(
        app=None,
        need={"id": "1", "a": "1"},
        needs={"x": {"b": "1", "id": "123"}},
        test_option="a",
        target_option="b",
    ) == ["123"]


def test_tr_link_none_or_empty():
    """
    'None' and empty string values are not considered as valid matches.
    """
    need = {"id": "1", "a": None, "b": ""}
    needs = {
        "x": {"c": None, "id": "111"},
        "y": {"c": "valid", "id": "222"},
        "z": {"c": "", "id": "333"},
    }
    assert (
        tr_link(app=None, need=need, needs=needs, test_option="b", target_option="c")
        == []
    )
    assert (
        tr_link(app=None, need=need, needs=needs, test_option="a", target_option="c")
        == []
    )


def test_tr_link_regex_match():
    """
    Returns a list of ids when the test option value containing an asterisk (*)
    correctly matches target options using regular expression patterns.
    """
    needs = {
        "x": {"b": "abc123", "id": "111"},
        "q": {"b": "abc/123", "id": "112"},
        "y": {"b": "def456", "id": "222"},
        "z": {"b": "ghi789", "id": "333"},
    }
    need = {"id": "1", "a": "abc.*"}
    assert tr_link(
        app=None, need=need, needs=needs, test_option="a", target_option="b"
    ) == ["111", "112"]


def test_tr_link_regex_no_match():
    """
    Returns an empty list when the test option value containing an asterisk (*)
    does not match any target options using regular expression patterns.
    """
    needs = {"x": {"b": "abc123", "id": "111"}, "y": {"b": "def456", "id": "222"}}
    need = {"id": "1", "a": "xyz.*"}
    assert (
        tr_link(app=None, need=need, needs=needs, test_option="a", target_option="b")
        == []
    )


def test_tr_link_skip_linking_to_itself():
    """
    Returns an empty list when the need and needs have the same 'id'.
    """
    needs = {"x": {"b": "abc123", "id": "111"}, "y": {"b": "abc123", "id": "222"}}
    need = {"id": "111", "a": "abc123"}
    assert tr_link(
        app=None, need=need, needs=needs, test_option="a", target_option="b"
    ) == ["222"]
