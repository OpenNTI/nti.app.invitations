#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

from zope import component

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.model import Invitation


class TestAdminViews(ApplicationLayerTest):

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_get_invitations(self):

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = component.getUtility(IInvitationsContainer)
            invitation = Invitation(receiver=u'ichigo',
                                    sender=u'aizen',
                                    expiryTime=180,
                                    code=u"ichigo-aizen")
            invitations.add(invitation)

            invitation = Invitation(receiver=u'toshiro',
                                    sender=u'urahara',
                                    code=u"toshiro-urahara")
            invitations.add(invitation)

            invitation = Invitation(receiver=u'rukia',
                                    sender=u'zaraki',
                                    code=u"rukia-zaraki")
            invitations.add(invitation)

        res = self.testapp.get('/dataserver2/Invitations/@@AllInvitations',
                               status=200)
        assert_that(res.json_body, has_entry('Items', has_length(3)))

        res = self.testapp.get('/dataserver2/Invitations/@@AllInvitations?sender=zaraki',
                               status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

        res = self.testapp.get('/dataserver2/Invitations/@@AllInvitations?receiver=rukia',
                               status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

        res = self.testapp.get('/dataserver2/Invitations/@@AllInvitations?receiver=aizen',
                               status=200)
        assert_that(res.json_body, has_entry('Items', has_length(0)))

        res = self.testapp.get('/dataserver2/Invitations/@@PendingInvitations?receiver=rukia',
                               status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_expired_invitations(self):

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = component.getUtility(IInvitationsContainer)
            invitation = Invitation(receiver=u'ichigo',
                                    sender=u'aizen',
                                    expiryTime=180)
            invitations.add(invitation)

            invitation = Invitation(receiver=u'ichigo',
                                    sender=u'aizen')
            invitations.add(invitation)
            assert_that(invitations, has_length(2))

        res = self.testapp.get('/dataserver2/Invitations/@@ExpiredInvitations?username=ichigo',
                               status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

        res = self.testapp.post_json('/dataserver2/Invitations/@@DeleteExpiredInvitations',
                                     {'username': 'ichigo'},
                                     status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = component.getUtility(IInvitationsContainer)
            assert_that(invitations, has_length(1))
            
    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_rebuild_invitations_catalog(self):

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = component.getUtility(IInvitationsContainer)
            invitation = Invitation(receiver=u'ichigo',
                                    sender=u'aizen',
                                    expiryTime=180)
            invitations.add(invitation)

            invitation = Invitation(receiver=u'ichigo',
                                    sender=u'aizen')
            invitations.add(invitation)

        res = self.testapp.post('/dataserver2/Invitations/@@RebuildInvitationsCatalog',
                                status=200)
        assert_that(res.json_body, has_entry('Total', is_(2)))
