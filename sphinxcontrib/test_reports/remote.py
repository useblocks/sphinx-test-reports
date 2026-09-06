"""Web URLs for test sources.

Sphinx-free, like every module the converter CLI depends on.

Only the small amount of URL handling the converter actually needs lives here:
normalising a git remote into a browsable base, and formatting a line-anchored
source URL. sphinx-codelinks carries a fuller implementation (giturlparse-based,
covering more forges); when the two extensions are consolidated the machinery
should be shared rather than duplicated -- which is why this stays deliberately
minimal instead of growing a second forge matrix.
"""

import re

#: GitHub and GitHub-compatible forges. GitLab needs ``{base}/-/blob/...``.
DEFAULT_URL_PATTERN = "{base}/blob/{commit}/{file}#L{line}"

#: The part after ``scheme://`` of an ``ssh://`` or ``git://`` remote:
#: ``[user@]host[:port]/org/repo[.git]``. The port belongs to the transport
#: endpoint, not to the web UI, so it must not survive into the browsable base
#: -- and must not be mistaken for the first path segment.
_SCHEME_REMOTE = re.compile(
    r"^(?:[^@/]+@)?(?P<host>[^:/]+)(?::\d+)?/(?P<path>.+?)(?:\.git)?/?$"
)

#: ``git@host:org/repo.git`` and bare ``host/org/repo``.
_SCP_STYLE = re.compile(r"^(?:[^@/]+@)?(?P<host>[^:/]+)[:/](?P<path>.+?)(?:\.git)?/?$")

#: Placeholders a URL pattern may use, with representative values for checking
#: a pattern before any need is built.
_PATTERN_FIELDS = {"base": "https://h/r", "commit": "c", "file": "f", "line": "1"}


def normalise_remote_url(remote_url: str) -> str:
    """Turn a git remote into a browsable ``https`` base URL.

    An already-browsable URL is returned unchanged apart from a trailing
    ``.git``/``/``; ``ssh://`` and ``git://`` remotes and scp-style
    ``git@host:path`` become ``https://host/path``. Anything unrecognised -- an
    unknown scheme, a shape none of the patterns match -- is passed through, so
    an explicitly configured base is never mangled.
    """
    url = remote_url.strip()
    if not url:
        return ""

    scheme, separator, rest = url.partition("://")
    if separator:
        if scheme in ("http", "https"):
            return url.rstrip("/").removesuffix(".git")
        if scheme in ("ssh", "git"):
            match = _SCHEME_REMOTE.match(rest)
            if match is not None:
                return f"https://{match.group('host')}/{match.group('path')}"
        return url.rstrip("/")

    match = _SCP_STYLE.match(url)
    if match is None:
        return url.rstrip("/")
    return f"https://{match.group('host')}/{match.group('path')}"


def check_url_pattern(pattern: str) -> str | None:
    """Why *pattern* cannot be used as a source-URL template, or ``None``.

    ``str.format`` only fails when a URL is actually built -- that is, on the
    first case that carries a file -- and it fails with a traceback. Checking
    the template up front turns a typo in a flag or in ``ubproject.toml`` into
    a configuration error at the start of the run.
    """
    try:
        pattern.format(**_PATTERN_FIELDS)
    except KeyError as error:
        allowed = ", ".join(f"{{{name}}}" for name in _PATTERN_FIELDS)
        missing = str(error).strip("'")  # KeyError's str is the quoted key
        return f"unknown placeholder {{{missing}}}; the placeholders are {allowed}"
    except (IndexError, ValueError) as error:
        return f"malformed template ({error}); braces must be balanced and named"
    return None


def source_url(
    base_url: str,
    commit: str,
    file: str,
    line: str,
    pattern: str = DEFAULT_URL_PATTERN,
) -> str:
    """Line-anchored URL of a test source, or ``""`` without repo metadata.

    A hermetic build has no git remote, so the absence of metadata must yield an
    empty field rather than a placeholder URL that looks real and 404s.
    When the line is unknown the anchor is dropped instead of pointing at a
    fabricated line.
    """
    if not base_url or not commit or not file:
        return ""

    if not line:
        # Drop the fragment only when the anchor lives there. A pattern that
        # carries the line elsewhere keeps its shape and gets an empty value,
        # instead of losing whatever else followed the ``#``.
        head, hash_sign, fragment = pattern.partition("#")
        if hash_sign and "{line}" in fragment:
            pattern = head
    return pattern.format(base=base_url, commit=commit, file=file, line=line)
