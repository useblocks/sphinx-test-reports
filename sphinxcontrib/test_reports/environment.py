import os

import sphinx
from packaging.version import Version
from sphinx.util.console import brown
from sphinx.util.osutil import copyfile, ensuredir

sphinx_version = sphinx.__version__
if Version(sphinx_version) >= Version("1.6"):
    if Version(sphinx_version) >= Version("6.1"):
        from sphinx.util.display import status_iterator
    else:
        from sphinx.util import status_iterator  # NOQA Sphinx 1.5

STATICS_DIR_NAME = "_static"


def safe_add_file(filename, app):
    """
    Adds files to builder resources only, if the given filename was not already registered.
    Needed mainly for tests to avoid multiple registration of the same file and therefore also multiple execution
    of e.g. a javascript file during page load.

    :param filename: filename to remove
    :param app: app object
    :return: None
    """
    data_file = filename
    static_data_file = os.path.join("_static", data_file)

    if data_file.split(".")[-1] == "js":
        if hasattr(app.builder, "script_files") and static_data_file not in app.builder.script_files:  # noqa: W503
            app.add_js_file(data_file)
    elif data_file.split(".")[-1] == "css":
        if hasattr(app.builder, "css_files") and static_data_file not in app.builder.css_files:  # noqa: W503
            app.add_css_file(data_file)
    else:
        raise NotImplementedError("File type {} not support by save_add_file".format(data_file.split(".")[-1]))


def safe_remove_file(filename, app):
    """
    Removes a given resource file from builder resources.
    Needed mostly during test, if multiple sphinx-build are started.
    During these tests js/cass-files are not cleaned, so a css_file from run A is still registered in run B.

    :param filename: filename to remove
    :param app: app object
    :return: None
    """
    data_file = filename
    static_data_file = os.path.join("_static", data_file)

    if data_file.split(".")[-1] == "js":
        if hasattr(app.builder, "script_files") and static_data_file in app.builder.script_files:  # noqa: W503
            app.builder.script_files.remove(static_data_file)
    elif data_file.split(".")[-1] == "css" and (
        hasattr(app.builder, "css_files") and static_data_file in app.builder.css_files  # noqa: W503
    ):
        app.builder.css_files.remove(static_data_file)


# Base implementation from sphinxcontrib-images
# https://github.com/spinus/sphinxcontrib-images/blob/master/sphinxcontrib/images.py#L203
def install_styles_static_files(app, env):
    statics_dir_path = os.path.join(app.builder.outdir, STATICS_DIR_NAME)
    dest_path = os.path.join(statics_dir_path, "sphinx-test-results")

    files_to_copy = ["common.css"]

    # Be sure no "old" css layout is already set
    safe_remove_file("sphinx-test-reports/common.css", app)

    if Version(sphinx_version) < Version("1.6"):
        global status_iterator
        status_iterator = app.status_iterator

    for source_file_path in status_iterator(
        files_to_copy,
        "Copying static files for sphinx-test-results custom style support...",
        brown,
        len(files_to_copy),
    ):
        if not os.path.isabs(source_file_path):
            source_file_path = os.path.join(os.path.dirname(__file__), "css", source_file_path)

        if not os.path.exists(source_file_path):
            source_file_path = os.path.join(os.path.dirname(__file__), "css", "blank.css")
            print(f"{source_file_path} not found. Copying sphinx-internal blank.css")

        dest_file_path = os.path.join(dest_path, os.path.basename(source_file_path))

        if not os.path.exists(os.path.dirname(dest_file_path)):
            ensuredir(os.path.dirname(dest_file_path))

        copyfile(source_file_path, dest_file_path)

        safe_add_file(os.path.relpath(dest_file_path, statics_dir_path), app)
