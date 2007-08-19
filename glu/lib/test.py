# -*- coding: utf-8 -*-
'''
File:          test.py

Authors:       Kevin Jacobs (jacobske@bioinformed.com)

Created:

Abstract:      Run glu doctest suite

Requires:      Python 2.5, glu

Revision:      $Id$
'''

import pkg_resources


def test(report=True):
  import os
  import doctest

  import glu
  from   glu.lib import utils,fileutils,association,glm,imerge,sections,sequence,stats
  import utils as local_utils

  # Standardize on the .py source, since one can load the .py and the other the .pyc
  packagefile =  utils.__file__.replace('.pyc','.py')
  localfile   =  local_utils.__file__.replace('.pyc','.py')

  if not os.path.samefile(packagefile,localfile):
    raise ImportError('Your PYTHONPATH is not set correctly to find this GLU tree')

  for module in association,fileutils,glm,imerge,sections,sequence,stats,utils:
    doctest.testmod(module,report=False)

  from glu.lib.genolib.test import test as test_genolib

  test_genolib(False)

  if report:
    doctest.master.summarize()


if __name__ == '__main__':
  test()