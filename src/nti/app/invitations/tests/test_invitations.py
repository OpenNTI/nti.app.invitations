#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import assert_that
from hamcrest import has_length
from hamcrest import is_

from zope import component

from nti.app.invitations.interfaces import IVerifyAndAcceptSiteInvitation
from nti.app.invitations.invitations import JoinEntityInvitation
from nti.app.invitations.invitations import JoinEntityInvitationActor
from nti.app.invitations.invitations import JoinSiteInvitation

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.coremetadata.interfaces import IUser

from nti.dataserver.tests import mock_dataserver

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.utils import get_pending_invitations
from nti.invitations.utils import get_sent_invitations


class TesInvitations(ApplicationLayerTest):

    @WithSharedApplicationMockDS
    def test_validation(self):

        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user()
            actor = JoinEntityInvitationActor()
            # missing entity
            invitation = JoinEntityInvitation()
            invitation.entity = 'invalid'
            invitation.receiver = self.default_username
            assert_that(actor.accept(user, invitation),
                        is_(False))
            # invalid entity
            invitation.entity = self.default_username
            invitation.receiver = self.default_username
            assert_that(actor.accept(user, invitation),
                        is_(False))

    @WithSharedApplicationMockDS
    def test_verify_and_accept_invitation(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u"aizen", external_value={'email': u"aizen@nti.com"})
            invitation = JoinSiteInvitation(code=u'bleach',
                                            receiver=u'ichigo@nti.com',
                                            sender=u'aizen',
                                            accepted=False,
                                            target_site=u'dataserver2')
            component.getUtility(IInvitationsContainer).add(invitation)

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = get_sent_invitations(u'aizen')
            assert_that(invitations, has_length(1))

            invitations = get_pending_invitations()
            assert_that(invitations, has_length(1))

        with mock_dataserver.mock_db_trans(self.ds):
            # The user accepts the invitation and now has an account
            user = self._create_user(u"ichigo", external_value={'email': u"ichigo@nti.com"})
            accepter = IVerifyAndAcceptSiteInvitation(user)
            accepter.accept(invitation)

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = get_sent_invitations(u'aizen')
            assert_that(invitations, has_length(0))

            invitations = get_pending_invitations()
            assert_that(invitations, has_length(0))

            container = component.getUtility(IInvitationsContainer)
            assert_that(container, has_length(1))
