#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than
does_not = is_not

from zope import component

from nti.app.invitations.interfaces import IInvitationsWorkspace

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.appserver.workspaces import UserService

from nti.dataserver.tests import mock_dataserver

from nti.externalization.externalization import toExternalObject

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.model import Invitation


class TestUserService(ApplicationLayerTest):

    def _create_invitations(self):
        invitations = component.getUtility(IInvitationsContainer)
        invitation = Invitation(receiver='ossmkitty',
                                sender=self.default_username,
                                accepted=True,
                                code="accepted")
        invitations.add(invitation)

        invitation = Invitation(receiver='ichigo',
                                sender=self.default_username,
                                code="123456")
        invitations.add(invitation)

        invitation = Invitation(receiver=self.default_username,
                                sender='aizen',
                                code="7890")
        invitations.add(invitation)

    @mock_dataserver.WithMockDSTrans
    def test_external(self):
        user = self._create_user(external_value={'email': u"steve@nti.com"})
        self._create_invitations()
        # find the workspace
        invitations_wss = None
        service = UserService(user)
        for ws in service.workspaces or ():
            if IInvitationsWorkspace.providedBy(ws):
                invitations_wss = ws
                break
        assert_that(invitations_wss, is_not(none()))
        assert_that(invitations_wss, has_length(1))
        # coverage
        assert_that(invitations_wss[''], is_not(none()))
        # externalize
        ext_object = toExternalObject(service)
        assert_that(ext_object['Items'],
                    has_item(has_entry('Title', 'Invitations')))
        invitations_wss = [
            x for x in ext_object['Items'] if x['Title'] == 'Invitations'
        ]
        assert_that(invitations_wss, has_length(1))
        invitations_wss, = invitations_wss
        assert_that(invitations_wss['Items'],
                    has_item(has_entry('Links', has_length(greater_than(0)))))
