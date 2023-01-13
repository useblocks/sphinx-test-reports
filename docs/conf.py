#
# Configuration file for the Sphinx documentation builder.
#
# This file does only contain a selection of the most common options. For a
# full list see the documentation:
# http://www.sphinx-doc.org/en/stable/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
import sys
import datetime
import os

sys.path.append(os.path.abspath('.'))

from ub_theme.conf import html_theme_options

# -- Project information -----------------------------------------------------

project = "sphinx-test-reports"
now = datetime.datetime.now()
copyright = 'team useblocks, 2017-{year}'.format(
    year=now.year
)
author = "team useblocks"

# The short X.Y version
version = "1.0"
# The full version, including alpha/beta/rc tags
release = "1.0.2"


# -- General configuration ---------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx_needs",
    "sphinxcontrib.test_reports",
    "sphinxcontrib.plantuml",
    "sphinx_design",
    "sphinx_immaterial"
]

cwd = os.getcwd()
plantuml = "java -jar %s" % os.path.join(cwd, "utils/plantuml.jar")

# If we are running on windows, we need to manipulate the path,
# otherwise plantuml will have problems.
if os.name == "nt":
    plantuml = plantuml.replace("/", "\\")
    plantuml = plantuml.replace("\\", "\\\\")

plantuml_output_format = "png"


# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates', 'ub_theme/templates']
# Add a custom test report template. Please add a relative path from this conf.py
# tr_report_template = "./custom_test_report_template.txt"

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path .
exclude_patterns = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_immaterial"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
html_logo = "_static/sphinx-test-reports-logo.png"
html_title = "Sphinx-Test-Reports"
html_theme_options = html_theme_options

other_options = {
    "repo_url": "https://github.com/useblocks/sphinx-test-reports",
    "repo_name": "sphinx-test-reports",
    "repo_type": "github",
}
html_theme_options.update(other_options)
html_theme_options["features"].extend(["navigation.tabs", "navigation.tabs.sticky"])
# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static", "ub_theme/css"]
html_css_files = ['ub-theme.css']

# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "sphinx-test-reportsdoc"


# -- Options for LaTeX output ------------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',
    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (
        master_doc,
        "sphinx-test-reports.tex",
        "sphinx-test-reports Documentation",
        "team useblocks",
        "manual",
    ),
]


# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (
        master_doc,
        "sphinx-test-reports",
        "sphinx-test-reports Documentation",
        [author],
        1,
    )
]


# -- Options for Texinfo output ----------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "sphinx-test-reports",
        "sphinx-test-reports Documentation",
        author,
        "sphinx-test-reports",
        "One line description of project.",
        "Miscellaneous",
    ),
]

# LINKCHECK config
# https://www.sphinx-doc.org/en/master/usage/configuration.html?highlight=linkcheck#options-for-the-linkcheck-builder
linkcheck_ignore = [
    r"http://localhost:\d+",
    r"http://127.0.0.1:\d+",
]

linkcheck_request_headers = {
    "*": {
        "User-Agent": "Mozilla/5.0",
    }
}

linkcheck_workers = 5
