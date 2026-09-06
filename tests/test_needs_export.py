"""Unit tests for the needs.json writer and the URL helpers behind it.

The CLI tests cover the end-to-end shape; these pin down the pieces whose
failure would be silent in that shape -- evidence text mangled but present,
cases lost but the file valid, a URL that looks right and 404s.
"""

import pytest

from sphinxcontrib.test_reports.needs_export import (
    build_content,
    build_need,
    build_needs_file,
)
from sphinxcontrib.test_reports.remote import normalise_remote_url, source_url


def _case(name="test_x", **extra):
    return {"classname": "Suite", "name": name, "file": "t.py", "line": 3, **extra}


class TestEvidenceText:
    def test_relative_indentation_survives(self):
        # A traceback is only readable with its indentation; only the common
        # indentation XML pretty-printing adds may go.
        text = (
            "\n"
            "      Traceback (most recent call last):\n"
            '        File "t.py", line 3, in test_x\n'
            "          assert a == b\n"
            "                 ^^^^^^\n"
            "      AssertionError\n"
            "    "
        )
        content = build_content({"parts": [{"kind": "failure", "text": text}]})
        assert '   Traceback (most recent call last):\n     File "t.py"' in content
        assert "            ^^^^^^\n   AssertionError" in content

    def test_blank_lines_carry_no_trailing_whitespace(self):
        content = build_content({"parts": [{"kind": "failure", "text": "a\n\nb"}]})
        assert "\n   a\n\n   b\n" in content


class TestDuplicateCases:
    def test_a_case_reported_twice_is_refused(self):
        # Its ID is derived from where the test is, so a repeat is the same
        # case twice; collapsing them would silently lose evidence.
        suites = [
            {"name": "s", "testcases": [_case(), _case("test_y")]},
            {"name": "s", "testcases": [_case()]},
        ]
        with pytest.raises(ValueError, match="1 test case.*testcase__Suite__test_x"):
            build_needs_file(suites)

    def test_distinct_cases_are_all_kept(self):
        suites = [{"name": "s", "testcases": [_case(), _case("test_y")]}]
        payload = build_needs_file(suites)
        assert payload["versions"]["1.0"]["needs_amount"] == 2


class TestPropertyCollisions:
    def test_a_property_named_like_a_builtin_field_warns_and_is_dropped(self):
        reported = []
        need = build_need(
            "s",
            _case(properties={"result": "tampered", "owner": "me"}),
            warn=reported.append,
        )
        assert need["result"] != "tampered"
        assert need["owner"] == "me"
        assert len(reported) == 1
        assert "'result'" in reported[0]

    def test_without_a_reporter_the_property_is_still_dropped(self):
        need = build_need("s", _case(properties={"file": "elsewhere.py"}))
        assert need["file"] == "t.py"


class TestRemoteUrls:
    @pytest.mark.parametrize(
        ("remote", "base"),
        [
            (
                "ssh://git@gitlab.example.com:2222/org/repo.git",
                "https://gitlab.example.com/org/repo",
            ),
            ("ssh://git@github.com/org/repo.git", "https://github.com/org/repo"),
            ("git@github.com:org/repo.git", "https://github.com/org/repo"),
            ("https://github.com/org/repo.git/", "https://github.com/org/repo"),
            ("gitlab.example.com/org/repo", "https://gitlab.example.com/org/repo"),
        ],
    )
    def test_remotes_normalise_to_a_browsable_base(self, remote, base):
        # An ssh port belongs to the ssh endpoint, not the web UI -- and must
        # not be mistaken for the first path segment.
        assert normalise_remote_url(remote) == base

    def test_without_a_line_the_anchor_is_dropped(self):
        assert (
            source_url("https://h/r", "abc", "f.py", "") == "https://h/r/blob/abc/f.py"
        )

    def test_without_a_line_a_fragment_without_the_line_is_kept(self):
        url = source_url(
            "https://h/r", "abc", "f.py", "", "{base}/{file}?ref={commit}#src"
        )
        assert url == "https://h/r/f.py?ref=abc#src"

    def test_without_a_line_a_query_pattern_keeps_its_shape(self):
        url = source_url(
            "https://h/r", "abc", "f.py", "", "{base}/{file}?ref={commit}&line={line}"
        )
        assert url == "https://h/r/f.py?ref=abc&line="
