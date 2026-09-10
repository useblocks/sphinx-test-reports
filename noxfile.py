import nox
from nox import session

PYTHON_VERSIONS = ["3.11", "3.12"]
SPHINX_VERSIONS = ["7.4.7", "8.1.3"]
SPHINX_NEEDS_VERSIONS = ["6.0.1", "6.3.0", "7.0.0", "8.0.0", "8.5.0"]


def run_tests(session, sphinx, sphinx_needs):
    session.install(".[test]")
    session.run("pip", "install", f"sphinx=={sphinx}", silent=True)
    session.run("pip", "install", f"sphinx_needs=={sphinx_needs}", silent=True)
    session.run("make", "test", external=True)


@session(python=PYTHON_VERSIONS)
@nox.parametrize("sphinx_needs", SPHINX_NEEDS_VERSIONS)
@nox.parametrize("sphinx", SPHINX_VERSIONS)
def tests(session, sphinx_needs, sphinx):
    run_tests(session, sphinx, sphinx_needs)


#: The oldest pytest the plugin's tests run on, per Python: 7.0 is the plugin's
#: own floor (the pytest extra), and 7.3.2 the first pytest that runs on
#: Python 3.12 at all.
PLUGIN_PYTEST_FLOORS = [("3.11", "7.0.1"), ("3.12", "7.3.2")]


@session
@nox.parametrize("python,pytest_version", PLUGIN_PYTEST_FLOORS)
def plugin_floor(session, pytest_version):
    """The pytest plugin's tests on the oldest pytest it supports."""
    session.install(".[test]", f"pytest=={pytest_version}")
    session.run("pytest", "tests/test_pytest_plugin.py")


# The converter and its configuration run without the documentation toolchain,
# and these are their tests. Everything else builds documentation.
TOOLCHAIN_FREE_TESTS = [
    "tests/test_cli_config.py",
    "tests/test_cli_convert.py",
    "tests/test_identity.py",
    "tests/test_junit_parser.py",
    "tests/test_junit_parser_gtest.py",
    "tests/test_needs_export.py",
    "tests/test_project_config.py",
    "tests/test_toolchain.py",
]

# Exits non-zero, naming them, if any module of the toolchain is importable.
TOOLCHAIN_IS_ABSENT = (
    "import importlib.util, sys;"
    "present = [m for m in ('sphinx', 'sphinx_needs', 'docutils')"
    " if importlib.util.find_spec(m)];"
    "sys.exit(f'toolchain installed: {present}' if present else 0)"
)


@session(python=PYTHON_VERSIONS)
def toolchain_free(session):
    """Run the converter's tests in an environment without Sphinx.

    The package is installed with the dependencies it declares -- `lxml` --
    plus pytest, so a toolchain import creeping into the converter's import
    chain, or Sphinx creeping back into the dependency list, fails here. The
    tests that need a documentation build carry the `toolchain` mark.
    """
    session.install(".", "pytest")
    session.run("python", "-c", TOOLCHAIN_IS_ABSENT)
    session.run(
        "pytest", "-m", "not toolchain", *TOOLCHAIN_FREE_TESTS, *session.posargs
    )


@session(python="3.12")
def linkcheck(session):
    session.install(".[docs]")
    with session.chdir("docs"):
        session.run("make", "linkcheck", external=True)
