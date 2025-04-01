import nox
from nox import session

PYTHON_VERSIONS = ["3.10", "3.12"]
SPHINX_VERSIONS = ["5.0", "7.2.5", "8.1.3"]
SPHINX_NEEDS_VERSIONS = ["2.1", "4.2"]
LINT_DEPENDENCIES = [
    "flake8",
    "pep8-naming",
    "flake8-isort",
    "flake8-black",
]


def is_supported(python: str, sphinx: str) -> bool:
    return not (python == "3.6" and float(sphinx) > 3.0)  # fmt: skip


def run_tests(session, sphinx, sphinx_needs):
    session.install(".[test]")
    session.run("pip", "install", f"sphinx=={sphinx}", silent=True)
    session.run("pip", "install", f"sphinx_needs=={sphinx_needs}", silent=True)
    session.run("make", "test", external=True)


@session(python=PYTHON_VERSIONS)
@nox.parametrize("sphinx_needs", SPHINX_NEEDS_VERSIONS)
@nox.parametrize("sphinx", SPHINX_VERSIONS)
def tests(session, sphinx_needs, sphinx):
    if is_supported(session.python, sphinx):
        run_tests(session, sphinx, sphinx_needs)
    else:
        session.skip("unsupported combination")


@session(python="3.12")
def lint(session):
    session.install(*LINT_DEPENDENCIES)
    session.run("make", "lint", external=True)


@session(python="3.12")
def linkcheck(session):
    session.install(".[docs]")
    session.run("make", "docs-linkcheck", external=True)
