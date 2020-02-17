#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import assert_that
from hamcrest import has_length
from hamcrest import is_

import time
from hamcrest import is_not
from nti.app.invitations.utils import accept_site_invitation_by_code
from nti.dataserver.users.interfaces import IUserProfile

from zope import component
from zope import interface

from nti.app.invitations import GENERIC_SITE_INVITATION_MIMETYPE
from nti.app.invitations import SITE_INVITATION_MIMETYPE

from nti.app.invitations.invitations import DefaultGenericSiteInvitationActor
from nti.app.invitations.invitations import DefaultSiteAdminInvitationActor
from nti.app.invitations.invitations import DefaultSiteInvitationActor
from nti.app.invitations.invitations import GenericSiteInvitation
from nti.app.invitations.invitations import JoinEntityInvitation
from nti.app.invitations.invitations import JoinEntityInvitationActor
from nti.app.invitations.invitations import SiteAdminInvitation
from nti.app.invitations.invitations import SiteInvitation

from nti.app.invitations.utils import accept_site_invitation

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.authorization import is_site_admin

from nti.dataserver.tests import mock_dataserver

from nti.invitations.interfaces import IDisabledInvitation
from nti.invitations.interfaces import InvitationEmailNotMatchingError
from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import InvitationAlreadyAcceptedError
from nti.invitations.interfaces import InvitationDisabledError
from nti.invitations.interfaces import InvitationExpiredError
from nti.invitations.interfaces import InvitationSiteNotMatchingError

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
    def test_site_invitation_actor(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u"lahey", external_value={'email': u"lahey@tpb.net"})
            invitation = SiteInvitation(code=u'Sunnyvale1',
                                        receiver=u'ricky@tpb.net',
                                        sender=u'lahey',
                                        target_site=u'dataserver2')
            component.getUtility(IInvitationsContainer).add(invitation)

        # Test a successful acceptance
        with mock_dataserver.mock_db_trans(self.ds):
            actor = DefaultSiteInvitationActor()
            invitations = get_sent_invitations(u'lahey')
            assert_that(invitations, has_length(1))

            invitations = get_pending_invitations()
            assert_that(invitations, has_length(1))

            # The user has been created
            ricky_user = self._create_user(u"ricky", external_value={'email': u"ricky_too@tpb.net"})
            actor.link_email = u"ricky@tpb.net"
            result = actor.accept(ricky_user, invitation)
            assert_that(result, is_(True))
            assert_that(invitation.is_accepted(), is_(True))
            assert_that(invitation.receiver, is_(ricky_user.username))
            assert_that(invitation.original_receiver, is_(u'ricky@tpb.net'))

            invitations = get_sent_invitations(u'lahey')
            assert_that(invitations, has_length(0))

            invitations = get_pending_invitations()
            assert_that(invitations, has_length(0))

            container = component.getUtility(IInvitationsContainer)
            assert_that(container, has_length(1))

        # Test wrong user email for invite
        with mock_dataserver.mock_db_trans(self.ds):
            actor = DefaultSiteInvitationActor()
            invitation = SiteInvitation(code=u'Sunnyvale2',
                                        receiver=u'julian@tpb.net',
                                        sender=u'lahey',
                                        target_site=u'dataserver2',
                                        require_matching_email=True)
            component.getUtility(IInvitationsContainer).add(invitation)
            with self.assertRaises(InvitationEmailNotMatchingError):
                actor.accept(ricky_user, invitation)

            assert_that(invitation.is_accepted(), is_(False))
            assert_that(invitation.receiver, is_(u'julian@tpb.net'))
            assert_that(invitation.require_matching_email, is_(True))

            invitations = get_sent_invitations(u'lahey')
            assert_that(invitations, has_length(1))
            invitations = get_pending_invitations()
            assert_that(invitations, has_length(1))
            container = component.getUtility(IInvitationsContainer)
            assert_that(container, has_length(2))

            julian_user = self._create_user(u"julian", external_value={'email': u"julian@tpb.net"})
            assert_that(invitation.original_receiver, is_(u'julian@tpb.net'))
            result = actor.accept(julian_user, invitation)
            assert_that(result, is_(True))
            assert_that(invitation.is_accepted(), is_(True))
            assert_that(invitation.receiver, is_(julian_user.username))

        # Test different user email for invite that doesn't require match
        with mock_dataserver.mock_db_trans(self.ds):
            actor = DefaultSiteInvitationActor()
            invitation = SiteInvitation(code=u'Sunnyvale3',
                                        receiver=u'mmouse@tpb.net',
                                        sender=u'lahey',
                                        target_site=u'dataserver2')
            component.getUtility(IInvitationsContainer).add(invitation)

            mmouse_user = self._create_user(u"mmouse", external_value={'email': u"mmouse@tpb.net"})

            result = actor.accept(mmouse_user, invitation)

            assert_that(result, is_(True))
            assert_that(invitation.is_accepted(), is_(True))
            assert_that(invitation.receiver, is_(mmouse_user.username))
            assert_that(invitation.require_matching_email, is_(False))

            invitations = get_sent_invitations(u'lahey')
            assert_that(invitations, has_length(0))
            invitations = get_pending_invitations()
            assert_that(invitations, has_length(0))
            container = component.getUtility(IInvitationsContainer)
            assert_that(container, has_length(3))


    @WithSharedApplicationMockDS
    def test_generic_site_invitation_actor(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u"lahey", external_value={'email': u"lahey@tpb.net"})
            invitation = GenericSiteInvitation(code=u'Sunnyvale',
                                               sender=u'lahey',
                                               target_site=u'dataserver2')
            component.getUtility(IInvitationsContainer).add(invitation)
            actor = DefaultGenericSiteInvitationActor()

        # Test a successful acceptance
        with mock_dataserver.mock_db_trans(self.ds):
            invitations = get_sent_invitations(u'lahey')
            assert_that(invitations, has_length(1))

            invitations = get_pending_invitations(mimeTypes=SITE_INVITATION_MIMETYPE)
            assert_that(invitations, has_length(0))

            invitations = get_pending_invitations(mimeTypes=GENERIC_SITE_INVITATION_MIMETYPE)
            assert_that(invitations, has_length(1))

            # The user has been created
            ricky_user = self._create_user(u"ricky", external_value={'email': u"ricky@tpb.net"})
            result = actor.accept(ricky_user, invitation)
            assert_that(result, is_(True))
            assert_that(invitation.is_accepted(), is_(False))
            assert_that(invitation.receiver, is_(None))
            assert_that(invitation.sender, is_(u'lahey'))

            invitations = get_sent_invitations(u'lahey', mimeTypes=SITE_INVITATION_MIMETYPE, accepted=True)
            assert_that(invitations, has_length(1))
            ricky_invite = invitations[0]
            assert_that(ricky_invite.is_accepted(), is_(True))
            assert_that(ricky_invite.receiver, is_(ricky_user.username))
            assert_that(ricky_invite.sender, is_(u'lahey'))

            invitations = get_sent_invitations(u'lahey', mimeTypes=GENERIC_SITE_INVITATION_MIMETYPE)
            assert_that(invitations, has_length(1))

            invitations = get_pending_invitations(u'lahey', mimeTypes=SITE_INVITATION_MIMETYPE)
            assert_that(invitations, has_length(0))

    @WithSharedApplicationMockDS(users=True)
    def test_site_admin_invitation_actor(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u"lahey", external_value={'email': u"lahey@tpb.net"})
            invitation = SiteAdminInvitation(code=u'Sunnyvale1',
                                             receiver=u'ricky@tpb.net',
                                             sender=u'sjohnson@nextthought.com',
                                             require_matching_email=True,
                                             target_site=u'dataserver3')
            component.getUtility(IInvitationsContainer).add(invitation)

        # Test a successful acceptance, non-matching e-mail
        with mock_dataserver.mock_db_trans(self.ds):
            actor = DefaultSiteAdminInvitationActor()
            invitations = get_sent_invitations(u'sjohnson@nextthought.com')
            assert_that(invitations, has_length(1))

            invitations = get_pending_invitations()
            assert_that(invitations, has_length(1))

            # The user has been created
            ricky_user = self._create_user(u"ricky", external_value={'email': u"ricky_too@tpb.net"})

            # Fails b/c require_matching_email is True and created user
            # email doesn't match
            with self.assertRaises(InvitationEmailNotMatchingError):
                actor.accept(ricky_user, invitation)

            # Even with ISiteInvitation.require_matching_email unset, if
            # there's no e-mail associated with the link, the account e-mail
            # must match
            invitation.require_matching_email = False
            with self.assertRaises(InvitationEmailNotMatchingError):
                actor.accept(ricky_user, invitation)

            # Link email must match what was on the invitation, this is sent
            # as part of the link.
            with self.assertRaises(InvitationEmailNotMatchingError):
                actor.link_email = u"ricky_too@tpb.net"
                actor.accept(ricky_user, invitation)

            # Site doesn't match
            with self.assertRaises(InvitationSiteNotMatchingError):
                actor.link_email = u"ricky@tpb.net"
                actor.accept(ricky_user, invitation)

            invitation.target_site = u"dataserver2"
            assert_that(invitation.original_receiver, is_(u'ricky@tpb.net'))
            result = actor.accept(ricky_user, invitation)
            assert_that(result, is_(True))
            assert_that(invitation.is_accepted(), is_(True))
            assert_that(invitation.receiver, is_(ricky_user.username))
            assert_that(invitation.original_receiver, is_(u'ricky@tpb.net'))

            assert_that(is_site_admin(ricky_user), is_(True))
            invitations = get_sent_invitations(u'sjohnson@nextthought.com')
            assert_that(invitations, has_length(0))

            invitations = get_pending_invitations()
            assert_that(invitations, has_length(0))

            container = component.getUtility(IInvitationsContainer)
            assert_that(container, has_length(1))

        # Test non-matching-email
        with mock_dataserver.mock_db_trans(self.ds):
            actor = DefaultSiteAdminInvitationActor()
            invitation = SiteAdminInvitation(code=u'Sunnyvale2',
                                             receiver=u'bobby@tpb.net',
                                             sender=u'sjohnson@nextthought.com',
                                             target_site=u'dataserver2',
                                             require_matching_email=True)

            component.getUtility(IInvitationsContainer).add(invitation)
            with self.assertRaises(InvitationEmailNotMatchingError):
                actor.accept(ricky_user, invitation)

            assert_that(invitation.is_accepted(), is_(False))
            assert_that(invitation.receiver, is_(u'bobby@tpb.net'))

            invitations = get_sent_invitations(u'sjohnson@nextthought.com')
            assert_that(invitations, has_length(1))

            invitations = get_pending_invitations()
            assert_that(invitations, has_length(1))

            # The user has been created
            bobby_user = self._create_user(u"bobby", external_value={'email': u"bobby@tpb.net"})
            actor.accept(bobby_user, invitation)

            assert_that(result, is_(True))
            assert_that(invitation.is_accepted(), is_(True))
            assert_that(invitation.receiver, is_(bobby_user.username))

            invitations = get_sent_invitations(u'sjohnson@nextthought.com')
            assert_that(invitations, has_length(0))

            invitations = get_pending_invitations()
            assert_that(invitations, has_length(0))

            container = component.getUtility(IInvitationsContainer)
            assert_that(container, has_length(2))

    @WithSharedApplicationMockDS
    def test_accept_site_invitation(self):
        # Test expired site invitation
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u"lahey", external_value={'email': u"lahey@tpb.net"})
            invitation = SiteInvitation(code=u'Sunnyvale1',
                                        receiver=u'ricky@tpb.net',
                                        sender=u'lahey',
                                        expiryTime=(time.time() - 1000))
            ricky_user = self._create_user(u"ricky", external_value={'email': u"ricky@tpb.net"})
            with self.assertRaises(InvitationExpiredError):
                accept_site_invitation(ricky_user, invitation, None)

        # Test accepted site invitation
        with mock_dataserver.mock_db_trans(self.ds):
            invitation = SiteInvitation(code=u'Sunnyvale1',
                                        receiver=u'ricky@tpb.net',
                                        sender=u'lahey',
                                        accepted=True)
            with self.assertRaises(InvitationAlreadyAcceptedError):
                accept_site_invitation(ricky_user, invitation, None)

        # Test expired site invitation
        with mock_dataserver.mock_db_trans(self.ds):
            invitation = SiteInvitation(code=u'Sunnyvale1',
                                        receiver=u'ricky@tpb.net',
                                        sender=u'lahey')
            interface.alsoProvides(invitation, IDisabledInvitation)
            with self.assertRaises(InvitationDisabledError):
                accept_site_invitation(ricky_user, invitation, None)

    def _test_site_invitation_by_code(self,
                                      sending_user,
                                      receiving_user,
                                      code,
                                      invite_email,
                                      link_email=None):
        invitation = SiteInvitation(code=code,
                                    receiver=invite_email,
                                    sender=sending_user.username,
                                    target_site=u'dataserver2')
        component.getUtility(IInvitationsContainer).add(invitation)

        accept_site_invitation_by_code(receiving_user, code, link_email or invite_email)

        return invitation

    @WithSharedApplicationMockDS
    def test_accept_site_invitation_by_code(self):
        with mock_dataserver.mock_db_trans(self.ds):
            sender = self._create_user(u"lahey", external_value={'email': u"lahey@tpb.net"})
            receiver = self._create_user(u"ricky", external_value={'email': u"ricky@home.net"})

        # If account email differs from invitation email, it's not verified
        with mock_dataserver.mock_db_trans(self.ds):
            invitation = self._test_site_invitation_by_code(sender,
                                                            receiver,
                                                            code=u"code.1",
                                                            invite_email=u"ricky@tpb.net")

            assert_that(invitation.is_accepted(), is_(True))
            assert_that(IUserProfile(receiver).email_verified, is_not(True))


        # If account email matches invitation email, assert it's verified
        with mock_dataserver.mock_db_trans(self.ds):
            invitation = self._test_site_invitation_by_code(sender,
                                                            receiver,
                                                            code=u"code.2",
                                                            invite_email=u"ricky@home.net")

            assert_that(invitation.is_accepted(), is_(True))
            assert_that(IUserProfile(receiver).email_verified, is_(True))

