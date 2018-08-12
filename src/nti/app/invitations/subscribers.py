#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zc.intid.interfaces import IBeforeIdRemovedEvent

from zope import component

from nti.app.invitations import SITE_INVITATION_SESSION_KEY

from nti.app.invitations.interfaces import InvitationRequiredError

from nti.app.invitations.utils import accept_site_invitation
from nti.app.invitations.utils import pending_site_invitation_for_email

from nti.appserver.interfaces import IUserCreatedWithRequestEvent

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile

from nti.invitations.interfaces import InvitationCodeError
from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import InvitationValidationError

from nti.invitations.utils import get_sent_invitations

logger = __import__('logging').getLogger(__name__)


@component.adapter(IUser, IBeforeIdRemovedEvent)
def _user_removed(user, unused_event):
    invitations = set()
    # check unaccepted invitations sent via username
    invitations.update(get_sent_invitations(user.username))
    # check unaccepted invitations sent via user's email
    profile = IUserProfile(user)
    email = getattr(profile, 'email', None)
    if email:
        invitations.update(get_sent_invitations(email))
    # remove unaccepted invitations
    container = component.getUtility(IInvitationsContainer)
    for invitation in invitations:
        container.remove(invitation)


@component.adapter(IUser, IUserCreatedWithRequestEvent)
def _validate_site_invitation(user, event):
    request = event.request
    invitation_code = request.session.get(SITE_INVITATION_SESSION_KEY)
    invitations = component.queryUtility(IInvitationsContainer)
    if invitation_code is not None:
        # Make sure the container exists
        assert invitations is not None

        # We only have the code in the session, not the object
        invitation = invitations.get_invitation_by_code(invitation_code)
        if invitation is None:
            # There is a possibility that the invitation tied to this code
            # has been rescended and the user now has a new invitation
            # so we will check if there is one for this email
            profile = IUserProfile(user, None)
            email = getattr(profile, 'email', None)
            invitation = pending_site_invitation_for_email(email)
        if invitation is None:
            logger.info(u'Unable to find an invitation for user %s' % user)
            raise InvitationCodeError
        result = accept_site_invitation(user, invitation)
        if not result:
            logger.exception(u'Failed to accept invitation for %s' % invitation.receiver)
            raise InvitationValidationError


@component.adapter(IUser, IUserCreatedWithRequestEvent)
def require_invite_for_user_creation(unused_user, event):
    request = event.request
    invitation = request.session.get(SITE_INVITATION_SESSION_KEY)
    if invitation is None:
        raise InvitationRequiredError
