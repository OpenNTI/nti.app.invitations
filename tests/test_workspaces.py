#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than
does_not = is_not

from nti.appserver.workspaces import UserService

from nti.dataserver.users import User

from nti.externalization.externalization import toExternalObject

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver


class TestUserService(ApplicationLayerTest):

    @mock_dataserver.WithMockDSTrans
    def test_external(self):
        user = User.create_user(dataserver=self.ds,
                                username=u'sjohnson@nextthought.com')
        service = UserService(user)
        ext_object = toExternalObject(service)

        assert_that(ext_object['Items'],
                    has_item(has_entry('Title','Invitations')))
        invitations_wss = [
            x for x in ext_object['Items'] if x['Title'] == 'Invitations'
        ]
        assert_that(invitations_wss, has_length(1))
        invitations_wss, = invitations_wss
        assert_that(invitations_wss['Items'],
                    has_item(has_entry('Links', has_length(greater_than(0)))))
