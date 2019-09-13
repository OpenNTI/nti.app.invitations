#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than
does_not = is_not

from zope import component

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.invitations.predicates import UserInvitationsObjects
from nti.app.invitations.predicates import SystemInvitationsObjects

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.dataserver.tests import mock_dataserver

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.model import Invitation


class TestPredicates(ApplicationLayerTest):

    @mock_dataserver.WithMockDSTrans
    def test_system(self):
        invitations = component.getUtility(IInvitationsContainer)
        invitation = Invitation(receiver=u"ichigo@bleach.org",
                                sender=SYSTEM_USER_ID)
        invitations.add(invitation)

        predicate = SystemInvitationsObjects()
        assert_that(list(predicate.iter_objects()),
                    has_length(greater_than(0)))

    @mock_dataserver.WithMockDSTrans
    def test_user(self):
        self._create_user(self.default_username)

        invitations = component.getUtility(IInvitationsContainer)
        invitation = Invitation(receiver=u"ichigo@bleach.org",
                                sender=self.default_username)
        invitations.add(invitation)

        predicate = UserInvitationsObjects(self.default_username)
        assert_that(list(predicate.iter_objects()),
                    has_length(greater_than(0)))
