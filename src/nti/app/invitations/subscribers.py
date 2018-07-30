#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.event import notify

from zc.intid.interfaces import IBeforeIdRemovedEvent

from nti.app.invitations.invitations import JoinSiteInvitation

from nti.app.invitations.utils import pending_site_invitations_for_email

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile

from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import IMarkAsAcceptedInvitationEvent
from nti.invitations.interfaces import InvitationAcceptedEvent

from nti.invitations.utils import get_sent_invitations

from nti.site.site import getSite

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
def _site_invitation_accepted(event):
    # If we get passed an invitation then we can just update it and be done
    # otherwise try to fuzzy match the newly created user to an invite
    invitation = event.obj
    user = event.user
    user = IUserProfile(user, None)
    email = getattr(user, 'email', None)
    invitation = pending_site_invitations_for_email(email) if invitation is None else invitation
    if invitation is not None and not invitation.IsGeneric:
        invitation.accepted = True
        invitation.receiver = getattr(user, 'username', user)  # update
    # The user may have gotten here through a generic invitation or our fuzzy match didn't work
    # Let's go ahead and create an invitation for them so that it is documented they accepted an
    # invitation to this site
    else:
        invitation = JoinSiteInvitation(receiver=user,
                                        target_site=getSite(),
                                        sender=u'Generic',
                                        accepted=True)
    notify(InvitationAcceptedEvent(invitation, user))
