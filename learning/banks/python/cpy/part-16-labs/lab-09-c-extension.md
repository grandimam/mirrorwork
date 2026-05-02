# Lab 9: C Extension

## Objective

Build a C extension module from scratch to understand the Python C API, reference counting, and GIL management.

## Prerequisites

- Understanding of C API (Part 14)
- Basic C programming knowledge
- Python development headers installed

## Lab Setup

First, set up the project structure:

```bash
mkdir -p fastmath
cd fastmath
```

## Exercise 1: Basic Module Structure

Create the basic C extension module:

```c
/* fastmath.c - A simple C extension module */

#define PY_SSIZE_T_CLEAN
#include <Python.h>

/* Module documentation */
PyDoc_STRVAR(module_doc,
    "fastmath - A fast math operations module.\n"
    "\n"
    "This module provides optimized mathematical operations.\n"
);

/* Function: add two integers */
static PyObject *
fastmath_add(PyObject *self, PyObject *args)
{
    long a, b;

    /* Parse arguments */
    if (!PyArg_ParseTuple(args, "ll", &a, &b)) {
        return NULL;
    }

    return PyLong_FromLong(a + b);
}

/* Function: multiply two integers */
static PyObject *
fastmath_multiply(PyObject *self, PyObject *args)
{
    long a, b;

    if (!PyArg_ParseTuple(args, "ll", &a, &b)) {
        return NULL;
    }

    return PyLong_FromLong(a * b);
}

/* Method table */
static PyMethodDef fastmath_methods[] = {
    {"add", fastmath_add, METH_VARARGS,
     "Add two integers.\n\nArgs:\n    a: First integer\n    b: Second integer\n\nReturns:\n    Sum of a and b"},
    {"multiply", fastmath_multiply, METH_VARARGS,
     "Multiply two integers."},
    {NULL, NULL, 0, NULL}  /* Sentinel */
};

/* Module definition */
static struct PyModuleDef fastmath_module = {
    PyModuleDef_HEAD_INIT,
    "fastmath",      /* Module name */
    module_doc,      /* Module docstring */
    -1,              /* Size of per-interpreter state (-1 = global) */
    fastmath_methods /* Method table */
};

/* Module initialization function */
PyMODINIT_FUNC
PyInit_fastmath(void)
{
    return PyModule_Create(&fastmath_module);
}
```

## Exercise 2: Keyword Arguments and Error Handling

Add functions with keyword arguments and proper error handling:

```c
/* Function with keyword arguments */
static PyObject *
fastmath_power(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = {"base", "exponent", "modulo", NULL};
    long base, exponent;
    PyObject *modulo_obj = Py_None;

    /*
     * TODO: Parse arguments with PyArg_ParseTupleAndKeywords
     *
     * Format: "ll|O" means:
     *   l - long (base)
     *   l - long (exponent)
     *   | - remaining are optional
     *   O - Python object (modulo)
     */
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "ll|O", kwlist,
                                      &base, &exponent, &modulo_obj)) {
        return NULL;
    }

    /* Validate exponent */
    if (exponent < 0) {
        PyErr_SetString(PyExc_ValueError, "exponent must be non-negative");
        return NULL;
    }

    /* Calculate power */
    long result = 1;
    for (long i = 0; i < exponent; i++) {
        result *= base;
    }

    /* Apply modulo if provided */
    if (modulo_obj != Py_None) {
        if (!PyLong_Check(modulo_obj)) {
            PyErr_SetString(PyExc_TypeError, "modulo must be an integer");
            return NULL;
        }
        long modulo = PyLong_AsLong(modulo_obj);
        if (modulo == 0) {
            PyErr_SetString(PyExc_ZeroDivisionError, "modulo cannot be zero");
            return NULL;
        }
        result = result % modulo;
    }

    return PyLong_FromLong(result);
}

/* Add to method table with METH_VARARGS | METH_KEYWORDS */
{"power", (PyCFunction)fastmath_power, METH_VARARGS | METH_KEYWORDS,
 "Calculate base raised to exponent, optionally with modulo."},
```

## Exercise 3: Working with Lists and Reference Counting

Implement functions that work with Python lists:

```c
/*
 * Function: Sum all elements in a list
 *
 * TODO: Implement proper reference counting
 */
static PyObject *
fastmath_sum_list(PyObject *self, PyObject *args)
{
    PyObject *list_obj;

    if (!PyArg_ParseTuple(args, "O", &list_obj)) {
        return NULL;
    }

    /* Check if it's a list */
    if (!PyList_Check(list_obj)) {
        PyErr_SetString(PyExc_TypeError, "argument must be a list");
        return NULL;
    }

    Py_ssize_t size = PyList_Size(list_obj);
    double sum = 0.0;

    for (Py_ssize_t i = 0; i < size; i++) {
        /* PyList_GetItem returns borrowed reference - no DECREF needed */
        PyObject *item = PyList_GetItem(list_obj, i);

        if (PyLong_Check(item)) {
            sum += PyLong_AsLong(item);
        } else if (PyFloat_Check(item)) {
            sum += PyFloat_AsDouble(item);
        } else {
            PyErr_SetString(PyExc_TypeError, "list must contain only numbers");
            return NULL;
        }
    }

    return PyFloat_FromDouble(sum);
}

/*
 * Function: Create a range list efficiently
 */
static PyObject *
fastmath_range_list(PyObject *self, PyObject *args)
{
    long start, stop, step = 1;

    if (!PyArg_ParseTuple(args, "ll|l", &start, &stop, &step)) {
        return NULL;
    }

    if (step == 0) {
        PyErr_SetString(PyExc_ValueError, "step cannot be zero");
        return NULL;
    }

    /* Calculate list size */
    Py_ssize_t size = 0;
    if (step > 0 && start < stop) {
        size = (stop - start + step - 1) / step;
    } else if (step < 0 && start > stop) {
        size = (start - stop - step - 1) / (-step);
    }

    /* Create list with known size for efficiency */
    PyObject *list = PyList_New(size);
    if (list == NULL) {
        return NULL;  /* Memory allocation failed */
    }

    /* Fill the list */
    long value = start;
    for (Py_ssize_t i = 0; i < size; i++) {
        /* PyLong_FromLong creates new reference */
        PyObject *num = PyLong_FromLong(value);
        if (num == NULL) {
            Py_DECREF(list);  /* Clean up on error */
            return NULL;
        }
        /* PyList_SET_ITEM steals reference - no DECREF needed */
        PyList_SET_ITEM(list, i, num);
        value += step;
    }

    return list;
}
```

## Exercise 4: Releasing the GIL

Implement CPU-intensive operations that release the GIL:

```c
#include <math.h>

/*
 * Function: Calculate prime count up to n (CPU-intensive)
 *
 * TODO: Release GIL during computation
 */
static PyObject *
fastmath_count_primes(PyObject *self, PyObject *args)
{
    long n;

    if (!PyArg_ParseTuple(args, "l", &n)) {
        return NULL;
    }

    if (n < 2) {
        return PyLong_FromLong(0);
    }

    long count = 0;

    /* Release GIL for CPU-intensive work */
    Py_BEGIN_ALLOW_THREADS

    /* Sieve of Eratosthenes */
    char *sieve = (char *)malloc(n + 1);
    if (sieve != NULL) {
        memset(sieve, 1, n + 1);
        sieve[0] = sieve[1] = 0;

        for (long i = 2; i * i <= n; i++) {
            if (sieve[i]) {
                for (long j = i * i; j <= n; j += i) {
                    sieve[j] = 0;
                }
            }
        }

        for (long i = 2; i <= n; i++) {
            if (sieve[i]) count++;
        }

        free(sieve);
    }

    /* Reacquire GIL */
    Py_END_ALLOW_THREADS

    if (sieve == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    return PyLong_FromLong(count);
}

/*
 * Function: Matrix multiply (releases GIL)
 */
static PyObject *
fastmath_matrix_multiply(PyObject *self, PyObject *args)
{
    PyObject *a_obj, *b_obj;

    if (!PyArg_ParseTuple(args, "OO", &a_obj, &b_obj)) {
        return NULL;
    }

    /* Validate inputs are lists of lists */
    if (!PyList_Check(a_obj) || !PyList_Check(b_obj)) {
        PyErr_SetString(PyExc_TypeError, "arguments must be lists");
        return NULL;
    }

    Py_ssize_t a_rows = PyList_Size(a_obj);
    if (a_rows == 0) {
        PyErr_SetString(PyExc_ValueError, "matrices cannot be empty");
        return NULL;
    }

    PyObject *a_row0 = PyList_GetItem(a_obj, 0);
    if (!PyList_Check(a_row0)) {
        PyErr_SetString(PyExc_TypeError, "matrix must be list of lists");
        return NULL;
    }

    Py_ssize_t a_cols = PyList_Size(a_row0);
    Py_ssize_t b_rows = PyList_Size(b_obj);

    PyObject *b_row0 = PyList_GetItem(b_obj, 0);
    Py_ssize_t b_cols = PyList_Size(b_row0);

    if (a_cols != b_rows) {
        PyErr_SetString(PyExc_ValueError, "matrix dimensions don't match");
        return NULL;
    }

    /* Extract data to C arrays */
    double *a_data = malloc(a_rows * a_cols * sizeof(double));
    double *b_data = malloc(b_rows * b_cols * sizeof(double));
    double *c_data = calloc(a_rows * b_cols, sizeof(double));

    if (!a_data || !b_data || !c_data) {
        free(a_data);
        free(b_data);
        free(c_data);
        PyErr_NoMemory();
        return NULL;
    }

    /* Copy data from Python lists */
    for (Py_ssize_t i = 0; i < a_rows; i++) {
        PyObject *row = PyList_GetItem(a_obj, i);
        for (Py_ssize_t j = 0; j < a_cols; j++) {
            PyObject *item = PyList_GetItem(row, j);
            a_data[i * a_cols + j] = PyFloat_AsDouble(item);
        }
    }

    for (Py_ssize_t i = 0; i < b_rows; i++) {
        PyObject *row = PyList_GetItem(b_obj, i);
        for (Py_ssize_t j = 0; j < b_cols; j++) {
            PyObject *item = PyList_GetItem(row, j);
            b_data[i * b_cols + j] = PyFloat_AsDouble(item);
        }
    }

    /* Release GIL for computation */
    Py_BEGIN_ALLOW_THREADS

    for (Py_ssize_t i = 0; i < a_rows; i++) {
        for (Py_ssize_t j = 0; j < b_cols; j++) {
            for (Py_ssize_t k = 0; k < a_cols; k++) {
                c_data[i * b_cols + j] += a_data[i * a_cols + k] * b_data[k * b_cols + j];
            }
        }
    }

    Py_END_ALLOW_THREADS

    /* Build result Python list */
    PyObject *result = PyList_New(a_rows);
    for (Py_ssize_t i = 0; i < a_rows; i++) {
        PyObject *row = PyList_New(b_cols);
        for (Py_ssize_t j = 0; j < b_cols; j++) {
            PyList_SET_ITEM(row, j, PyFloat_FromDouble(c_data[i * b_cols + j]));
        }
        PyList_SET_ITEM(result, i, row);
    }

    free(a_data);
    free(b_data);
    free(c_data);

    return result;
}
```

## Exercise 5: Custom Type Definition

Define a custom Python type:

```c
/*
 * Vector type - a simple 3D vector
 */
typedef struct {
    PyObject_HEAD
    double x;
    double y;
    double z;
} VectorObject;

static void
Vector_dealloc(VectorObject *self)
{
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
Vector_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    VectorObject *self;
    self = (VectorObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->x = 0.0;
        self->y = 0.0;
        self->z = 0.0;
    }
    return (PyObject *)self;
}

static int
Vector_init(VectorObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"x", "y", "z", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|ddd", kwlist,
                                      &self->x, &self->y, &self->z)) {
        return -1;
    }

    return 0;
}

/* Vector methods */
static PyObject *
Vector_magnitude(VectorObject *self, PyObject *Py_UNUSED(ignored))
{
    double mag = sqrt(self->x * self->x +
                      self->y * self->y +
                      self->z * self->z);
    return PyFloat_FromDouble(mag);
}

static PyObject *
Vector_normalize(VectorObject *self, PyObject *Py_UNUSED(ignored))
{
    double mag = sqrt(self->x * self->x +
                      self->y * self->y +
                      self->z * self->z);

    if (mag == 0) {
        PyErr_SetString(PyExc_ZeroDivisionError, "cannot normalize zero vector");
        return NULL;
    }

    VectorObject *result = (VectorObject *)Vector_new(Py_TYPE(self), NULL, NULL);
    if (result != NULL) {
        result->x = self->x / mag;
        result->y = self->y / mag;
        result->z = self->z / mag;
    }

    return (PyObject *)result;
}

static PyObject *
Vector_dot(VectorObject *self, PyObject *args)
{
    VectorObject *other;

    if (!PyArg_ParseTuple(args, "O!", Py_TYPE(self), &other)) {
        return NULL;
    }

    double dot = self->x * other->x +
                 self->y * other->y +
                 self->z * other->z;

    return PyFloat_FromDouble(dot);
}

static PyObject *
Vector_repr(VectorObject *self)
{
    return PyUnicode_FromFormat("Vector(%.2f, %.2f, %.2f)",
                                 self->x, self->y, self->z);
}

/* Number protocol - vector addition */
static PyObject *
Vector_add(PyObject *a, PyObject *b)
{
    if (!PyObject_TypeCheck(a, &VectorType) ||
        !PyObject_TypeCheck(b, &VectorType)) {
        Py_RETURN_NOTIMPLEMENTED;
    }

    VectorObject *va = (VectorObject *)a;
    VectorObject *vb = (VectorObject *)b;

    VectorObject *result = (VectorObject *)Vector_new(&VectorType, NULL, NULL);
    if (result != NULL) {
        result->x = va->x + vb->x;
        result->y = va->y + vb->y;
        result->z = va->z + vb->z;
    }

    return (PyObject *)result;
}

/* Member definitions */
static PyMemberDef Vector_members[] = {
    {"x", T_DOUBLE, offsetof(VectorObject, x), 0, "x component"},
    {"y", T_DOUBLE, offsetof(VectorObject, y), 0, "y component"},
    {"z", T_DOUBLE, offsetof(VectorObject, z), 0, "z component"},
    {NULL}
};

/* Method definitions */
static PyMethodDef Vector_methods[] = {
    {"magnitude", (PyCFunction)Vector_magnitude, METH_NOARGS,
     "Return the magnitude of the vector."},
    {"normalize", (PyCFunction)Vector_normalize, METH_NOARGS,
     "Return a normalized copy of the vector."},
    {"dot", (PyCFunction)Vector_dot, METH_VARARGS,
     "Return the dot product with another vector."},
    {NULL}
};

/* Number methods for operator overloading */
static PyNumberMethods Vector_as_number = {
    .nb_add = Vector_add,
};

/* Type definition */
static PyTypeObject VectorType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "fastmath.Vector",
    .tp_doc = "3D Vector type",
    .tp_basicsize = sizeof(VectorObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = Vector_new,
    .tp_init = (initproc)Vector_init,
    .tp_dealloc = (destructor)Vector_dealloc,
    .tp_repr = (reprfunc)Vector_repr,
    .tp_members = Vector_members,
    .tp_methods = Vector_methods,
    .tp_as_number = &Vector_as_number,
};
```

## Build Setup

Create `setup.py`:

```python
# setup.py
from setuptools import setup, Extension

fastmath_module = Extension(
    'fastmath',
    sources=['fastmath.c'],
    extra_compile_args=['-O3'],
)

setup(
    name='fastmath',
    version='1.0',
    description='Fast math operations in C',
    ext_modules=[fastmath_module],
)
```

Build commands:

```bash
# Build in-place
python setup.py build_ext --inplace

# Or using pip
pip install -e .
```

## Test Script

```python
# test_fastmath.py
import fastmath
import time

def test_basic():
    """Test basic operations."""
    print("=== Basic Operations ===")
    print(f"add(5, 3) = {fastmath.add(5, 3)}")
    print(f"multiply(5, 3) = {fastmath.multiply(5, 3)}")
    print(f"power(2, 10) = {fastmath.power(2, 10)}")
    print(f"power(2, 10, modulo=100) = {fastmath.power(2, 10, modulo=100)}")

def test_lists():
    """Test list operations."""
    print("\n=== List Operations ===")
    nums = [1, 2, 3, 4, 5]
    print(f"sum_list({nums}) = {fastmath.sum_list(nums)}")

    range_list = fastmath.range_list(0, 10, 2)
    print(f"range_list(0, 10, 2) = {range_list}")

def test_gil_release():
    """Test GIL-releasing operations."""
    print("\n=== GIL Release (Prime Counting) ===")

    # Time comparison
    n = 1000000

    start = time.time()
    count = fastmath.count_primes(n)
    elapsed = time.time() - start

    print(f"count_primes({n}) = {count}")
    print(f"Time: {elapsed:.3f}s")

def test_matrix():
    """Test matrix multiplication."""
    print("\n=== Matrix Multiplication ===")

    a = [[1.0, 2.0], [3.0, 4.0]]
    b = [[5.0, 6.0], [7.0, 8.0]]

    result = fastmath.matrix_multiply(a, b)
    print(f"Matrix A: {a}")
    print(f"Matrix B: {b}")
    print(f"A × B = {result}")

def test_vector():
    """Test Vector type."""
    print("\n=== Vector Type ===")

    v1 = fastmath.Vector(1, 2, 3)
    v2 = fastmath.Vector(4, 5, 6)

    print(f"v1 = {v1}")
    print(f"v2 = {v2}")
    print(f"v1.magnitude() = {v1.magnitude():.4f}")
    print(f"v1.normalize() = {v1.normalize()}")
    print(f"v1.dot(v2) = {v1.dot(v2)}")
    print(f"v1 + v2 = {v1 + v2}")

def test_error_handling():
    """Test error handling."""
    print("\n=== Error Handling ===")

    try:
        fastmath.power(2, -1)
    except ValueError as e:
        print(f"Caught ValueError: {e}")

    try:
        fastmath.sum_list("not a list")
    except TypeError as e:
        print(f"Caught TypeError: {e}")

if __name__ == "__main__":
    test_basic()
    test_lists()
    test_gil_release()
    test_matrix()
    test_vector()
    test_error_handling()
```

## Expected Output

```
=== Basic Operations ===
add(5, 3) = 8
multiply(5, 3) = 15
power(2, 10) = 1024
power(2, 10, modulo=100) = 24

=== List Operations ===
sum_list([1, 2, 3, 4, 5]) = 15.0
range_list(0, 10, 2) = [0, 2, 4, 6, 8]

=== GIL Release (Prime Counting) ===
count_primes(1000000) = 78498
Time: 0.015s

=== Matrix Multiplication ===
Matrix A: [[1.0, 2.0], [3.0, 4.0]]
Matrix B: [[5.0, 6.0], [7.0, 8.0]]
A × B = [[19.0, 22.0], [43.0, 50.0]]

=== Vector Type ===
v1 = Vector(1.00, 2.00, 3.00)
v2 = Vector(4.00, 5.00, 6.00)
v1.magnitude() = 3.7417
v1.normalize() = Vector(0.27, 0.53, 0.80)
v1.dot(v2) = 32.0
v1 + v2 = Vector(5.00, 7.00, 9.00)

=== Error Handling ===
Caught ValueError: exponent must be non-negative
Caught TypeError: argument must be a list
```

## Submission

1. Complete all TODO sections
2. Add cross product method to Vector
3. Implement buffer protocol for Vector
4. Bonus: Add SIMD optimizations using intrinsics

---

[Next: Lab 10 - Subinterpreters →](lab-10-subinterpreters.md)
