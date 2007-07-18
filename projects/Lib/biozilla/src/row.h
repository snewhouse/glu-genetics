/*
File:          row.c

Author:        Kevin Jacobs (jacobs@theopalgroup.com)

Created:       June 3, 2002

Purpose:       A faster and better database result object

Compatibility: Python 2.2+

Requires:

Revision:      $Id: row.h 202 2006-06-13 18:17:19Z jacobske $

Copyright (c) 2001,2002 The OPAL Group.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.
*/

#ifndef Py_ROWOBJECT_H
#define Py_ROWOBJECT_H

#ifdef __cplusplus
extern "C" {
#endif

extern PyTypeObject PyRow_Type;

#define PyRow_Check(op) PyObject_TypeCheck(op, &PyRow_Type)
#define PyRow_CheckExact(op) ((op)->ob_type == &PyRow_Type)

#if PY_VERSION_HEX < 0x02030000
extern PyObject* db_row_subscript_wrap(PyObject* row, PyObject* args);
#endif

#ifdef __cplusplus
}
#endif

#endif /* !Py_ROWOBJECT_H */
