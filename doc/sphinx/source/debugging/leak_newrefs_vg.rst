.. highlight:: python
    :linenothreshold: 10

.. highlight:: c
    :linenothreshold: 10

.. toctree::
    :maxdepth: 3


.. _leaked-new-references-label:

===============================================
Leaked New References
===============================================

This shows what happens if create new Python objects and leak them and how we might detect that.

----------------
A Leak Example
----------------

Here is an example function that deliberately creates leaks with new references. It takes an integer value to be created (and leaked) and a count of the number of times that this should happen. We can then call this from the Python interpreter and observe what happens.

.. code-block:: c
    :linenos:
    :emphasize-lines: 11, 12, 13

    static PyObject *leak_new_reference(PyObject *pModule,
                                        PyObject *args, PyObject *kwargs) {
        PyObject *ret = NULL;
        int value, count;
        static char *kwlist[] = {"value", "count", NULL};
    
        if (!PyArg_ParseTupleAndKeywords(args, kwargs, "ii", kwlist, &value, &count)) {
            goto except;
        }
        fprintf(stdout, "loose_new_reference: value=%d count=%d\n", value, count);
        for (int i = 0; i < count; ++i) {
            PyLong_FromLong(value);    /* New reference, leaked. */
        }
    
        Py_INCREF(Py_None);
        ret = Py_None;
        goto finally;
    except:
        Py_XDECREF(ret);
        ret = NULL;
    finally:
        fprintf(stdout, "loose_new_reference: DONE\n");
        return ret;
    }

And we add this to the ``cPyRefs`` module function table as the python function ``leakNewRefs``:

.. code-block:: c

    static PyMethodDef cPyRefs_methods[] = {
        /* Other functions here
         * ...
         */
        {"leakNewRefs", (PyCFunction)leak_new_reference,
            METH_VARARGS | METH_KEYWORDS, "Leaks new references to longs."},
    
        {NULL, NULL, 0, NULL}  /* Sentinel */
    };

In Python first we check what the size of a long is then we call the leaky function with the value 1000 (not the values -5 to 255 which are interned) one million times and there should be a leak of one million times the size of a long::

    >>> import sys
    >>> sys.getsizeof(1000)
    44
    >>> import cPyRefs
    >>> cPyRefs.leakNewRefs(1000, 1000000)
    loose_new_reference: value=1000 count=1000000
    loose_new_reference: DONE
    >>>

This should generate a leak of 44Mb or thereabouts.

----------------------------------
Recognising Leaked New References
----------------------------------

Leaked references can lay unnoticed for a long time, especially if they are small. The ways that you might detect that they are happening are:

* Noticing an unanticipated, ever increasing memory usage at the OS level (by using ``top`` for example).
* If you run a debug build of Python with ``Py_REF_DEBUG`` defined you might notice a very high level of total reference counts by either invoking Python with ``-X showrefcount`` or calling ``sys.gettotalrefcount()``.
* Other types of debug build can be useful too.
* Examining Valgrind results. 

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Observing the Memory Usage
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the debug tools section there is a :ref:`simple-memory-monitor-label` that can examine the memory of another running process.

Lets test it. In one shell fire up Python and find its PID::

    >>> import os
    >>> os.getpid()
    14488

In a second shell fire up pidmon.py with this PID:

.. code-block:: bash

    $ python3 pidmon.py 14488
    pextmem(rss=7659520, vms=2475937792, pfaults=8380416, pageins=2617344)
         7.660 [Mb]
         7.660 [Mb]     +0.000 [Mb]
         7.660 [Mb]     +0.000 [Mb]
         7.660 [Mb]     +0.000 [Mb]

Go back to the first shell and import ``cPyRefs``::

    >>> import cPyRefs
    >>> cPyRefs.leakNewRefs(1000, 1000000)
    loose_new_reference: value=1000 count=1000000
    loose_new_reference: DONE
    >>>

In the second shell pidmon.py shows the sudden jump in memory usage:

.. code-block:: bash

    $ python3 pidmon.py 14488
    pextmem(rss=7659520, vms=2475937792, pfaults=8380416, pageins=2617344)
         7.660 [Mb]
         7.660 [Mb]     +0.000 [Mb]
         7.660 [Mb]     +0.000 [Mb]
         7.660 [Mb]     +0.000 [Mb]
         ...
         7.684 [Mb]     +0.000 [Mb]
         7.684 [Mb]     +0.000 [Mb]
        56.443 [Mb]    +48.759 [Mb]
        56.443 [Mb]     +0.000 [Mb]
        56.443 [Mb]     +0.000 [Mb]
        56.443 [Mb]     +0.000 [Mb]
        56.443 [Mb]     +0.000 [Mb]
         ...

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Observing the Total Reference Counts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have a debug build of Python with ``Py_REF_DEBUG`` defined you might notice a very high level of total reference counts by either invoking Python with ``-X showrefcount`` or calling ``sys.gettotalrefcount()``.

For example:

.. code-block:: python

    >>> import sys
    >>> import cPyRefs
    >>> dir()
    ['__builtins__', '__doc__', '__loader__', '__name__', '__package__', '__spec__', 'cPyRefs', 'sys']
    >>> sys.gettotalrefcount()
    55019
    >>> cPyRefs.leakNewRefs(1000, 1000000)
    loose_new_reference: value=1000 count=1000000
    loose_new_reference: DONE
    >>> dir()
    ['__builtins__', '__doc__', '__loader__', '__name__', '__package__', '__spec__', 'cPyRefs', 'sys']
    >>> sys.gettotalrefcount()
    1055019

Notice that ``cPyRefs.leakNewRefs(1000, 1000000)`` does not add anything to the result of ``dir()`` but adds 1m reference counts somewhere.

And those references are not collectable::

    >>> import gc
    >>> gc.collect()
    0
    >>> sys.gettotalrefcount()
    1055519


.. _leaked-new-references-usingCOUNT_ALLOCS-label:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Observing the Reference Counts for a Particular Type
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have a debug build with ``COUNT_ALLOCS`` [See: :ref:`debug-version-of-python-COUNT_ALLOCS-label`] defined you can see the references counts for each type. This build will have a new function ``sys.getcounts()`` which returns a list of tuples ``(tp_name, tp_allocs, tp_frees, tp_maxalloc)`` where ``tp_maxalloc`` is the maximum ever seen value of the reference ``tp_allocs - tp_frees``. The list is ordered by time of first object allocation:

.. code-block:: python

    >>> import pprint
    >>> import sys
    >>> pprint.pprint(sys.getcounts())
    [('Repr', 1, 0, 1),
     ('symtable entry', 3, 3, 1),
     ('OSError', 1, 1, 1),
     ...
     ('int', 3342, 2630, 712),
     ...
     ('dict', 1421, 714, 714),
     ('tuple', 13379, 9633, 3746)]

We can try our leaky code:

.. code-block:: python

    >>> import cPyRefs
    >>> cPyRefs.leakNewRefs(1000, 1000000)
    loose_new_reference: value=1000 count=1000000
    loose_new_reference: DONE
    >>> pprint.pprint(sys.getcounts())
    [('memoryview', 103, 103, 1),
     ...
     ('int', 1004362, 3650, 1000712),
     ...
     ('dict', 1564, 853, 718),
     ('tuple', 22986, 19236, 3750)]

There is a big jump in ``tp_maxalloc`` for ints that is worth investigating.

When the Python process finishes you get a dump of this list as the interpreter is broken down::

.. code-block:: console

    memoryview alloc'd: 210, freed: 210, max in use: 1
    managedbuffer alloc'd: 210, freed: 210, max in use: 1
    PrettyPrinter alloc'd: 2, freed: 2, max in use: 1
    ...
    int alloc'd: 1005400, freed: 4887, max in use: 1000737
    ...
    str alloc'd: 21920, freed: 19019, max in use: 7768
    dict alloc'd: 1675, freed: 1300, max in use: 718
    tuple alloc'd: 32731, freed: 31347, max in use: 3754
    fast tuple allocs: 28810, empty: 2101
    fast int allocs: pos: 7182, neg: 20
    null strings: 69, 1-strings: 5


.. _leaked-new-references-valgrind-label:

------------------------------------------
Finding Where the Leak is With Valgrind
------------------------------------------

Now that we have noticed that there is a problem, then where, exactly, is the problem?

Lets run our debug version of Python with Valgrind and see if we can spot the leak (assumes *.valgrind-python.supp* is in your $HOME directory and ``./Python.3.4.3D`` is the debug executable)::

    valgrind --tool=memcheck --trace-children=yes --dsymutil=yes --leak-check=full --show-leak-kinds=all --suppressions=~/.valgrind-python.supp ./Python.3.4.3D

.. note::

    You need to use the option ``--show-leak-kinds=all`` for the next bit to work otherwise you see in the summary that memory has been leaked but not where from.

Then run this code::

    >>> import cPyRefs
    >>> cPyRefs.leakNewRefs(1000, 1000000)
    loose_new_reference: value=1000 count=1000000
    loose_new_reference: DONE
    >>>^D

In the Valgrind output you should see this in the summary at the end:

.. code-block:: bash
    :emphasize-lines: 5

    ==13042== LEAK SUMMARY:
    ==13042==    definitely lost: 6,925 bytes in 26 blocks
    ==13042==    indirectly lost: 532 bytes in 5 blocks
    ==13042==      possibly lost: 329,194 bytes in 709 blocks
    ==13042==    still reachable: 44,844,200 bytes in 1,005,419 blocks

The "still reachable" value is a clue that something has gone awry.

In the body of the Valgrind output you should find something like this - the important lines are highlighted:

.. code-block:: bash
    :emphasize-lines: 1, 7

    ==13042== 44,000,000 bytes in 1,000,000 blocks are still reachable in loss record 2,325 of 2,325
    ==13042==    at 0x47E1: malloc (vg_replace_malloc.c:300)
    ==13042==    by 0x41927E: _PyMem_RawMalloc (in /Library/Frameworks/Python.framework/Versions/3.4/Python)
    ==13042==    by 0x418D80: PyObject_Malloc (in /Library/Frameworks/Python.framework/Versions/3.4/Python)
    ==13042==    by 0x3DFBA8: _PyLong_New (in /Library/Frameworks/Python.framework/Versions/3.4/Python)
    ==13042==    by 0x3DFF8D: PyLong_FromLong (in /Library/Frameworks/Python.framework/Versions/3.4/Python)
    ==13042==    by 0x11BFA40: leak_new_reference (cPyRefs.c:149)
    ==13042==    by 0x40D81C: PyCFunction_Call (in /Library/Frameworks/Python.framework/Versions/3.4/Python)
    ==13042==    by 0x555C15: call_function (in /Library/Frameworks/Python.framework/Versions/3.4/Python)
    ==13042==    by 0x54E02B: PyEval_EvalFrameEx (in /Library/Frameworks/Python.framework/Versions/3.4/Python)
    ==13042==    by 0x53A7B4: PyEval_EvalCodeEx (in /Library/Frameworks/Python.framework/Versions/3.4/Python)
    ==13042==    by 0x539414: PyEval_EvalCode (in /Library/Frameworks/Python.framework/Versions/3.4/Python)
    ==13042==    by 0x5A605E: run_mod (in /Library/Frameworks/Python.framework/Versions/3.4/Python)
    ==13042== 

Which is exactly what we are looking for.



