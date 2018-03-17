#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import has_key
from hamcrest import assert_that

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

class TestFunctionalInstall(ApplicationLayerTest):

    @mock_dataserver.WithMockDSTrans
    def test_installed(self):
        conn = mock_dataserver.current_transaction
        root = conn.root()
        generations = root['zope.generations']
        assert_that(generations, has_key('nti.dataserver-app-invitations'))
