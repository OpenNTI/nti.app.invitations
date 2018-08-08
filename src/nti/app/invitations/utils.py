#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from nti.app.invitations import SITE_INVITATION_MIMETYPE

from nti.invitations.interfaces import IDisabledInvitation
from nti.invitations.interfaces import InvitationActorError
from nti.invitations.interfaces import InvitationAlreadyAcceptedError
from nti.invitations.interfaces import InvitationDisabledError
from nti.invitations.interfaces import InvitationExpiredError

from nti.invitations.utils import get_invitation_actor
from nti.invitations.utils import get_pending_invitations

from nti.site.site import getSite

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


def pending_site_invitations_for_email(user):
    email = getattr(user, 'email', user)
    current_site = getSite().__name__
    pending_invitations = get_pending_invitations(receivers=email,
                                                  mimeTypes=SITE_INVITATION_MIMETYPE)
    for pending in pending_invitations:
        if pending.target_site == current_site:
            return pending


def accept_site_invitation(user, invitation):
    if invitation.is_expired():
        raise InvitationExpiredError(invitation)
    if invitation.is_accepted():
        raise InvitationAlreadyAcceptedError(invitation)
    if IDisabledInvitation.providedBy(invitation):
        raise InvitationDisabledError(invitation)
    actor = get_invitation_actor(invitation, user)
    if actor is None:
        raise InvitationActorError(invitation)
    return actor.accept(user, invitation)
