#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.app.invitations.utils import pending_site_invitations_for_user
from zope import component

from zc.intid.interfaces import IBeforeIdRemovedEvent

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile

from nti.invitations.interfaces import IInvitationsContainer, IMarkAsAcceptedInvitationEvent, InvitationAcceptedEvent

from nti.invitations.utils import get_sent_invitations
from zope.event import notify

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


@component.adapter(IMarkAsAcceptedInvitationEvent)
def _invitation_accepted(event):
    user = event.user
    invitation = pending_site_invitations_for_user(user)
    if invitation is not None:
        invitation.accepted = True
        invitation.receiver = getattr(user, 'username', user)  # update
        notify(InvitationAcceptedEvent(invitation, user))
