.. _pytest_plugin:

pytest plugin
=============
.. versionadded:: 1.5.0

A stock pytest run writes a JUnit XML that this extension can only partly use:
no ``<testcase>`` carries the ``file``/``line`` attributes that give a test case
its source location (``tr_source_file_option``/``tr_source_line_option``, and
the deterministic ID of ``tr_deterministic_case_ids``), and nothing records the
requirements a test verifies. ``Sphinx-Test-Reports`` ships a small pytest
plugin that writes both.

The plugin is generic: which properties exist, what they are called in the XML
and whether they take a list is pytest configuration, not code. S-CORE's model
is the worked example below.

Enabling it
-----------

.. code-block:: ini

   # pytest.ini / pyproject.toml [tool.pytest.ini_options]
   addopts = -p sphinxcontrib.test_reports.pytest_plugin
   junit_family = xunit1

then run with ``--junitxml=report.xml`` as usual. ``junit_family = xunit1`` is
required: pytest writes ``<testcase>`` attributes only under that family (its
``legacy`` is an alias), and the plugin warns at start-up when a report is
requested under ``xunit2``. Every test case now carries ``file`` and ``line`` --
the path is relative to the pytest rootdir, and Bazel's ``_main/`` runfiles
prefix is cut off.

Nothing else changes for tests that do not use the decorator below.

.. note::

   pytest builds the XML writer on the controller only, so under pytest-xdist
   (``-n``) the workers cannot record the location: the test cases then carry
   pytest's stock ``file``/``line`` (counted from 0), silently. The plugin warns
   at start-up; write the report in a run without ``-n``.

Both start-up notices are a ``TestReportsConfigWarning``. A project that turns
warnings into errors (``filterwarnings = error``, ``-W error``) gets them as a
clean usage error instead;
``ignore::sphinxcontrib.test_reports.pytest_plugin.TestReportsConfigWarning``
silences them. pytest's own notice that ``record_xml_attribute`` is experimental
is dropped by the plugin, whatever the warning policy.

Declaring the properties
------------------------

The ``test_reports_properties`` ini option declares the properties a test may
carry, one per line:

.. code-block:: text

   keyword [= XmlName] [, list]

*keyword*
   what a test author writes -- the argument of ``add_test_properties`` or the
   key in the metadata of ``apply_test_metadata``.
*XmlName*
   the ``<property name="...">`` written to the report. Leave it out when it
   equals the keyword.
``list``
   marks a multi-valued property: a list is written joined with ``", "`` -- the
   shape ``tr_property_link_types`` splits again -- and a bare string counts as
   one value. Without it the property takes exactly one value, and a list is a
   ``TypeError`` rather than a silent join.

A keyword that is not declared is written under its own name with a single
value. A list under it is a ``TypeError`` whose message names the option, so a
project cannot lose requirement IDs to a Python ``repr`` silently. A line
outside the grammar stops the run at start-up with a usage error that quotes
it.

**Example: S-CORE.** The model of S-CORE's docs-as-code, whose ``score_pytest``
plugin this one was ported from:

.. code-block:: ini

   # pytest.ini
   [pytest]
   addopts = -p sphinxcontrib.test_reports.pytest_plugin
   junit_family = xunit1
   test_reports_properties =
       partially_verifies = PartiallyVerifies, list
       fully_verifies = FullyVerifies, list
       test_type = TestType
       derivation_technique = DerivationTechnique

.. code-block:: toml

   # pyproject.toml
   [tool.pytest.ini_options]
   addopts = "-p sphinxcontrib.test_reports.pytest_plugin"
   junit_family = "xunit1"
   test_reports_properties = [
       "partially_verifies = PartiallyVerifies, list",
       "fully_verifies = FullyVerifies, list",
       "test_type = TestType",
       "derivation_technique = DerivationTechnique",
   ]

With it, tests written against ``score_pytest`` keep working when they import
``add_test_properties`` and ``apply_test_metadata`` from here. The values of
``test_type`` and ``derivation_technique`` are the identifiers of S-CORE's
verification methods and derivation techniques, from its
`verification concept <https://eclipse-score.github.io/process_description/main/process_areas/verification/verification_concept.html#verification-concept-types-methods>`_:

.. list-table::
   :header-rows: 1

   * - ``TestType``
     - ``DerivationTechnique``
   * - ``control-flow-analysis``, ``data-flow-analysis``, ``fault-injection``,
       ``inspection``, ``interface-test``, ``requirements-based``,
       ``resource-usage``, ``static-code-analysis``,
       ``structural-statement-coverage``, ``structural-branch-coverage``,
       ``walkthrough``
     - ``requirements-analysis``, ``design-analysis``, ``boundary-values``,
       ``equivalence-classes``, ``fuzz-testing``, ``error-guessing``,
       ``explorative-testing``

They are documented here, not enforced by the plugin: S-CORE's own metamodel
accepts any string for both fields, and a project with a different metamodel
writes its own values.

Linking a test to requirements
------------------------------

With the S-CORE model declared:

.. code-block:: python

   from sphinxcontrib.test_reports.pytest_plugin import add_test_properties

   @add_test_properties(
       partially_verifies=["REQ_1", "REQ_2"],
       test_type="requirements-based",
       derivation_technique="requirements-analysis",
   )
   def test_addition():
       """Adding two numbers."""
       assert 1 + 1 == 2

writes, on that test's ``<testcase>``:

.. code-block:: xml

   <properties>
     <property name="PartiallyVerifies" value="REQ_1, REQ_2"/>
     <property name="TestType" value="requirements-based"/>
     <property name="DerivationTechnique" value="requirements-analysis"/>
   </properties>

The declared XML name doubles as keyword, so ``PartiallyVerifies=[...]`` is
accepted too. Empty values are not written, and a decorator that would write
nothing is an error at import time. The values are written when the test is
set up, against the declared model; a wrong shape -- a list where one value is
expected -- fails that test with the ``TypeError`` above.

The decorator also goes on a class, and decorators stack: a classification on
the class and the requirement links on each method are merged into the method's
``<properties>``, the decorator closest to the function winning where two set
the same property.

On the build side the properties arrive through the directives' property
handling: ``tr_property_link_types`` turns a comma-separated property into a
link field, and the link field has to exist as a sphinx-needs link type --

.. code-block:: python

   # conf.py
   needs_extra_links = [
       {"option": "partially_verifies", "incoming": "partially verified by", "outgoing": "partially verifies"},
       {"option": "fully_verifies", "incoming": "fully verified by", "outgoing": "fully verifies"},
   ]
   tr_property_link_types = {"PartiallyVerifies": "partially_verifies", "FullyVerifies": "fully_verifies"}

-- and ``tr_extra_options`` lists the properties that become plain fields
(``TestType``, ``DerivationTechnique``, ...), each of which needs its
``needs_extra_options`` entry in turn. A link field missing from
``needs_extra_links`` fails the build on the first test case that carries the
property. The same names work for any other consumer of the report.

Metadata known only at run time
-------------------------------

A parameterised test whose metadata comes from the file it is driven by cannot
use a decorator. :func:`apply_test_metadata` records the same properties from
inside the test body, and can point the case at the file that drove it instead
of at the test function:

.. code-block:: python

   from sphinxcontrib.test_reports.pytest_plugin import apply_test_metadata

   @pytest.mark.parametrize("spec", SPECS)
   def test_spec(spec, record_property, record_xml_attribute):
       metadata = read_metadata(spec)   # {"fully_verifies": [...], "test_type": ...}
       apply_test_metadata(
           record_property=record_property,
           metadata=metadata,
           record_xml_attribute=record_xml_attribute,
           file=str(spec),
           line=metadata_line(spec),
       )
       ...  # the actual checks

Call it before the first assertion, so a failing test still carries its
metadata. Metadata without values -- a file with an empty metadata block --
writes no properties and is not an error; ``file`` and ``line`` are applied
regardless.

Origin
------

The plugin is a port of the ``score_pytest`` attribute plugin of S-CORE's
`docs-as-code <https://github.com/eclipse-score/docs-as-code>`_. What that
plugin hard-codes -- the four properties and their spelling -- is the
``test_reports_properties`` example above here, so the XML comes out the same
and other metamodels declare their own. Two of its rules are not ported,
because they are that project's process rules rather than properties of the
data: the ``test_type`` and ``derivation_technique`` vocabularies are documented
but not enforced, and a decorated test is not required to carry a docstring.
