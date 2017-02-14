#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

from zope import component

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.model import Invitation

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestAdminViews(ApplicationLayerTest):

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_expired_invitations(self):

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = component.getUtility(IInvitationsContainer)
            invitation = Invitation(receiver='ichigo',
                                    sender='aizen',
                                    expiryTime=180)
            invitations.add(invitation)

            invitation = Invitation(receiver='ichigo',
                                    sender='aizen')
            invitations.add(invitation)
            assert_that(invitations, has_length(2))

        res = self.testapp.get('/dataserver2/@@ExpiredInvitations',
                               status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

        res = self.testapp.post('/dataserver2/@@DeleteExpiredInvitations',
                                status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = component.getUtility(IInvitationsContainer)
            assert_that(invitations, has_length(1))
