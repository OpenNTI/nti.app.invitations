#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

from zope import component

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users.users import User

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.model import Invitation

from nti.invitations.utils import get_sent_invitations
from nti.invitations.utils import get_pending_invitations


class TestSubscribers(ApplicationLayerTest):

    @WithSharedApplicationMockDS
    def test_user_deletion_event(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u"aizen")
            self._create_user(u"ichigo")
            invitation = Invitation(code=u'bleach',
                                    receiver=u'ichigo',
                                    sender=u'aizen',
                                    accepted=False)
            component.getUtility(IInvitationsContainer).add(invitation)

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = get_sent_invitations(u'aizen')
            assert_that(invitations, has_length(1))

            invitations = get_pending_invitations()
            assert_that(invitations, has_length(1))

        with mock_dataserver.mock_db_trans(self.ds):
            User.delete_entity(u"aizen")

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = get_sent_invitations(u'aizen')
            assert_that(invitations, has_length(0))

            invitations = get_pending_invitations()
            assert_that(invitations, has_length(0))

            container = component.getUtility(IInvitationsContainer)
            assert_that(container, has_length(0))
