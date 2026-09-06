"""``test-reports`` command line interface.

Converts test-result XML into needs.json *outside* Sphinx, so a build system can
schedule and cache the conversion and the documentation build only imports the
result. Nothing in the import chain of this module may import Sphinx; the test
suite asserts that.

The conversion settings come from three places, highest precedence first: a
command-line flag, the ``[test_reports.convert]`` table of the project's
``ubproject.toml``, the built-in default. The file is the declarative
description of the project that the Sphinx build reads too, so the two
consumers cannot drift apart; the flags stay for per-invocation values such as
the commit a CI job is converting for.
"""

import argparse
import json
import sys
from pathlib import Path

from sphinxcontrib.test_reports.junitparser import JUnitParser
from sphinxcontrib.test_reports.needs_export import DEFAULT_VERSION, build_needs_file
from sphinxcontrib.test_reports.projectconfig import (
    CONVERSION_KEYS,
    CONVERT_TABLE,
    DEFAULT_TOML_FILENAME,
    SECTION,
    TomlConfigError,
    case_need_type,
    find_project_config,
    load_project_config,
)
from sphinxcontrib.test_reports.remote import DEFAULT_URL_PATTERN, normalise_remote_url

#: How the table is spelled in help texts and diagnostics.
TABLE = f"[{SECTION}.{CONVERT_TABLE}]"


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="test-reports",
        description="Convert test-result XML into sphinx-needs data.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    convert = subcommands.add_parser(
        "convert",
        help="Convert one or more test-result XML files into needs.json.",
        description=(
            "Convert one or more test-result XML files into a needs.json that "
            "can be consumed with needimport or needs_external_needs. Settings "
            f"default to the {TABLE} table of {DEFAULT_TOML_FILENAME}; a flag "
            "overrides the file's value for that key."
        ),
    )
    convert.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="Test-result XML files (a build system passes these as a file list).",
    )
    convert.add_argument(
        "--output",
        "-o",
        required=True,
        metavar="PATH",
        help="Where to write the needs.json.",
    )
    # Every setting the TOML file can supply defaults to None here and is
    # resolved in _resolve_settings: a given flag beats the file, which beats
    # the built-in default. None is safe because each key resolves to a
    # concrete value there.
    convert.add_argument(
        "--project",
        default=None,
        help="Project name recorded in the needs.json envelope (default: empty).",
    )
    convert.add_argument(
        "--version",
        default=None,
        help=f"Version key in the envelope (default: {DEFAULT_VERSION}).",
    )
    convert.add_argument(
        "--need-type",
        default=None,
        help="Need type for each test case (default: testcase).",
    )
    convert.add_argument(
        "--tags",
        default=None,
        help="Comma-separated tags applied to every created need.",
    )
    convert.add_argument(
        "--link-property",
        action="append",
        default=None,
        metavar="PROPERTY=LINK_FIELD",
        help=(
            "Promote an XML property to a link field, comma-splitting its value "
            "(repeatable), e.g. PartiallyVerifies=partially_verifies. Given at "
            "all, it replaces the file's link_properties table."
        ),
    )
    convert.add_argument(
        "--remote-url",
        default=None,
        help="Repository URL used to synthesize source links; git remotes are accepted.",
    )
    convert.add_argument(
        "--commit",
        default=None,
        help="Commit-ish the reports were produced from.",
    )
    convert.add_argument(
        "--url-pattern",
        default=None,
        help=f"Source-URL template (default: {DEFAULT_URL_PATTERN}).",
    )
    config_source = convert.add_mutually_exclusive_group()
    config_source.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help=(
            f"Declarative config file to read the {TABLE} table from. By "
            f"default {DEFAULT_TOML_FILENAME} is searched for in the working "
            "directory and its parents, up to the project root; an explicitly "
            "given path is used as-is and must exist."
        ),
    )
    config_source.add_argument(
        "--no-config",
        action="store_true",
        help=(
            "Ignore the declarative config file entirely, so the output "
            "depends only on the arguments given here."
        ),
    )
    return parser


def _parse_link_properties(
    values: "list[str] | dict[str, str] | None",
) -> dict[str, str]:
    """Normalise the link-property mapping from any input spelling.

    Flags provide ``PROPERTY=LINK_FIELD`` strings; the TOML file provides a
    ``PROPERTY = "LINK_FIELD"`` table; neither given is ``None``. Both spellings
    must yield non-empty keys and values -- a silently dropped mapping would
    send link fields into needs.json as plain fields instead. This is the only
    place the mapping is normalised, so the two spellings cannot drift.
    """
    if values is None:
        return {}
    if isinstance(values, dict):
        mapping = {}
        for property_name, link_field in values.items():
            if not str(property_name).strip() or not str(link_field).strip():
                raise ValueError(
                    f'link_properties expects PROPERTY = "LINK_FIELD", got '
                    f"{property_name!r} = {link_field!r}"
                )
            mapping[str(property_name).strip()] = str(link_field).strip()
        return mapping

    mapping = {}
    for value in values:
        property_name, separator, link_field = value.partition("=")
        if not separator or not property_name.strip() or not link_field.strip():
            raise ValueError(
                f"--link-property expects PROPERTY=LINK_FIELD, got {value!r}"
            )
        mapping[property_name.strip()] = link_field.strip()
    return mapping


def _warn_about_absent_source_lines(path: Path, suites: list) -> None:
    """Report the most common cause of a missing source location.

    pytest emits ``file``/``line`` as ``<testcase>`` attributes only under
    ``junit_family = xunit1`` (or ``legacy``); its default ``xunit2`` filters
    them out, which silently costs the source location of every case.
    """
    cases = [case for suite in suites for case in suite.get("testcases", [])]
    if cases and all(case.get("line", -1) == -1 for case in cases):
        print(
            f"warning: {path}: no <testcase> carries a 'line' attribute, so no "
            "source location could be recorded. pytest emits file/line only "
            "with junit_family = xunit1 (or legacy); its default xunit2 drops "
            "them.",
            file=sys.stderr,
        )


def _load_section(
    arguments: argparse.Namespace,
) -> "tuple[dict, Path | None, str | None]":
    """Load the ``[test_reports]`` section, honouring ``--config``/``--no-config``.

    Returns ``(section, path, error_message)``. ``section`` is ``{}`` and
    ``path`` ``None`` when no file applies: an absent *default* file is not an
    error, an explicitly given path that cannot be read is.

    The whole section is loaded, not only the converter's table: validation
    covers the file as the build sees it, and the build's ``case`` entry is
    needed to check the need type against.

    The default file is searched for upwards from the working directory, since
    it conventionally sits at the project root while the converter runs from
    wherever CI invoked it. That is also where the Sphinx side looks, so both
    consumers read the same file.
    """
    if arguments.no_config:
        return {}, None, None

    if arguments.config is not None:
        path = Path(arguments.config)
        if not path.is_file():
            return {}, None, f"error: no such config file: {path}"
    else:
        found = find_project_config(Path.cwd())
        if found is None:
            return {}, None, None
        path = found

    try:
        section = load_project_config(path, _warn) or {}
    except TomlConfigError as error:
        return {}, path, f"error: {error}"
    return section, path, None


#: Built-in value of every conversion setting, used when neither a flag nor
#: the TOML file supplies one. Keyed by :data:`CONVERSION_KEYS`, and checked
#: against it at import time, so a key cannot be added to the table without
#: also being given a default here.
_DEFAULTS: "dict[str, object]" = {
    "project": "",
    "version": DEFAULT_VERSION,
    "need_type": "testcase",
    "tags": "",
    "link_properties": None,
    "remote_url": "",
    "commit": "",
    "url_pattern": DEFAULT_URL_PATTERN,
}
if set(_DEFAULTS) != set(CONVERSION_KEYS):  # pragma: no cover - import-time guard
    raise RuntimeError("every [test_reports.convert] key needs a built-in default")

#: argparse destination per conversion key, where it differs from the key.
#: Only the repeatable ``--link-property`` flag does.
_DESTS = {"link_properties": "link_property"}

#: Command-line spelling of a conversion key, for diagnostics.
_FLAGS = {key: "--" + key.replace("_", "-") for key in CONVERSION_KEYS}
_FLAGS["link_properties"] = "--link-property"


def _resolve_settings(
    arguments: argparse.Namespace, table: dict
) -> "tuple[dict, dict[str, str]]":
    """Merge the conversion settings: flag > TOML table > built-in default.

    Flags default to ``None``, so ``None`` means "not given"; every key resolves
    to a concrete value here. Also returns, per key, where the value came from,
    because a diagnostic has to name the flag or the TOML key the user actually
    wrote.
    """
    resolved: "dict[str, object]" = {}
    sources: "dict[str, str]" = {}
    for key in CONVERSION_KEYS:
        flag = getattr(arguments, _DESTS.get(key, key))
        if flag is not None:
            resolved[key], sources[key] = flag, "flag"
        elif key in table:
            resolved[key], sources[key] = table[key], "toml"
        else:
            resolved[key], sources[key] = _DEFAULTS[key], "default"

    tags = resolved["tags"]
    if isinstance(tags, str):  # comma-separated, from the flag
        resolved["tags"] = [tag.strip() for tag in tags.split(",") if tag.strip()]
    else:  # array from the TOML file
        resolved["tags"] = [str(tag) for tag in tags or []]

    return resolved, sources


def _spell(key: str, sources: "dict[str, str]") -> str:
    """The key as the user wrote it: the flag, the TOML key, or the default."""
    source = sources.get(key)
    if source == "toml":
        return key
    if source == "default":
        return f"the default {key}"
    return _FLAGS[key]


def _pair_requirement(sources: "dict[str, str]", path: "Path | None") -> str:
    """Name the remote-url/commit pair the way the user actually spelled it.

    Either half can come from the TOML file, so naming only the flags would
    point at options that appear nowhere in the invocation.
    """
    # The half that is missing is named by the flag that would supply it --
    # that is the actionable spelling -- and the half that was given by however
    # the user gave it.
    names = [
        key if sources.get(key) == "toml" else _FLAGS[key]
        for key in ("remote_url", "commit")
    ]
    requirement = f"{names[0]} and {names[1]}"
    if "toml" in (sources.get("remote_url"), sources.get("commit")):
        requirement += f" (the bare names are {TABLE} keys in {path})"
    return requirement


def _convert(arguments: argparse.Namespace) -> int:
    section, config_path, error = _load_section(arguments)
    if error:
        print(error, file=sys.stderr)
        return 2

    table = section.get(CONVERT_TABLE, {})
    settings, sources = _resolve_settings(
        arguments, table if isinstance(table, dict) else {}
    )

    # The loader already rejects a file whose convert.need_type disagrees with
    # case's type. A --need-type flag (or the default) is not in the file, so
    # the merged value has to be checked here as well, or the converter writes
    # needs of a type the build does not register.
    case_type = case_need_type(section)
    if case_type is not None and settings["need_type"] != case_type:
        print(
            f"error: {_spell('need_type', sources)} is {settings['need_type']!r} "
            f"but [{SECTION}] case's type is {case_type!r} in {config_path}. Both "
            f"name the need type of a test case -- need_type for this converter, "
            f"case for the Sphinx build -- so they must agree.",
            file=sys.stderr,
        )
        return 2

    try:
        link_properties = _parse_link_properties(settings["link_properties"])
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if bool(settings["remote_url"]) != bool(settings["commit"]):
        print(
            f"error: {_pair_requirement(sources, config_path)} must be given "
            f"together; without both, no source URL can be synthesized.",
            file=sys.stderr,
        )
        return 2

    suites: list = []
    for name in arguments.files:
        path = Path(name)
        if not path.is_file():
            print(f"error: no such file: {path}", file=sys.stderr)
            return 1
        try:
            parsed = JUnitParser(str(path)).parse()
        except Exception as error:  # noqa: BLE001 - report, never traceback
            print(f"error: {path}: {error}", file=sys.stderr)
            return 1
        _warn_about_absent_source_lines(path, parsed)
        suites.extend(parsed)

    try:
        payload = build_needs_file(
            suites,
            project=settings["project"],
            version=settings["version"],
            need_type=settings["need_type"],
            tags=settings["tags"],
            link_properties=link_properties,
            base_url=normalise_remote_url(settings["remote_url"]),
            commit=settings["commit"],
            url_pattern=settings["url_pattern"],
            warn=_warn,
        )
    except ValueError as error:  # duplicate test cases across the inputs
        print(f"error: {error}", file=sys.stderr)
        return 2

    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Sorted keys and a fixed indent keep the output byte-stable across runs.
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def main(argv: "list[str] | None" = None) -> int:
    """Entry point. Returns a process exit code instead of raising."""
    arguments = _build_parser().parse_args(argv)
    if arguments.command == "convert":
        return _convert(arguments)
    return 2  # pragma: no cover - argparse rejects unknown commands


if __name__ == "__main__":
    sys.exit(main())
