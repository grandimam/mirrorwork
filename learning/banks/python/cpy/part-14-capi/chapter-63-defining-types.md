# Chapter 63: Defining Types in C

## 63.1 Custom Type Structure

```c
typedef struct {
    PyObject_HEAD
    double x;
    double y;
} PointObject;

static PyTypeObject PointType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "point.Point",
    .tp_doc = "Point objects",
    .tp_basicsize = sizeof(PointObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = PyType_GenericNew,
    .tp_init = (initproc)Point_init,
    .tp_dealloc = (destructor)Point_dealloc,
    .tp_members = Point_members,
    .tp_methods = Point_methods,
};
```

## 63.2 Type Methods

```c
static int
Point_init(PointObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"x", "y", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|dd", kwlist,
                                      &self->x, &self->y))
        return -1;
    return 0;
}

static void
Point_dealloc(PointObject *self)
{
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
Point_distance(PointObject *self, PyObject *Py_UNUSED(ignored))
{
    double dist = sqrt(self->x * self->x + self->y * self->y);
    return PyFloat_FromDouble(dist);
}
```

## 63.3 Members and Getsets

```c
static PyMemberDef Point_members[] = {
    {"x", T_DOUBLE, offsetof(PointObject, x), 0, "x coordinate"},
    {"y", T_DOUBLE, offsetof(PointObject, y), 0, "y coordinate"},
    {NULL}
};

static PyGetSetDef Point_getsets[] = {
    {"magnitude", (getter)Point_get_magnitude, NULL, "distance from origin", NULL},
    {NULL}
};
```

## Summary

- Define struct extending PyObject_HEAD
- Initialize PyTypeObject with slots
- Implement tp_init, tp_dealloc, methods
- Use PyMemberDef for direct attribute access

---

[Next: Embedding Python →](chapter-64-embedding.md)
