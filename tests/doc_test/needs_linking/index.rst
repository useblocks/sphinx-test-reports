Basic Document FOR TEST FILE
============================

.. spec:: TEST_1
   :id: TEST_1
   :tags: A
   :asil: D

.. spec:: TEST_2
   :id: TEST_2
   :tags: A

.. spec:: TEST_3
   :id: TEST_3
   :tags: A, B
   :uses_secure: True
   :references: TEST_4
   :links: [[tr_link('references', 'id')]]

.. spec:: TEST_4
   :id: TEST_4
   :tags: B
   :uses_secure: True
   :references: TEST_1, TEST_2
   :links: [[tr_link('references', 'id')]]

Need number with extra options: :need_count:`asil=='D'`

Need number with extra options: :need_count:`uses_secure=='True'`


.. toctree::

   subfolder/file_1
