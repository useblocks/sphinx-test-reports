"""Declarative project configuration for sphinx-test-reports.

Reads the ``[test_reports]`` section of a project's ``ubproject.toml`` -- the
declarative file shared with the other useblocks tooling (sphinx-needs,
sphinx-codelinks, sphinx-mounts, ubCode) -- so that a project is described once
instead of being restated in every tool that acts on it.

**Nothing in this module may import Sphinx.** The section describes the project,
not this extension, and a report-to-``needs.json`` converter has to be able to
read it as a build action without the documentation toolchain installed.

The keys are the Sphinx-facing configuration (:data:`BRIDGE_KEYS`), spelled
like the ``tr_*`` config values without the prefix. The section may also carry
sub-tables for tools other than the Sphinx extension -- a report converter
reads ``[test_reports.convert]`` -- which this reader does not interpret.

**Error policy.** A known key carrying the wrong type is fatal: that is the
typo class this validation exists to catch, and letting it through would
silently change what gets produced. An *unknown* key is only reported. The
file is shared with tools on independent release cadences, so a key this
reader does not model is routine rather than a mistake -- and aborting on it
would take down every build of the project on every older sphinx-test-reports,
including builds the key would not have changed. This is the same posture
sphinx-mounts takes for ``[[source.mounts]]``.
"""

import tomllib
from pathlib import Path
from typing import Callable, Mapping, NoReturn, Sequence

#: Default file the configuration is read from. Looked up by walking up from
#: the ``confdir`` (Sphinx) or the working directory (a converter); see
#: :func:`find_project_config`. ``ubproject.toml`` is the convention shared
#: with other useblocks tooling so a single declarative file describes the
#: project to every downstream consumer -- Sphinx, ubCode, a converter --
#: without
#: any of them having to execute Python.
DEFAULT_TOML_FILENAME = "ubproject.toml"

#: The section this extension owns inside the shared file. Spelled
#: ``snake_case`` like every other section of ``ubproject.schema.json``
#: (``build_tags``, ``format_rst``, ``needs_json``, ``rst_lint``, ...); note
#: that ``[reports]`` is already taken, and means report *templates*.
SECTION = "test_reports"

#: Directory entries that end the upward search of
#: :func:`find_project_config`. A directory carrying one of these is a project
#: root, so a consumer below it must not silently adopt the configuration of
#: an unrelated parent project. ``ubproject.toml`` itself is not listed --
#: finding it is the success case, checked first.
_ROOT_MARKERS = (".git", "pyproject.toml")

#: Section keys bridged onto their ``tr_*`` Sphinx config values.
BRIDGE_KEYS = (
    "file",
    "suite",
    "case",
    "file_option",
    "source_file_option",
    "source_line_option",
    "rootdir",
    "report_template",
    "suite_id_length",
    "case_id_length",
    "import_encoding",
    "extra_options",
    "property_link_types",
    "json_mapping",
    "deterministic_case_ids",
)

#: Keys holding a path. Relative values are anchored against the directory
#: containing the TOML file, not against ``confdir`` or the process working
#: directory: the file is self-describing, and moving it as a unit keeps its
#: relative paths meaningful. It also makes every consumer resolve a
#: relative path identically.
PATH_KEYS = ("rootdir", "report_template")

#: The keys whose need-type setting accepts both the positional ``conf.py``
#: list and a named table; :func:`_normalise_type_entry` reduces both to the
#: list form. ``None`` in :data:`_KEY_TYPES` marks exactly these.
_DUAL_SPELLING_KEYS = ("file", "suite", "case")

#: Sub-tables of the section that belong to another consumer. They are
#: recognised so they do not draw an unknown-key warning, and deliberately not
#: interpreted: ``convert`` holds the settings for turning test reports into a
#: ``needs.json`` outside Sphinx, which this extension never does.
FOREIGN_TABLES = ("convert",)

#: Expected Python type per key. ``bool`` must be checked *before* ``int``
#: (bool is an int subclass). ``None`` marks the dual-spelling keys, which are
#: normalised separately; path keys are validated as ``str`` and anchored
#: afterwards.
_KEY_TYPES: dict[str, type[object] | None] = {
    "file": None,
    "suite": None,
    "case": None,
    "file_option": str,
    "source_file_option": str,
    "source_line_option": str,
    "rootdir": str,
    "report_template": str,
    "suite_id_length": int,
    "case_id_length": int,
    "import_encoding": str,
    "extra_options": list,
    "property_link_types": dict,
    "json_mapping": dict,
    "deterministic_case_ids": bool,
    "convert": dict,
}

#: Required type of the *values* inside a table-valued key. Without this a
#: table passes validation on its outer shape alone, and a mistake such as
#: ``property_link_types = { request = ["req"] }`` reaches the directives,
#: which fail with a bare ``TypeError`` on an unhashable field name.
#: ``None`` means the nested shape is free-form -- ``json_mapping`` mirrors an
#: arbitrary parser mapping -- so only the outer table is checked.
_DICT_VALUE_TYPES: dict[str, type[object] | None] = {
    "property_link_types": str,
    "json_mapping": None,
    "convert": None,
}

#: Field order of the positional ``tr_file``-style lists, and the table keys
#: that spell the same thing readably.
_TYPE_ENTRY_FIELDS = ("directive", "type", "name", "prefix", "color", "style")

#: ``tomllib.TOMLDecodeError`` bound through an annotation: the attribute
#: expression itself is typed loosely enough to trip the strict ``Any`` bans,
#: and an ``except`` clause has no annotation of its own to absorb it.
_TOML_DECODE_ERROR: type[Exception] = tomllib.TOMLDecodeError


class TomlConfigError(Exception):
    """Raised when the declarative config cannot be parsed or is malformed.

    Deliberately *not* a ``SphinxError``: this module must stay importable
    without Sphinx. The Sphinx-side bridge re-raises it as an
    ``InvalidConfigurationError`` to abort the build; a non-Sphinx consumer
    reports it and exits non-zero.
    """


def find_project_config(
    start: Path, filename: str = DEFAULT_TOML_FILENAME
) -> Path | None:
    """Search *start* and its parents for *filename*.

    The declarative file conventionally sits at the project root while its
    consumers run from below it -- ``conf.py`` in ``docs/``, a build action
    from wherever CI invoked it -- so anchoring strictly at the caller's own
    directory would leave the shared file unread by one of them, silently.

    The walk stops at the first directory holding *filename*, and at a
    directory that looks like a project root (:data:`_ROOT_MARKERS`) even when
    it does not hold the file, so a consumer never adopts the configuration of
    an unrelated parent project.

    :return: The file, or ``None`` when the search reached a project root or
        the filesystem root without finding one.
    """
    for directory in (start, *start.parents):
        candidate = directory / filename
        if candidate.is_file():
            return candidate
        if any((directory / marker).exists() for marker in _ROOT_MARKERS):
            return None
    return None


def load_project_config(
    path: Path, warn: Callable[[str], None] | None = None
) -> dict[str, object] | None:
    """Read and normalise the ``[test_reports]`` section of a TOML file.

    :param path: Absolute path to the TOML file (``ubproject.toml`` or whatever
        the caller resolved).
    :param warn: Called with a message for every non-fatal problem -- today,
        an unknown key. Callers pass their own logger so this module stays
        Sphinx-free; ``None`` discards the reports.
    :return: The normalised section as a plain dict; ``None`` when the file
        does not exist (an absence is not an error -- callers decide whether
        that is fine, e.g. neither consumer minds a missing *default* file but
        both complain about an explicitly given one). An existing file without
        the section yields ``{}``.
    :raises TomlConfigError: If the file cannot be read, is not valid TOML, the
        section has the wrong shape, or a known key has the wrong type.
    """
    if not path.is_file():
        return None
    data = _read_toml(path)

    section = data.get(SECTION)
    if section is None:
        return {}
    if not isinstance(section, dict):
        msg = f"{path}: [{SECTION}] must be a table, got {type(section).__name__}"
        raise TomlConfigError(msg)

    return _normalise_section(section, path, warn)


def _read_toml(path: Path) -> dict[str, object]:
    """Parse *path*, reporting every read failure as a ``TomlConfigError``.

    ``is_file()`` succeeding does not mean the open will: the file may be
    unreadable, or replaced between the check and the open. Both consumers
    handle ``TomlConfigError`` and neither handles a bare ``OSError``, so an
    unwrapped one surfaces as a traceback instead of a configuration error.
    """
    try:
        with path.open("rb") as handle:
            # tomllib is typed ``-> dict[str, Any]``; everything downstream of
            # here is ``object`` so the strict Any bans hold for the rest of
            # the module.
            data: dict[str, object] = tomllib.load(handle)
    except _TOML_DECODE_ERROR as error:
        msg = f"{path}: invalid TOML: {error}"
        raise TomlConfigError(msg) from error
    except OSError as error:
        msg = f"{path}: cannot be read: {error}"
        raise TomlConfigError(msg) from error
    return data


def _normalise_section(
    section: Mapping[str, object], path: Path, warn: Callable[[str], None] | None
) -> dict[str, object]:
    """Validate every key and return a normalised copy of *section*.

    Normalisation: relative paths become absolute (anchored at the TOML file's
    directory), the ``file``/``suite``/``case`` need-type settings accept both
    the positional-list spelling of ``conf.py`` and a named table.

    Unknown keys are reported through *warn* and dropped -- see the module
    docstring for why they are not fatal.
    """
    unknown = sorted(set(section) - set(_KEY_TYPES))
    if unknown and warn is not None:
        warn(
            f"{path}: ignoring unknown key(s) in [{SECTION}]: "
            f"{', '.join(unknown)}. Supported keys: "
            f"{', '.join(sorted(_KEY_TYPES))}"
        )

    normalised: dict[str, object] = {}
    for key, value in section.items():
        if key in unknown:
            continue
        expected = _KEY_TYPES[key]
        # bool first: bool is an int subclass, and for int keys a TOML
        # ``true`` must be rejected, not silently accepted.
        if expected is int and isinstance(value, bool):
            _wrong_type(key, value, expected, path)
        if expected is not None and not isinstance(value, expected):
            _wrong_type(key, value, expected, path)
        if key in FOREIGN_TABLES:
            normalised[key] = value
        elif key in _DUAL_SPELLING_KEYS:
            normalised[key] = _normalise_type_entry(key, value, path)
        else:
            if expected is list:
                _check_list_items(key, value, path)
            elif expected is dict:
                _check_table_values(key, value, path)
            normalised[key] = value

    return _anchor_paths(normalised, path.parent)


def _check_list_items(key: str, value: object, path: Path) -> None:
    """Every element of an array-valued key must be a string."""
    if not isinstance(value, Sequence):
        return
    for item in value:
        if not isinstance(item, str):
            _wrong_type(key, value, list, path)


def _check_table_values(key: str, value: object, path: Path) -> None:
    """Every value of a table-valued key must have the declared type.

    Skipped for keys whose nested shape is free-form (:data:`_DICT_VALUE_TYPES`
    maps them to ``None``).
    """
    expected = _DICT_VALUE_TYPES.get(key)
    if expected is None or not isinstance(value, Mapping):
        return
    for name, item in value.items():
        if not isinstance(item, expected):
            msg = (
                f"{path}: [{SECTION}] {key}.{name} must be "
                f"{_type_label(expected)}, got {type(item).__name__}: {item!r}"
            )
            raise TomlConfigError(msg)


def _wrong_type(
    key: str, value: object, expected: type[object] | None, path: Path
) -> NoReturn:
    msg = (
        f"{path}: [{SECTION}] {key} must be "
        f"{_type_label(expected)}, got {type(value).__name__}: {value!r}"
    )
    raise TomlConfigError(msg)


def _type_label(expected: type[object] | None) -> str:
    if expected is None:
        return "a 6-element array or a table"
    if expected is int:
        return "an integer"
    if expected is bool:
        return "a boolean"
    if expected is str:
        return "a string"
    if expected is list:
        return "an array of strings"
    if expected is dict:
        return "a table"
    return expected.__name__


def _normalise_type_entry(key: str, value: object, path: Path) -> list[str]:
    """The ``file``/``suite``/``case`` settings in one of two spellings.

    Positional (exactly what ``conf.py`` accepts)::

        file = ["test-file", "testfile", "Test-File", "TF_", "#ffffff", "node"]

    Named -- the recommended TOML spelling, since six bare strings in a row
    cannot be told apart::

        [test_reports.file]
        directive = "test-file"
        type = "testfile"
        name = "Test-File"
        prefix = "TF_"
        color = "#ffffff"
        style = "node"
    """
    if isinstance(value, list):
        entry = [item for item in value if isinstance(item, str)]
        if len(entry) != len(_TYPE_ENTRY_FIELDS) or len(entry) != len(value):
            msg = (
                f"{path}: [{SECTION}] {key} as an array must hold exactly "
                f"{len(_TYPE_ENTRY_FIELDS)} strings "
                f"({'/'.join(_TYPE_ENTRY_FIELDS)}), got {value!r}"
            )
            raise TomlConfigError(msg)
        return entry

    if isinstance(value, Mapping):
        table: dict[str, object] = {str(name): item for name, item in value.items()}
        missing = [field for field in _TYPE_ENTRY_FIELDS if field not in table]
        unknown = sorted(set(table) - set(_TYPE_ENTRY_FIELDS))
        wrong = sorted(
            field
            for field in _TYPE_ENTRY_FIELDS
            if field in table and not isinstance(table[field], str)
        )
        problems = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        if wrong:
            problems.append(f"non-string {', '.join(wrong)}")
        if problems:
            msg = (
                f"{path}: [{SECTION}] [{SECTION}.{key}]: "
                f"{'; '.join(problems)}. Expected the keys "
                f"{'/'.join(_TYPE_ENTRY_FIELDS)}."
            )
            raise TomlConfigError(msg)
        return [str(table[field]) for field in _TYPE_ENTRY_FIELDS]

    msg = (
        f"{path}: [{SECTION}] {key} must be a 6-element array or a table, "
        f"got {type(value).__name__}"
    )
    raise TomlConfigError(msg)


def _anchor_paths(section: dict[str, object], base: Path) -> dict[str, object]:
    """Resolve :data:`PATH_KEYS` against *base* (the TOML file's directory).

    Joined but deliberately not ``resolve()``d: *base* is already absolute, and
    resolving would collapse symlinks that the ``conf.py`` spelling of the same
    option preserves, so the two spellings would not name the same directory.
    """
    for key in PATH_KEYS:
        value = section.get(key)
        if isinstance(value, str) and not Path(value).is_absolute():
            section[key] = str(base / value)
    return section
