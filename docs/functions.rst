:hide-navigation:

Dynamic functions
=================

Sphinx-Test-Reports provides dynamic functions for Sphinx-Needs.

Read chapter `Dynamic function <https://sphinx-needs.readthedocs.io/en/latest/dynamic_functions.html>`_
from Sphinx-Needs documentation to know how to use them.


tr_link
-------
Links a need (e.g testcase) automatically to other needs, which have a specific value in a given option.

**Usage**::

   .. test-case:: My test case
      :id: TESTCASE_1
      :file: my_test_file.xml
      :suite: pytest
      :classname: sphinxcontrib.test_reports.test_reports
      :case: FLAKE8
      :links: [[tr_link("source_option", "target_option")]]

``tr_link`` needs the following arguments:

* **source_option**: Name of an option of the test-need, which is used for comparison. E.g. ``classname``.
* **target_option**: Name of an option of all other needs, which is used for comparison. E.g. ``title``.

The function reads the ``target_option`` from the need, where it is used.
Then it goes through **all** other needs and checks if the value of their ``source_option`` is equal to
the ``target_option``.
If this is the case, their IDs get stored and finally returned.

``source_option`` can also reference an option with comma separated values.
In this case a comparison is performed for each value, which may lead to multiple links.

**Example**::

   .. spec:: sphinxcontrib.test_reports.test_reports
      :id: TESTSPEC_001
      :status: open
      :tags: example, link_example

      This specification specifies the test case ``sphinxcontrib.test_reports.test_reports``.

   .. test-case:: Flake8 test case
      :id: TESTLINK_1
      :file: ../tests/doc_test/utils/pytest_data.xml
      :suite: pytest
      :classname: sphinxcontrib.test_reports.test_reports
      :case: FLAKE8
      :tags: example, link_example
      :links: [[tr_link('classname', 'title')]]

      A simple test case.
      We will set a link to the need, which has our classname as title.

   .. needflow::
      :tags: link_example

.. spec:: sphinxcontrib.test_reports.test_reports
   :id: TESTSPEC_001
   :status: open
   :tags: example, link_example

   This specification specifies the test case ``sphinxcontrib.test_reports.test_reports``.

.. test-case:: Flake8 test case
   :id: TESTLINK_1
   :file: ../tests/doc_test/utils/pytest_data.xml
   :suite: pytest
   :classname: sphinxcontrib.test_reports.test_reports
   :case: FLAKE8
   :tags: example, link_example
   :links: [[tr_link('classname', 'title')]]

   A simple test case.
   We will set a link to the need, which has our classname as title.

.. needflow::
   :tags: link_example


tr_link_match
-------------

Similar to ``tr_link``, but allows using a regex to find needs to link to.  
When using ``tr_link_match``, the value of the ``source_option`` is compiled as a regular expression, and all other needs
whose ``target_option`` values match this pattern are linked.

**Usage**::

   .. test-case:: Tests/TestSuite.TestCase/*
      :id: TESTLINK_1
      :results: "[[tr_link_match('title', 'case')]]",

The example above will link all test results which have a classname starting with ``Tests/TestSuite.TestCase`` 
(given that the ``results`` are defined as ``needs_extra_links`` in the ``conf.py``).

``tr_link_match`` needs the following arguments:

* **source_option**: Name of an option of the test-need (regex is taken from its value).
* **target_option**: Name of an option in other needs, which must match the regex in ``source_option``.
