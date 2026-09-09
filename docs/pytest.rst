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

Enabling it
-----------

.. code-block:: ini

   # pytest.ini / pyproject.toml [tool.pytest.ini_options]
   addopts = -p sphinxcontrib.test_reports.pytest_plugin
   junit_family = xunit1

then run with ``--junitxml=report.xml`` as usual. ``junit_family = xunit1`` is
required: pytest writes ``<testcase>`` attributes only under that family, and the
plugin warns at start-up when a report is requested under ``xunit2``. Every test
case now carries ``file`` and ``line`` -- the path is relative to the pytest
rootdir, and Bazel's ``_main/`` runfiles prefix is cut off.

Nothing else changes for tests that do not use the decorator below.

Linking a test to requirements
------------------------------

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

``fully_verifies`` writes ``FullyVerifies`` the same way. How a value is written
is declared per property, not guessed from the value:

* ``partially_verifies`` and ``fully_verifies`` are multi-valued: a list is
  joined with ``", "`` -- the shape ``tr_property_link_types`` splits again --
  and a bare string is one ID (``partially_verifies="REQ_1"`` writes ``REQ_1``,
  not five one-letter IDs).
* ``test_type`` and ``derivation_technique`` are single-valued; a list is a
  ``TypeError``, not a silent join.
* Any further keyword argument is written under its own name with a single
  value (``Owner="team-a"`` writes ``Owner``). A list under a keyword the plugin
  does not know is a ``TypeError``: register the keyword first, see below.

Empty values are not written, and a decorator that would write nothing is an
error.

The property names are the ones S-CORE's metamodel spells. On the build side
they arrive through the directives' property handling: ``tr_property_link_types``
turns a comma-separated property into a link field --

.. code-block:: python

   tr_property_link_types = {"PartiallyVerifies": "partially_verifies", "FullyVerifies": "fully_verifies"}

-- and ``tr_extra_options`` lists the properties that become plain fields
(``TestType``, ``DerivationTechnique``, ...). The same names work for any other
consumer of the report.

Properties of your own metamodel
--------------------------------

The four keywords above are S-CORE's. A project with other link fields registers
them once, before the tests are collected -- ``conftest.py`` is the place:

.. code-block:: python

   # conftest.py
   from sphinxcontrib.test_reports.pytest_plugin import register_property

   register_property("satisfies", "Satisfies", multi=True)

``@add_test_properties(satisfies=["REQ_1", "REQ_2"])`` then writes
``<property name="Satisfies" value="REQ_1, REQ_2"/>``, ready for
``tr_property_link_types = {"Satisfies": "satisfies"}`` on the build side.
Without ``multi=True`` the property takes a single value, like ``test_type``.
The XML name doubles as keyword, so ``PartiallyVerifies=[...]`` is accepted too.

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
`docs-as-code <https://github.com/eclipse-score/docs-as-code>`_, producing the
same XML, so tests written against that plugin keep working when they import
``add_test_properties`` and ``apply_test_metadata`` from here. Two of its rules
are not ported, because they are that project's process rules rather than
properties of the data: the ``test_type`` and ``derivation_technique``
vocabularies are documented (``TEST_TYPES``, ``DERIVATION_TECHNIQUES``) but not
enforced, and a decorated test is not required to carry a docstring.
