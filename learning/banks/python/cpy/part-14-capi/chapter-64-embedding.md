# Chapter 64: Embedding Python

## 64.1 Basic Embedding

```c
#include <Python.h>

int main(int argc, char *argv[])
{
    // Initialize Python
    Py_Initialize();

    // Run Python code
    PyRun_SimpleString("print('Hello from embedded Python!')");

    // Finalize
    Py_Finalize();
    return 0;
}
```

## 64.2 Calling Python Functions

```c
PyObject *pModule, *pFunc, *pValue, *pArgs;

// Import module
pModule = PyImport_ImportModule("mymodule");

// Get function
pFunc = PyObject_GetAttrString(pModule, "my_function");

// Call function
pArgs = PyTuple_Pack(2, PyLong_FromLong(1), PyLong_FromLong(2));
pValue = PyObject_CallObject(pFunc, pArgs);

// Get result
long result = PyLong_AsLong(pValue);

// Cleanup
Py_DECREF(pArgs);
Py_DECREF(pValue);
Py_DECREF(pFunc);
Py_DECREF(pModule);
```

## 64.3 Multi-Threaded Embedding

```c
// Initialize with threading support
Py_Initialize();
PyEval_InitThreads();

// Save thread state before creating threads
PyThreadState *mainThreadState = PyThreadState_Get();
PyEval_ReleaseLock();

// In each thread
void thread_function() {
    PyGILState_STATE gstate = PyGILState_Ensure();

    // Python code here
    PyRun_SimpleString("print('Hello from thread')");

    PyGILState_Release(gstate);
}
```

## Summary

- Py_Initialize() starts the interpreter
- PyImport_ImportModule() loads modules
- PyObject_CallObject() calls functions
- Use PyGILState for multi-threaded embedding

---

[Next: PyPy and Other Implementations →](../part-15-alternatives/chapter-65-pypy.md)
