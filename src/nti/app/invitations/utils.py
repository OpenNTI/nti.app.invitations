#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from itsdangerous import URLSafeSerializer
from nti.common.cypher import get_plaintext
from nti.dataserver.users.utils import force_email_verification
from nti.dataserver.users.utils import reindex_email_verification

from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.component.hooks import getSite


from nti.app.invitations import SITE_INVITATION_MIMETYPE
from nti.app.invitations import SITE_ADMIN_INVITATION_MIMETYPE
from nti.app.invitations import INVITATIONS
from nti.app.invitations import REL_ACCEPT_SITE_INVITATION
from nti.app.invitations import SIGNED_CONTENT_VERSION_1_0

from nti.app.invitations.interfaces import IInvitationSigner

from nti.dataserver.users.interfaces import IUserProfile

from nti.invitations.interfaces import IDisabledInvitation
from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import InvitationCodeError
from nti.invitations.interfaces import InvitationValidationError
from nti.invitations.interfaces import InvitationActorError
from nti.invitations.interfaces import InvitationExpiredError
from nti.invitations.interfaces import InvitationDisabledError
from nti.invitations.interfaces import InvitationAlreadyAcceptedError

from nti.invitations.utils import get_invitation_actor
from nti.invitations.utils import get_pending_invitations

logger = __import__('logging').getLogger(__name__)


def pending_site_invitation_for_email(email):
    current_site = getattr(getSite(), '__name__', None)
    pending_invitations = get_pending_invitations(receivers=email,
                                                  mimeTypes=(SITE_INVITATION_MIMETYPE,
                                                             SITE_ADMIN_INVITATION_MIMETYPE))
    for pending_invite in pending_invitations:
        if pending_invite.target_site == current_site:
            return pending_invite


def get_site_invitation_actor(invitation, user, link_email):
    actor = get_invitation_actor(invitation, user)

    if actor:
        actor.link_email = link_email

    return actor


def accept_site_invitation(user, invitation, link_email):
    if invitation.is_expired():
        raise InvitationExpiredError(invitation)
    if invitation.is_accepted():
        raise InvitationAlreadyAcceptedError(invitation)
    if IDisabledInvitation.providedBy(invitation):
        raise InvitationDisabledError(invitation)
    actor = get_site_invitation_actor(invitation, user, link_email)
    if actor is None:
        raise InvitationActorError(invitation)
    return actor.accept(user, invitation)


def accept_site_invitation_by_code(user, code, link_email):
    invitations = component.getUtility(IInvitationsContainer)
    # We only have the code in the session, not the object
    invitation = invitations.get_invitation_by_code(code)
    result = True
    profile = IUserProfile(user, None)
    email = getattr(profile, 'email', None)
    if invitation is None:
        # There is a possibility that the invitation tied to this code
        # has been rescended and the user now has a new invitation
        # so we will check if there is one for this email
        invitation = pending_site_invitation_for_email(email)
    if invitation is None:
        logger.info(u'Unable to find an invitation for user %s' % user)
        raise InvitationCodeError(invitation)
    if invitation.is_accepted() and invitation.receiver == getattr(user, 'username', None):
        return result

    # Typical flows send invites via email or verify prior to creating the
    # invite (e.g. the ASCI flow).  See the second comment in NTI-8974 for
    # detail. Also, this needs to happen prior to accepting, since the
    # receiver field is updated on the invitation once accepted.
    from IPython.terminal.debugger import set_trace; set_trace()
    if email is not None and email.lower() == invitation.receiver.lower():
        profile.email_verified = True
        reindex_email_verification(user)

    result = accept_site_invitation(user, invitation, link_email)
    if not result:
        logger.exception(u'Failed to accept invitation for %s' % invitation.receiver)
        raise InvitationValidationError(invitation)
    return result


def get_invitation_url(application_url, invitation):
    signed_params = {
        'version': SIGNED_CONTENT_VERSION_1_0,
        'code': invitation.code,
        'email': invitation.original_receiver
    }
    signer = component.getUtility(IInvitationSigner)
    params = {'scode': signer.encode(signed_params)}
    query = urllib_parse.urlencode(params)

    url = '/%s/%s/%s?%s' % ("dataserver2",
                            INVITATIONS,
                            '@@' + REL_ACCEPT_SITE_INVITATION,
                            query)

    redemption_link = urllib_parse.urljoin(application_url, url)

    return redemption_link


@interface.implementer(IInvitationSigner)
class InvitationSigner(object):

    def __init__(self, secret, salt):
        self.serializer = URLSafeSerializer(get_plaintext(secret), salt=salt)

    def encode(self, content):
        return self.serializer.dumps(content)

    def decode(self, encoded_content):
        return self.serializer.loads(encoded_content)
