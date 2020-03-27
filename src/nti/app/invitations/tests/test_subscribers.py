#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ
import unittest

from hamcrest import is_not, is_
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import not_none
does_not = is_not

import fudge

from pyramid import httpexceptions as hexc

from zope import component

from zope.component import getGlobalSiteManager

from zope.event import notify

from nti.app.invitations import SITE_INVITATION_SESSION_KEY

from nti.app.invitations.invitations import SiteInvitation

from nti.app.invitations.subscribers import _get_invitations_bcc
from nti.app.invitations.subscribers import _validate_site_invitation
from nti.app.invitations.subscribers import require_invite_for_user_creation

from nti.appserver.interfaces import UserLogonEvent

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.invitations.interfaces import InvitationRequiredError

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users.interfaces import WillCreateNewEntityEvent

from nti.dataserver.users.users import User

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
                                    acceptedTime=None)
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
    @fudge.patch('nti.app.invitations.subscribers.get_current_request')
    def test_validate_site_invitation(self, mock_request):
        mock_request.is_callable().returns(self.request)
        with mock_dataserver.mock_db_trans(self.ds):
            ricky = self._create_user(u'ricky', external_value={'email': u'ricky@tpb.net'})
            lahey = self._create_user(u'lahey', external_value={'email': u'lahey@tpb.net'})

        # Make sure no exceptions are raised without an invitation
        try:
            event = UserLogonEvent(ricky)
            _validate_site_invitation(ricky)
        except Exception as e:
            self.fail(u'Unexpected exception in subscriber. %s' % e.message)

        # Test failed acceptance
        with mock_dataserver.mock_db_trans(self.ds):
            invitation = SiteInvitation(code=u'Sunnyvale1',
                                        sender=u'lahey',
                                        receiver=u'ricky@tpb.net',
                                        target_site=u'dataserver2')
            invitations = component.getUtility(IInvitationsContainer)
            invitations.add(invitation)

            self.request.session[SITE_INVITATION_SESSION_KEY] = invitation.code
            with self.assertRaises(hexc.HTTPSeeOther):
                _validate_site_invitation(lahey)

        # Test valid acceptance
        with mock_dataserver.mock_db_trans(self.ds):
            self.request.session[SITE_INVITATION_SESSION_KEY] = invitation.code
            _validate_site_invitation(ricky)
            ricky_invites = get_invitations(receivers=u'ricky')
            assert_that(ricky_invites, has_length(1))
            invite = ricky_invites[0]
            assert_that(invite.is_accepted(), is_(True))
            assert_that(invite.acceptedTime, not_none())
            assert_that(invite.receiver, is_(u'ricky'))
            assert_that(invite.sender, is_(u'lahey'))

        # Test new invitation code
        with mock_dataserver.mock_db_trans(self.ds):
            self.request.session[SITE_INVITATION_SESSION_KEY] = invitation.code
            invitations = component.getUtility(IInvitationsContainer)
            invitations.remove(invitation)
            invitation = SiteInvitation(code=u'Sunnyvale2',
                                        sender=u'lahey',
                                        receiver=u'ricky@tpb.net',
                                        target_site=u'dataserver2')
            invitations.add(invitation)
            _validate_site_invitation(ricky)
            ricky_invites = get_invitations(receivers=u'ricky')
            assert_that(ricky_invites, has_length(1))
            invite = ricky_invites[0]
            assert_that(invite.is_accepted(), is_(True))
            assert_that(invite.acceptedTime, not_none())
            assert_that(invite.receiver, is_(u'ricky'))
            assert_that(invite.sender, is_(u'lahey'))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.invitations.subscribers.get_current_request')
    def test_invitation_required_for_user_creation(self, mock_request):

        with mock_dataserver.mock_db_trans(self.ds):
            mock_request.is_callable().returns(self.request)
            user = self._create_user(u'testuser', external_value={'email': u'user@test.com'})

            # Test the subscriber
            event = WillCreateNewEntityEvent(user)
            event.request = self.request
            with self.assertRaises(InvitationRequiredError):
                require_invite_for_user_creation(user, event)

            # Test the subscriber isn't hit without zcml registration
            try:
                notify(event)
            except Exception as e:
                self.fail(u'Unexpected exception in subscriber. %s' % e.message)

            # Test the subscriber raises without invitation code
            gsm = getGlobalSiteManager()
            gsm.registerHandler(require_invite_for_user_creation)
            with self.assertRaises(InvitationRequiredError):
                notify(event)

            # Test the subscriber is silent when conditions are satisfied
            invitations = component.getUtility(IInvitationsContainer)
            invitation = SiteInvitation(code=u'code',
                                        sender=u'sjohnson@nextthought.com',
                                        receiver=u'user@test.com',
                                        target_site=u'dataserver2')
            invitations.add(invitation)
            self.request.session[SITE_INVITATION_SESSION_KEY] = u'code'
            try:
                notify(event)
            except Exception as e:
                self.fail(u'Unexpected exception in subscriber. %s' % e.message)

            gsm.unregisterHandler(require_invite_for_user_creation)


class TestInvitationsBcc(unittest.TestCase):

    @fudge.patch('nti.app.invitations.subscribers._get_app_setting')
    def test_invitations_bcc_none(self, get_app_setting):
        get_app_setting.is_callable().returns(None)
        assert_that(_get_invitations_bcc(), is_(()))

    @fudge.patch('nti.app.invitations.subscribers._get_app_setting')
    def test_invitations_bcc_empty(self, get_app_setting):
        get_app_setting.is_callable().returns("")
        assert_that(_get_invitations_bcc(), is_(()))

    @fudge.patch('nti.app.invitations.subscribers._get_app_setting')
    def test_invitations_bcc_unstripped(self, get_app_setting):
        get_app_setting.is_callable().returns(" follow@whiterabbit.org ")
        assert_that(_get_invitations_bcc(), is_(("follow@whiterabbit.org",)))

    @fudge.patch('nti.app.invitations.subscribers._get_app_setting')
    def test_invitations_bcc_invalid(self, get_app_setting):
        get_app_setting.is_callable().returns(" cheshire@wl.org , @xyz123")
        assert_that(_get_invitations_bcc(), is_(("cheshire@wl.org",)))

    @fudge.patch('nti.app.invitations.subscribers._get_app_setting')
    def test_invitations_bcc_multi(self, get_app_setting):
        get_app_setting.is_callable().returns("hatter@wl.org, cheshire@wl.org , @xyz123,")
        assert_that(_get_invitations_bcc(), is_(("hatter@wl.org", "cheshire@wl.org",)))
