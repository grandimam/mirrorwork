# Chapter 62: Extension Modules

## 62.1 Module Methods

```c
static PyObject *
mymodule_add(PyObject *self, PyObject *args)
{
    int a, b;
    if (!PyArg_ParseTuple(args, "ii", &a, &b))
        return NULL;
    return PyLong_FromLong(a + b);
}

static PyMethodDef mymodule_methods[] = {
    {"add", mymodule_add, METH_VARARGS, "Add two integers"},
    {NULL, NULL, 0, NULL}  // Sentinel
};
```

## 62.2 Keyword Arguments

```c
static PyObject *
greet(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = {"name", "greeting", NULL};
    const char *name;
    const char *greeting = "Hello";

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s|s", kwlist,
                                      &name, &greeting))
        return NULL;

    return PyUnicode_FromFormat("%s, %s!", greeting, name);
}

// Method def
{"greet", (PyCFunction)greet, METH_VARARGS | METH_KEYWORDS, "Greet someone"}
```

## 62.3 Building Extensions

```python
# setup.py
from setuptools import setup, Extension

module = Extension(
    'mymodule',
    sources=['mymodule.c'],
    include_dirs=['/usr/local/include'],
    library_dirs=['/usr/local/lib'],
    libraries=['mylib'],
)

setup(
    name='mymodule',
    ext_modules=[module],
)
```

## Summary

- Define methods with PyMethodDef
- Use METH_VARARGS or METH_KEYWORDS
- Build with setuptools Extension

---

[Next: Defining Types →](chapter-63-defining-types.md)
