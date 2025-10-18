import os
from typing import TYPE_CHECKING, Optional, List, Callable, Iterable, cast

import sphinx
from packaging.version import Version
from sphinx.util import console as _sphinx_console
from sphinx.util.osutil import copyfile, ensuredir

brown = cast(object, getattr(_sphinx_console, "brown", ""))

sphinx_version = sphinx.__version__
if Version(sphinx_version) >= Version("1.6"):
    try:
        from sphinx.util.display import status_iterator as _status_iterator 
    except Exception:
        from sphinx.util import status_iterator as _status_iterator

StatusIteratorType = Callable[[Iterable[str], str, object, int], Iterable[str]]

status_iterator_typed: Optional[StatusIteratorType]
if Version(sphinx_version) >= Version("1.6"):
    status_iterator_typed = cast(StatusIteratorType, _status_iterator)
else:
    status_iterator_typed = None

STATICS_DIR_NAME = "_static"


def safe_add_file(filename: str, app: object) -> None:
    """
    Adds files to builder resources only, if the given filename was not already registered.
    Needed mainly for tests to avoid multiple registration of the same file and therefore also multiple execution
    of e.g. a javascript file during page load.

    :param filename: filename to remove
    :param app: app object
    :return: None
    """
    data_file: str = filename
    static_data_file: str = os.path.join("_static", data_file)

    raw_builder = getattr(app, "builder", None)
    builder: object = cast(object, raw_builder)
    script_files = cast(Optional[List[str]], getattr(builder, "script_files", None))
    css_files = cast(Optional[List[str]], getattr(builder, "css_files", None))

    if data_file.split(".")[-1] == "js":
        if script_files is not None and static_data_file not in script_files:
            add_js_file_fn = cast(Optional[Callable[[str], object]], getattr(cast(object, app), "add_js_file", None))
            if add_js_file_fn is not None:
                add_js_file_fn(data_file)
    elif data_file.split(".")[-1] == "css":
        if hasattr(app.builder, "css_files"):
            css_files = [css.filename for css in app.builder.css_files]
            if static_data_file not in css_files:
                app.add_css_file(data_file)
    else:
        raise NotImplementedError(
            "File type {} not support by save_add_file".format(data_file.split(".")[-1])
        )


def safe_remove_file(filename: str, app: object) -> None:
    """
    Removes a given resource file from builder resources.
    Needed mostly during test, if multiple sphinx-build are started.
    During these tests js/cass-files are not cleaned, so a css_file from run A is still registered in run B.

    :param filename: filename to remove
    :param app: app object
    :return: None
    """
    data_file: str = filename
    static_data_file: str = os.path.join("_static", data_file)

    raw_builder = getattr(app, "builder", None)
    builder: object = cast(object, raw_builder)
    script_files = cast(Optional[List[str]], getattr(builder, "script_files", None))
    css_files = cast(Optional[List[str]], getattr(builder, "css_files", None))

    if data_file.split(".")[-1] == "js":
        if script_files is not None and static_data_file in script_files:
            script_files.remove(static_data_file)
    elif data_file.split(".")[-1] == "css":
        if css_files is not None and static_data_file in css_files:
            css_files.remove(static_data_file)


# Base implementation from sphinxcontrib-images
# https://github.com/spinus/sphinxcontrib-images/blob/master/sphinxcontrib/images.py#L203
def install_styles_static_files(app: object, env: object) -> None:
    builder_obj: object = cast(object, getattr(app, "builder"))
    outdir = cast(str, getattr(builder_obj, "outdir"))
    statics_dir_path: str = os.path.join(outdir, STATICS_DIR_NAME)
    dest_path: str = os.path.join(statics_dir_path, "sphinx-test-results")

    files_to_copy: List[str] = ["common.css"]

    # Be sure no "old" css layout is already set
    safe_remove_file("sphinx-test-reports/common.css", app)

    if Version(sphinx_version) < Version("1.6"):
        global status_iterator_typed
        status_it = getattr(cast(object, app), "status_iterator")
        status_iterator_typed = cast(StatusIteratorType, status_it)

    iterator = cast(StatusIteratorType, status_iterator_typed)
    for source_file_path in iterator(
        files_to_copy,
        "Copying static files for sphinx-test-results custom style support...",
        brown,
        len(files_to_copy),
    ):
        if not os.path.isabs(source_file_path):
            source_file_path = os.path.join(
                os.path.dirname(__file__), "css", source_file_path
            )

        if not os.path.exists(source_file_path):
            source_file_path = os.path.join(
                os.path.dirname(__file__), "css", "blank.css"
            )
            print(f"{source_file_path} not found. Copying sphinx-internal blank.css")

        dest_file_path: str = os.path.join(dest_path, os.path.basename(source_file_path))

        if not os.path.exists(os.path.dirname(dest_file_path)):
            ensuredir(os.path.dirname(dest_file_path))

        copyfile(source_file_path, dest_file_path)

        safe_add_file(os.path.relpath(dest_file_path, statics_dir_path), app)
