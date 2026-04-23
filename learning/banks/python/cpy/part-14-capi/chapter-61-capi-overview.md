# Chapter 61: C API Overview

## 61.1 Python C API Basics

```c
#include <Python.h>

// Every C extension starts with this
PyMODINIT_FUNC
PyInit_mymodule(void)
{
    return PyModule_Create(&mymodule_def);
}

static struct PyModuleDef mymodule_def = {
    PyModuleDef_HEAD_INIT,
    "mymodule",           // Module name
    "My module docs",     // Module docstring
    -1,                   // Module state size (-1 = global)
    mymodule_methods      // Method table
};
```

## 61.2 Reference Counting

```c
// Increment reference count
Py_INCREF(obj);

// Decrement reference count
Py_DECREF(obj);

// Safe versions (handle NULL)
Py_XINCREF(obj);
Py_XDECREF(obj);

// Borrowed vs New references
PyObject *item = PyList_GetItem(list, 0);  // Borrowed
PyObject *item = PyList_GET_ITEM(list, 0); // Borrowed (macro)
Py_INCREF(item);  // Now we own it
```

## 61.3 Type Conversion

```c
// Python to C
long n = PyLong_AsLong(obj);
double d = PyFloat_AsDouble(obj);
const char *s = PyUnicode_AsUTF8(obj);

// C to Python
PyObject *obj = PyLong_FromLong(42);
PyObject *obj = PyFloat_FromDouble(3.14);
PyObject *obj = PyUnicode_FromString("hello");
```

## 61.4 Error Handling

```c
static PyObject *
my_function(PyObject *self, PyObject *args)
{
    int x;
    if (!PyArg_ParseTuple(args, "i", &x))
        return NULL;  // Exception already set

    if (x < 0) {
        PyErr_SetString(PyExc_ValueError, "x must be positive");
        return NULL;
    }

    return PyLong_FromLong(x * 2);
}
```

## Summary

- Include Python.h for all C extensions
- Manage reference counts carefully
- Use PyArg_ParseTuple for argument parsing
- Return NULL with exception set on error

---

[Next: Extension Modules →](chapter-62-extension-modules.md)
