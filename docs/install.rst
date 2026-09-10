:hide-navigation:

Installation
============

The Sphinx extension needs the documentation toolchain -- Sphinx and
`Sphinx-Needs <https://sphinx-needs.readthedocs.io/en/latest/>`_ -- which is
the ``sphinx`` extra of the package::

   pip install "sphinx-test-reports[sphinx]"

.. versionchanged:: 1.5.0
   ``pip install sphinx-test-reports`` -- without the extra -- no longer
   installs Sphinx and Sphinx-Needs. The package also ships the
   :ref:`test-reports command <cli>`, which turns test results into a
   ``needs.json`` without a Sphinx build, and that is what the bare install is
   for: a test runner or a build action that has no documentation toolchain.
   A documentation project has to add the extra to its install line.

The extra also states the supported versions: Sphinx 7.4 and Sphinx-Needs
6.0.1 or later. An extra is opt-in, so a project that keeps installing the
bare package into an environment holding an older toolchain would never be
told by ``pip``; the extension therefore checks the installed versions when
Sphinx loads it and stops the build with a message naming the install line
above.

After that the extension must be added to the ``conf.py`` file::

   extensions = ['sphinx_needs',
                 'sphinxcontrib.test_reports',
                 'sphinxcontrib.plantuml']

Please note, ``Sphinx-Test-Report`` is based on the
`Sphinx-needs extension <https://sphinx-needs.readthedocs.io/en/latest/>`_.
Therefore it must also be added to the ``extensions`` list!

And same for `PlantUML <http://plantuml.com>`_, which is important to render flowcharts for filtered
test-cases.

More details can be found in the
`installation-guide <https://sphinx-needs.readthedocs.io/en/latest/installation.html>`_
of ``Sphinx-Needs``.
