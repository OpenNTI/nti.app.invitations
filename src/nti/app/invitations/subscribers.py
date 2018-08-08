#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zc.intid.interfaces import IBeforeIdRemovedEvent

from nti.app.invitations import SITE_INVITATION_SESSION_KEY

from nti.app.invitations.interfaces import InvitationRequiredError

from nti.app.invitations.utils import accept_site_invitation

from nti.appserver.interfaces import IUserCreatedWithRequestEvent

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile

from nti.invitations.interfaces import InvitationValidationError
from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.utils import get_sent_invitations

logger = __import__('logging').getLogger(__name__)


@component.adapter(IUser, IBeforeIdRemovedEvent)
def _user_removed(user, unused_event):
    invitations = set()
    # check unaccepted invitations sent via username
    invitations.update(get_sent_invitations(user.username))
    # check unaccepted invitations sent via user's email
    profile = IUserProfile(user, None)
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
    invitation = request.session.get(SITE_INVITATION_SESSION_KEY)
    if invitation is not None:
        result = accept_site_invitation(user, invitation)
        if not result:
            logger.exception(u'Failed to accept invitation for %s' % invitation.receiver)
            raise InvitationValidationError


@component.adapter(IUser, IUserCreatedWithRequestEvent)
def _require_invite_for_user_creation(user, event):
    request = event.request
    invitation = request.session.get(SITE_INVITATION_SESSION_KEY)
    if invitation is None:
        raise InvitationRequiredError
