#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

import unittest

from zope.dottedname import resolve as dottedname


class TestInterfaces(unittest.TestCase):

    def test_import(self):
        dottedname.resolve('nti.app.invitations.interfaces')
