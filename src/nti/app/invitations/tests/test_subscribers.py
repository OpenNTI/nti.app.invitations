#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_not, is_
from hamcrest import has_length
from hamcrest import assert_that
from zope.component import getGlobalSiteManager
from zope.event import notify

from nti.app.invitations import SITE_INVITATION_SESSION_KEY
from nti.app.invitations.interfaces import InvitationRequiredError
from nti.app.invitations.invitations import SiteInvitation
from nti.app.invitations.subscribers import _validate_site_invitation, _require_invite_for_user_creation
from nti.app.testing.request_response import DummyRequest
from nti.appserver.interfaces import UserCreatedWithRequestEvent

does_not = is_not

from zope import component

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users.users import User

from nti.invitations.interfaces import InvitationValidationError
from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.model import Invitation

from nti.invitations.utils import get_invitations
from nti.invitations.utils import get_sent_invitations
from nti.invitations.utils import get_pending_invitations


class TestSubscribers(ApplicationLayerTest):

    @WithSharedApplicationMockDS
    def test_user_deletion_event(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u"aizen", external_value={'email': u"aizen@nti.com"})
            self._create_user(u"ichigo", external_value={'email': u"ichigo@nti.com"})
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

    @WithSharedApplicationMockDS
    def test_validate_site_invitation(self):
        with mock_dataserver.mock_db_trans(self.ds):
            ricky = self._create_user(u'ricky', external_value={'email': u'ricky@tpb.net'})
            lahey = self._create_user(u'lahey', external_value={'email': u'lahey@tpb.net'})

        # Make sure no exceptions are raised without an invitation
        try:
            request = DummyRequest()
            event = UserCreatedWithRequestEvent(ricky, request)
            _validate_site_invitation(ricky, event)
        except Exception:
            self.fail(u'Unexpected exception in subscriber.')

        # Test failed acceptance
        with mock_dataserver.mock_db_trans(self.ds):
            invitation = SiteInvitation(code=u'Sunnyvale1',
                                        sender=u'lahey',
                                        receiver=u'ricky@tpb.net')
            invitations = component.getUtility(IInvitationsContainer)
            invitations.add(invitation)

            event.request.session[SITE_INVITATION_SESSION_KEY] = invitation.code
            with self.assertRaises(InvitationValidationError):
                _validate_site_invitation(lahey, event)

        # Test valid acceptance
        with mock_dataserver.mock_db_trans(self.ds):
            event.request.session[SITE_INVITATION_SESSION_KEY] = invitation.code
            _validate_site_invitation(ricky, event)
            ricky_invites = get_invitations(receivers=u'ricky')
            assert_that(ricky_invites, has_length(1))
            invite = ricky_invites[0]
            assert_that(invite.is_accepted(), is_(True))
            assert_that(invite.receiver, is_(u'ricky'))
            assert_that(invite.sender, is_(u'lahey'))

    @WithSharedApplicationMockDS
    def test_invitation_required_for_user_creation(self):

        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user(u'testuser', external_value={'email': u'user@test.com'})

        # Test the subscriber
        request = DummyRequest()
        event = UserCreatedWithRequestEvent(user, request)
        with self.assertRaises(InvitationRequiredError):
            _require_invite_for_user_creation(user, event)

        # Test the subscriber isn't hit without zcml registration
        try:
            notify(event)
        except Exception:
            self.fail(u'Unexpected exception in subscriber.')

        gsm = getGlobalSiteManager()
        gsm.registerHandler(_require_invite_for_user_creation)
        with self.assertRaises(InvitationRequiredError):
            notify(event)

        event.request.session[SITE_INVITATION_SESSION_KEY] = u'code'
        try:
            notify(event)
        except Exception:
            self.fail(u'Unexpected exception in subscriber.')

        gsm.unregisterHandler(_require_invite_for_user_creation)
