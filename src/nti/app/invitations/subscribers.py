#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import datetime

import isodate

from six.moves import urllib_parse

from zc.intid.interfaces import IBeforeIdRemovedEvent

from zope import component

from zope.component.hooks import getSite

from zope.i18n import translate

from nti.app.invitations import SITE_INVITATION_SESSION_KEY
from nti.app.invitations import INVITATIONS

from nti.app.invitations import MessageFactory as _

from nti.app.invitations.interfaces import InvitationRequiredError
from nti.app.invitations.interfaces import ISiteInvitation

from nti.app.invitations.utils import accept_site_invitation
from nti.app.invitations.utils import pending_site_invitation_for_email

from nti.appserver.interfaces import IUserCreatedWithRequestEvent

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.dataserver.authentication import get_current_request

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.dataserver.users.users import User

from nti.invitations.interfaces import InvitationCodeError
from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import InvitationValidationError
from nti.invitations.interfaces import IInvitationSentEvent

from nti.invitations.utils import get_sent_invitations

from nti.mailer.interfaces import ITemplatedMailer

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


# TODO these 3 functions are copied directly from nti.app.products.courseware.invitations.subscribers
def get_ds2(request):
    try:
        result = request.path_info_peek() if request else None
    except AttributeError:  # in unit test we may see this
        result = None
    return result or "dataserver2"


def get_policy_package():
    policy = component.getUtility(ISitePolicyUserEventListener)
    return getattr(policy, 'PACKAGE', None)


def get_template_and_package(site, base_template, default_package=None):
    #package = get_policy_package()
    #if not package:
    return base_template, default_package

    # package = dottedname.resolve(package)
    # # Safe ascii path
    # provider_unique_id = site.ProviderUniqueID.replace(' ', '').lower()
    # provider_unique_id = make_specific_safe(provider_unique_id)
    # full_provider_id = provider_unique_id.replace('-', '')
    # template = full_provider_id + "_" + base_template
    #
    # path = os.path.join(os.path.dirname(package.__file__), 'templates')
    # if not os.path.exists(os.path.join(path, template + ".pt")):
    #     # Full path doesn't exist; Drop our specific id part and try that
    #     provider_unique_prefix = provider_unique_id.split('-')[0]
    #     provider_unique_prefix = provider_unique_prefix.split('/')[0]
    #     template = provider_unique_prefix + "_" + base_template
    #     if not os.path.exists(os.path.join(path, template + ".pt")):
    #         template = base_template
    # if template == base_template:
    #     package = default_package
    # return template, package


def send_invitation_email(invitation,
                          sender,
                          receiver_name,
                          receiver_email,
                          message,
                          request=None):
    if not request or not receiver_email:
        logger.warn("Not sending an invitation email because of no email or request")
        return False

    site = getSite()
    template = 'site_invitation_email'
    template, package = get_template_and_package(site, template)

    policy = component.getUtility(ISitePolicyUserEventListener)
    support_email = getattr(policy, 'SUPPORT_EMAIL', 'support@nextthought.com')
    brand = getattr(policy, 'BRAND', 'NextThought')
    brand_tag = 'Presented by NextThought'
    if brand.lower() != 'nextthought':
        brand_tag = 'Presented by %s and NextThought' % brand

    names = IFriendlyNamed(sender)
    informal_username = names.alias or names.realname or sender.username

    params = {'code': invitation.code}
    query = urllib_parse.urlencode(params)
    url = '/%s/%s?%s' % (get_ds2(request),
                         INVITATIONS,
                         query)
    redemption_link = urllib_parse.urljoin(request.application_url, url)
    receiver_name = receiver_name
    args = {
        'sender_name': informal_username,
        'receiver_name': receiver_name,
        'support_email': support_email,
        'site_name': site.__name__,
        'invitation_code': invitation.code,
        'invitation_message': message,
        'redemption_link': redemption_link,
        'brand': brand,
        'brand_tag': brand_tag,
        'today': isodate.date_isoformat(datetime.datetime.now())
    }

    try:
        mailer = component.getUtility(ITemplatedMailer)
        mailer.queue_simple_html_text_email(
            template,
            subject=translate(_(u"You're invited to ${title}",
                                mapping={'title': site.__name__})),
            recipients=[receiver_email],
            template_args=args,
            request=request,
            package=package,
            text_template_extension='.mak')
    except Exception:
        logger.exception("Cannot send site invitation email to %s",
                         receiver_email)
        return False
    return True


@component.adapter(ISiteInvitation, IInvitationSentEvent)
def _on_site_invitation_sent(invitation, event):
    request = getattr(event, 'request', None) or get_current_request()
    sender = User.get_user(invitation.sender)
    send_invitation_email(invitation,
                          sender=sender,
                          receiver_name=invitation.receiver_name,
                          receiver_email=invitation.receiver_email,
                          message=invitation.message,
                          request=request)


@component.adapter(IUser, IUserCreatedWithRequestEvent)
def require_invite_for_user_creation(unused_user, event):
    request = event.request
    invitation = request.session.get(SITE_INVITATION_SESSION_KEY)
    if invitation is None:
        raise InvitationRequiredError
