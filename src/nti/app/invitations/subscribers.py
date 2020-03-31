#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from z3c.schema.email import isValidMailAddress

from zc.intid.interfaces import IBeforeIdRemovedEvent

from zope import component
from zope import interface

from zope.i18n import translate

from zope.lifecycleevent.interfaces import IObjectAddedEvent

from nti.app.invitations import MessageFactory as _

from nti.app.invitations import SITE_INVITATION_SESSION_KEY
from nti.app.invitations import SITE_INVITATION_EMAIL_SESSION_KEY

from nti.app.invitations.interfaces import ISiteInvitation
from nti.app.invitations.interfaces import InvitationRequiredError

from nti.app.invitations.utils import get_invitation_url
from nti.app.invitations.utils import accept_site_invitation_by_code

from nti.app.pushnotifications.digest_email import _TemplateArgs

from nti.appserver.interfaces import IUserLogonEvent
from nti.appserver.interfaces import IApplicationSettings

from nti.appserver.logon import create_failure_response

from nti.appserver.brand.utils import get_site_brand_name

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.common.url import safe_add_query_params

from nti.dataserver.authentication import get_current_request

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IFriendlyNamed
from nti.dataserver.users.interfaces import IWillCreateNewEntityEvent

from nti.dataserver.users.users import User

from nti.invitations.interfaces import IInvitationSentEvent
from nti.invitations.interfaces import IInvitationsContainer
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


def _validate_site_invitation(user):
    request = get_current_request()
    if not request:
        return
    invitation_code = request.session.get(SITE_INVITATION_SESSION_KEY)
    link_email = request.session.get(SITE_INVITATION_EMAIL_SESSION_KEY)
    if invitation_code is not None:
        del request.session[SITE_INVITATION_SESSION_KEY]
        if SITE_INVITATION_EMAIL_SESSION_KEY in request.session:
            del request.session[SITE_INVITATION_EMAIL_SESSION_KEY]
        try:
            accept_site_invitation_by_code(user, invitation_code, link_email)
        except InvitationValidationError as e:
            logger.info(u'Failed to accept invitation for user %s with error %s' % (user, str(e)))
            # Try to get the failure url from the request params
            url = request.params.get('failure', None)
            # If it wasn't there try to search for it in the request session
            if not url:
                for key in request.session:
                    if 'failure' in key:
                        url = request.session.get(key)
                        break
            # If we still don't have a url just redirect them to the login app
            if not url:
                url = request.application_url
                url += '/login/'
            # Add the error message to the query params
            url = safe_add_query_params(url, {'message': str(e)})
            # abort the transaction so the user isn't created
            request.environ['nti.commit_veto'] = 'abort'
            response = create_failure_response(request,
                                               url,
                                               error=str(e),
                                               error_factory=hexc.HTTPUnprocessableEntity)
            raise response


@component.adapter(IUser, IObjectAddedEvent)
def _new_user_validate_site_invitation(user, unused_event):
    # Must accept invite early to influence behavior down the line. These users
    # will most likely also hit the login event below, but the second call into
    # _validate_site_invitation should be fast, safe, and idempotent.
    _validate_site_invitation(user)


@component.adapter(IUser, IUserLogonEvent)
def _user_login_validate_site_invitation(user, unused_event):
    _validate_site_invitation(user)


def _get_app_setting(setting_name, default):
    settings = component.getUtility(IApplicationSettings)
    return settings.get(setting_name, default)


def _get_invitations_bcc():
    invitations_bcc = _get_app_setting("invitations_bcc", None) or ()

    if invitations_bcc:
        invitations_bcc = [email.strip() for email in invitations_bcc.split(",")]
        invitations_bcc = [email for email in invitations_bcc
                           if isValidMailAddress(email.strip())]
        invitations_bcc = tuple(invitations_bcc)

    logger.info("Using bcc of %s for sending invitation" % (invitations_bcc,))

    return tuple(invitations_bcc)


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

    # Some sites want a custom macros in the invitation
    # If there is a macro registered then we will render it to
    # We have to do this here because we cannot do try/except within the template
    custom_image = component.queryMultiAdapter((interface.Interface, interface.Interface, interface.Interface),
                                               name='site_invitation_image')
    tagline = component.queryMultiAdapter((interface.Interface, interface.Interface, interface.Interface),
                                          name='site_invitation_tagline')
    brand_message = component.queryMultiAdapter((interface.Interface, interface.Interface, interface.Interface),
                                                name='site_invitation_brand_message')

    support_email = getattr(policy, 'SUPPORT_EMAIL', 'support@nextthought.com')
    brand = get_site_brand_name()
    package = getattr(policy, 'PACKAGE', None)

    names = IFriendlyNamed(sender)
    informal_username = names.alias or names.realname or sender.username

    redemption_link = get_invitation_url(request.application_url, invitation)

    receiver_name = receiver_name
    msg_args = {
        'receiver_name': receiver_name,
        'support_email': support_email,
        'redemption_link': redemption_link,
        'brand': brand,
        'custom_image_macro': custom_image,
        'tagline': tagline,
        'brand_message': brand_message,
        'sender_content': None
    }

    if invitation.message:
        # Tal is not very cooperative for dynamic building up this style
        # so we create and stash it here
        avatar_styles = "float:left;height:40px;width:40px;border-radius:50%%;background-image: url('%s'), url('https://s3.amazonaws.com/content.nextthought.com/images/generic/imageassets/unresolved-user-avatar.png'); background-position: center center;background-size:cover;background-repeat:no-repeat;" % template_args.creator_avatar_url
        msg_args['sender_content'] = {
            'sender': informal_username,
            'message': message,
            'avatar_styles': avatar_styles
        }

    try:
        mailer = component.getUtility(ITemplatedMailer)
        mailer.queue_simple_html_text_email(
            template,
            subject=translate(_(u"You're invited to ${title}",
                                mapping={'title': brand})),
            recipients=[receiver_email],
            bcc=_get_invitations_bcc(),
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
                          receiver_name=invitation.receiver_name or invitation.receiver,
                          receiver_email=invitation.receiver,
                          message=invitation.message,
                          request=request)


@component.adapter(IUser, IWillCreateNewEntityEvent)
def require_invite_for_user_creation(unused_user, event):
    # Must be called before _validate_site_invitation, since that removes
    # the session key
    request = getattr(event, 'request', None) or get_current_request()
    if request is not None:
        invitation = request.session.get(SITE_INVITATION_SESSION_KEY)
        if invitation is None:
            raise InvitationRequiredError()
