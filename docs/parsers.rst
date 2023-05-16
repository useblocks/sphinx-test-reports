:hide-navigation:

Parsers
=======

``Sphinx-Test-Reports`` provides different parsers for test result files.
One for **XML-files**, following the **JUnit** format, and one for
generic **JSON-files**, which are not following any standard.

The needed parser is automatically selected by the file extensions ``xml`` or ``json``.

Junit
-----
This parser reads **xml** files and handles the content as **JUnit** data.
Other XML formats are not supported.

As **JUnit** format is not really standardized, different test framework produce slightly different JUnit xml files.
``Sphinx-Test-Reports`` supports the "dialects" of:

* pytest
* GoogleTest
* CasperJS

There is a high chance, that other tet frameworks are supported as well, as long as they provide a Junit file.

JSON
----

The JSON parser can read any JSON file. But as the data structure is not following any standard, the user need to
provide a mapping between the used JSON structure and the internal structure used by ``Sphinx-Test-Reports``.

Even if this means some more configuration effort, the benefit is a completely customizable data structure.

For an example please take a look into :ref:`json_example`.

Config tr_json_mapping
~~~~~~~~~~~~~~~~~~~~~~
Takes a mapping configuration, which defines how to map the JSON structure to the internal structure used by
``Sphinx-Test-Reports``.

``tr_json_mapping`` is a dictionary, where the first key is a name for the configuration.
The name is currently just a placeholder and the first config is used for all JSON imports.

Two mappings must be configured as dictionary, one for ``testsuite`` and one for the nested ``testcase``.

The key of this dictionary elements is the **internal** name and fix.

The value is a tuple, containing a **selector list** and a **default value**, if the selector does not find any data.

The **selector** is a list, where each entry is representing one level of the data structure.
If the entry is a string, it is used as a key for a dict. If it is a integer number, it is taken as position
of a list.

**JSON example**

.. code-block:: python

   {
       "level_1": {
           "level_2": [
               {"value": "Hello!"}
               {"value": "Bye Bye!"}
           ]
       }
   }

Given the above JSON example, the following "selector" will address the value ``Bye Bye!``::

   ["level_1", "level_2", 1, "value"]


**Example config**

This example contains **all** internal elements and a mapping as example.
For ``testsuite`` the value ``testcases`` defines the location of nested testcases.

An example of a JSON file, which supports the below configuration, can be seen in :ref:`json_example`.

.. code-block:: python

   tr_json_mapping = {
      "json_config_1": {
         "testsuite": {
            "name":        (["name"], "unknown"),
            "tests":       (["tests"], "unknown"),
            "errors":      (["errors"], "unknown"),
            "failures":    (["failures"], "unknown"),
            "skips":       (["skips"], "unknown"),
            "passed":      (["passed"], "unknown"),
            "time":        (["time"], "unknown"),
            "testcases":   (["testcase"], "unknown"),
            "name":        (["name"], "unknown"),
         },
         "testcase": {
            "name":        (["name"], "unknown"),
            "classname":   (["classname"], "unknown"),
            "file":        (["file"], "unknown"),
            "line":        (["line"], "unknown"),
            "time":        (["time"], "unknown"),
            "result":      (["result"], "unknown"),
            "type":        (["type"], "unknown"),
            "text":        (["text"], "unknown"),
            "message":     (["message"], "unknown"),
            "system-out":  (["system-out"], "unknown"),
         }
      }
   }





Technical details
-----------------
Each parser is realized by a class, which needs to provide specific functions.
Also the internal object representation is the same. So each parser must map the external format to the internal
representation.

Only the parser cares about the format. Other internal functions (like directives) just work with the common
data representation and rely on it.
So parsers are not allowed to rename or even extend this internal representation.
If this is needed, all available parsers need to be updated as well.


