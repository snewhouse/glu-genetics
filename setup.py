#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# To use:
#       python setup.py install
#

import os
import sys


from ez_setup import use_setuptools
use_setuptools()


# minimum versions required
min_python_version = (2,5)
min_numpy_version  = '1.0.2'

if sys.version_info < min_python_version:
  sys.stderr.write('Python 2.5 or newer to required to install and run GLU!\n')
  sys.exit(1)

import distutils
from   setuptools     import setup, find_packages, Extension

import numpy

classifiers = '''\
Development Status :: 5 - Production/Stable
Intended Audience :: Developers
Intended Audience :: Information Technology
Intended Audience :: Science/Research
License :: OSI Approved :: BSD License
Programming Language :: Python
Topic :: Database
Topic :: Software Development :: Libraries :: Python Modules
Operating System :: Microsoft :: Windows
Operating System :: Unix
'''

setup (name             = 'glu',
       version          = '0.52',
       author           = 'Kevin Jacobs',
       author_email     = 'jacobske@mail.nih.gov',
       maintainer       = 'Kevin Jacobs',
       maintainer_email = 'jacobske@mail.nih.gov',
       platforms        = ['any'],
       description      = 'Genotype Library and Utilities (GLU)',
       long_description = ('Genotype Library and Utilities (GLU): Tools for the management of large '
                           'amounts of SNP genotype data and programs to check its quality and to '
                           'test for association between SNP markers with continuous or discrete '
                           'trait phenotypes.'),
       classifiers      = filter(None, classifiers.split('\n')),
       install_requires = ['numpy>=%s' % min_numpy_version],
       setup_requires   = ['numpy>=%s' % min_numpy_version],
       packages         = find_packages(),
       scripts          = ['bin/glu'],
       #entry_points    = { 'console_scripts':['glu = glu.lib.glu_launcher:main'] },
       zip_safe         = True,
       ext_modules = [ Extension('glu.lib.bitarrayc',        ['glu/lib/bitarrayc.c']),
                       Extension('glu.lib._genoarray',       ['glu/lib/_genoarray.c','glu/lib/bitarrayc.c'],
                                                                   include_dirs = [numpy.get_include()]),
                       Extension('glu.modules.qc.dupcheckc',       sources = ['glu/modules/qc/dupcheckc.c']),
                       Extension('glu.modules.tagzilla.tagzillac', sources = ['glu/modules/tagzilla/tagzillac.c']),
                       Extension('glu.modules.tagzilla.pqueue',    sources = ['glu/modules/tagzilla/pqueue.c']),
                     ])
