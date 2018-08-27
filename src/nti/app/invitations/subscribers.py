#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from six.moves import urllib_parse

from zc.intid.interfaces import IBeforeIdRemovedEvent

from zope import component
from zope import interface

from zope.i18n import translate

from nti.app.invitations import REL_ACCEPT_SITE_INVITATION
from nti.app.invitations import SITE_INVITATION_SESSION_KEY
from nti.app.invitations import INVITATIONS

from nti.app.invitations import MessageFactory as _

from nti.app.invitations.interfaces import InvitationRequiredError
from nti.app.invitations.interfaces import ISiteInvitation

from nti.app.invitations.utils import accept_site_invitation_by_code

from nti.app.pushnotifications.digest_email import _TemplateArgs

from nti.appserver.interfaces import IUserCreatedWithRequestEvent
from nti.appserver.interfaces import IUserLogonEvent

from nti.appserver.logon import create_failure_response

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.dataserver.authentication import get_current_request

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.dataserver.users.users import User

from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import IInvitationSentEvent
from nti.invitations.interfaces import InvitationValidationError

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


def _safe_add_query_params(url, params):
    """
    Adds query params properly to a url
    :param url: The url to be updated
    :param params: The query params
    :return: The url with the query params safely added
    """
    url_parts = list(urllib_parse.urlparse(url))
    # Query params are in index 4
    query_params = dict(urllib_parse.parse_qsl(url_parts[4]))
    query_params.update(params)
    url_parts[4] = urllib_parse.urlencode(query_params)
    return urllib_parse.urlunparse(url_parts)


@component.adapter(IUser, IUserLogonEvent)
def _validate_site_invitation(user, event):
    request = get_current_request()
    invitation_code = request.session.get(SITE_INVITATION_SESSION_KEY)
    del request.session[SITE_INVITATION_SESSION_KEY]
    if invitation_code is not None:
        try:
            accept_site_invitation_by_code(user, invitation_code)
        except InvitationValidationError as e:
            # Try to get the failure url from the request params
            url = request.params.get('failure', None)
            # If it wasn't there try to search for it in the request session
            if not url:
                for key in request.session:
                    if 'failure' in key:
                        url = request.session.get(key)
                        break
            # If we have a failure url add the message to the query params
            if url:
                url = _safe_add_query_params(url, {'message': str(e)})
            response = create_failure_response(request,
                                               url,
                                               error=str(e),
                                               error_factory=hexc.HTTPUnprocessableEntity)
            raise response


def get_ds2(request):
    try:
        result = request.path_info_peek() if request else None
    except AttributeError:  # in unit test we may see this
        result = None
    return result or "dataserver2"


def send_invitation_email(invitation,
                          sender,
                          receiver_name,
                          receiver_email,
                          message,
                          request=None):
    if not request or not receiver_email:
        logger.warn("Not sending an invitation email because of no email or request")
        return False

    template_args = _TemplateArgs(request=request,
                                  remoteUser=sender,
                                  objs=[invitation])

    template = 'site_invitation_email'

    policy = component.getUtility(ISitePolicyUserEventListener)

    # Some sites want a custom image in the invitation
    # If there is a macro registered then we will render it to
    # We have to do this here because we cannot do try/except within the template
    custom_image = component.queryMultiAdapter((interface.Interface, interface.Interface, interface.Interface),
                                               name='site_invitation_image')

    support_email = getattr(policy, 'SUPPORT_EMAIL', 'support@nextthought.com')
    brand = getattr(policy, 'BRAND', 'NextThought')
    brand_message = getattr(policy, 'SITE_INVITATION_MESSAGE', u'Get started learning on an interactive '
                                                               u'platform like no other by clicking the button '
                                                               u'below or copying and pasting the URL into your '
                                                               u'browser.')
    package = getattr(policy, 'PACKAGE', None)

    names = IFriendlyNamed(sender)
    informal_username = names.alias or names.realname or sender.username

    params = {'code': invitation.code}
    query = urllib_parse.urlencode(params)
    url = '/%s/%s/%s?%s' % (get_ds2(request),
                            INVITATIONS,
                            '@@' + REL_ACCEPT_SITE_INVITATION,
                            query)
    redemption_link = urllib_parse.urljoin(request.application_url, url)

    receiver_name = receiver_name
    msg_args = {
        'receiver_name': receiver_name,
        'support_email': support_email,
        'redemption_link': redemption_link,
        'brand': brand,
        'brand_message': brand_message,
        'custom_image_macro': custom_image,
        'sender_content': None
    }

    if invitation.message:
        msg_args['sender_content'] = {
            'sender': informal_username,
            'message': message,
            'creator_avatar_initials': template_args.creator_avatar_initials,
            'creator_avatar_bg_color': template_args.creator_avatar_bg_color
        }

    try:
        mailer = component.getUtility(ITemplatedMailer)
        mailer.queue_simple_html_text_email(
            template,
            subject=translate(_(u"You're invited to ${title}",
                                mapping={'title': brand})),
            recipients=[receiver_email],
            template_args=msg_args,
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
                          receiver_email=invitation.receiver,
                          message=invitation.message,
                          request=request)


@component.adapter(IUser, IUserCreatedWithRequestEvent)
def require_invite_for_user_creation(unused_user, event):
    request = getattr(event, 'request', None) or get_current_request()
    invitation = request.session.get(SITE_INVITATION_SESSION_KEY)
    if invitation is None:
        raise InvitationRequiredError()
