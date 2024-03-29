#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views relating to working with invitations.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import csv
import six
import time
import calendar
import isodate

import unicodecsv as ucsv

from datetime import datetime

from io import BytesIO

from itsdangerous import BadSignature

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from pyramid.view import view_config
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

from six.moves import urllib_parse

from z3c.schema.email import isValidMailAddress

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from zope.lifecycleevent import ObjectModifiedEvent

from zope.location.interfaces import IContained

from zope.event import notify

from zope.intid.interfaces import IIntIds

from zope.traversing.interfaces import IPathAdapter

from nti.app.authentication import get_remote_user

from nti.app.base.abstract_views import AbstractView
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.base.abstract_views import get_source

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.externalization.error import handle_validation_error
from nti.app.externalization.error import handle_possible_validation_error

from nti.app.invitations import MessageFactory as _

from nti.app.invitations import INVITATIONS
from nti.app.invitations import REL_SEND_INVITATION
from nti.app.invitations import REL_ACCEPT_INVITATION
from nti.app.invitations import REL_ACCEPT_INVITATIONS
from nti.app.invitations import REL_CREATE_SITE_INVITATION
from nti.app.invitations import REL_DECLINE_INVITATION
from nti.app.invitations import REL_PENDING_INVITATIONS
from nti.app.invitations import REL_SEND_SITE_INVITATION
from nti.app.invitations import SITE_INVITATION_MIMETYPE
from nti.app.invitations import REL_ACCEPT_SITE_INVITATION
from nti.app.invitations import REL_DELETE_SITE_INVITATIONS
from nti.app.invitations import REL_GENERIC_SITE_INVITATION
from nti.app.invitations import SITE_INVITATION_SESSION_KEY
from nti.app.invitations import REL_PENDING_SITE_INVITATIONS
from nti.app.invitations import SITE_ADMIN_INVITATION_MIMETYPE
from nti.app.invitations import GENERIC_SITE_INVITATION_MIMETYPE
from nti.app.invitations import REL_TRIVIAL_DEFAULT_INVITATION_CODE
from nti.app.invitations import SITE_INVITATION_EMAIL_SESSION_KEY
from nti.app.invitations import SIGNED_CONTENT_VERSION_1_0

from nti.app.invitations.interfaces import ISiteInvitation
from nti.app.invitations.interfaces import ISiteAdminInvitation
from nti.app.invitations.interfaces import IChallengeLogonProvider
from nti.app.invitations.interfaces import IInvitationSigner
from nti.app.invitations.interfaces import IInvitationInfo

from nti.app.invitations.invitations import JoinEntityInvitation
from nti.app.invitations.invitations import GenericSiteInvitation

from nti.app.invitations.traversal import InvitationInfoPathAdapter

from nti.app.invitations.utils import accept_site_invitation_by_code
from nti.app.invitations.utils import get_site_invitation_for_email

from nti.appserver.interfaces import IApplicationSettings

from nti.common._compat import text_

from nti.common.url import safe_add_query_params

from nti.coremetadata.interfaces import IUsernameSubstitutionPolicy

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_site_admin
from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserverFolder
from nti.dataserver.interfaces import IDynamicSharingTargetFriendsList

from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.dataserver.users.users import User

from nti.dataserver.users.utils import get_users_by_email_in_sites

from nti.externalization.externalization import to_external_object

from nti.externalization.integer_strings import to_external_string
from nti.externalization.integer_strings import from_external_string

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.invitations.interfaces import IInvitation
from nti.invitations.interfaces import IDisabledInvitation
from nti.invitations.interfaces import InvitationSentEvent
from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import InvitationValidationError
from nti.invitations.interfaces import DuplicateInvitationCodeError

from nti.invitations.utils import accept_invitation
from nti.invitations.utils import get_all_invitations
from nti.invitations.utils import get_pending_invitations
from nti.invitations.utils import get_expired_invitations
from nti.invitations.utils import get_accepted_invitations
from nti.invitations.utils import get_random_invitation_code

from nti.links import Link

from nti.mailer.interfaces import IEmailAddressable

ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPathAdapter, IContained)
@component.adapter(IDataserverFolder, IRequest)
class InvitationsPathAdapter(object):
    __name__ = INVITATIONS

    def __init__(self, dataserver, unused_request):
        self.__parent__ = dataserver

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def __getitem__(self, key):
        # pylint: disable=no-member,too-many-function-args
        key = urllib_parse.unquote(key)
        result = self.invitations.get(key)
        if result is not None:
            return result
        raise KeyError(key) if key else hexc.HTTPNotFound()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IDynamicSharingTargetFriendsList,
             permission=nauth.ACT_UPDATE,
             request_method='GET',
             name=REL_TRIVIAL_DEFAULT_INVITATION_CODE)
class GetDefaultTrivialInvitationCode(AbstractAuthenticatedView):

    def __call__(self):
        intids = component.getUtility(IIntIds)
        iid = intids.getId(self.context)
        code = to_external_string(iid)
        return LocatedExternalDict({'invitation_code': code})


class AcceptInvitationMixin(AbstractView):

    def handle_validation_error(self, request, e):
        handle_validation_error(request, e)

    def handle_possible_validation_error(self, request, e):
        handle_possible_validation_error(request, e)

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def _validate_invitation(self, invitation, check_user=True):
        request = self.request
        if invitation.is_accepted():
            logger.info("Invitation is already accepted")
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Invitation already accepted."),
                                 'code': 'InvitationIsNotForUser',
                             },
                             None)
        if IDisabledInvitation.providedBy(invitation):
            logger.info("Invitation is disabled")
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Invitation code no longer valid."),
                                 'code': 'InvalidInvitationCode',
                             },
                             None)
        if check_user:
            profile = IUserProfile(self.context, None)
            email = getattr(profile, 'email', None) or u''
            receiver = invitation.receiver.lower()
            # pylint: disable=no-member
            if receiver not in (self.context.username.lower(), email.lower()):
                logger.info("Invitation email is invalid (%s) (%s)",
                            receiver, email)
                raise_json_error(request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"Invitation is not for this user."),
                                     'code': 'InvitationIsNotForUser',
                                 },
                                 None)
        return invitation

    def _do_validation(self, invite_code):
        request = self.request
        if not invite_code or invite_code not in self.invitations:
            logger.info("Invitation code is not found (%s)",
                        invite_code)
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Invalid invitation code."),
                                 'code': 'InvalidInvitationCode',
                                 'field': 'code',
                                 'value': invite_code
                             },
                             None)
        invitation = self.invitations[invite_code]
        return self._validate_invitation(invitation)

    def __call__(self):
        self._do_call()
        return hexc.HTTPNoContent()


@view_config(name=REL_ACCEPT_INVITATION)
@view_config(name=REL_ACCEPT_INVITATIONS)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=IUser,
               request_method='POST',
               permission=nauth.ACT_UPDATE)
class AcceptInvitationByCodeView(AcceptInvitationMixin,
                                 AbstractAuthenticatedView,
                                 ModeledContentUploadRequestUtilsMixin):

    def get_invite_code(self):
        values = CaseInsensitiveDict(self.readInput())
        result = values.get('code') \
                 or values.get('invitation') \
                 or values.get('invitation_code') \
                 or values.get('invitation_codes')  # legacy (should only be one)
        if isinstance(result, (list, tuple)) and result:  # pragma: no cover
            result = result[0]
        return result

    def get_legacy_dfl(self, code):
        result = None
        try:
            iid = from_external_string(code)
            obj = component.getUtility(IIntIds).queryObject(iid)
            if IDynamicSharingTargetFriendsList.providedBy(obj):
                result = obj
        except (TypeError, ValueError):  # pragma no cover
            pass
        return result

    def handle_legacy_dfl(self, code):
        # pylint: disable=no-member
        dfl = self.get_legacy_dfl(code)
        if dfl is not None:
            creator = dfl.creator
            invitation = JoinEntityInvitation()
            invitation.sent = time.time()
            invitation.entity = dfl.NTIID
            invitation.receiver = self.remoteUser.username
            invitation.sender = getattr(creator, 'username', creator)
            self.invitations.add(invitation)
            return invitation
        return None

    def accept_invitation(self, unused_user, invitation):
        return accept_invitation(self.context, invitation)

    def _do_call(self):
        request = self.request
        code = self.get_invite_code()
        invitation = self.handle_legacy_dfl(code)
        if invitation is None:
            invitation = self._do_validation(code)
        try:
            self.accept_invitation(self.context, invitation)
        except InvitationValidationError as e:
            e.field = u'invitation'
            self.handle_validation_error(request, e)
        except Exception as e:  # pragma: no cover pylint: disable=broad-except
            self.handle_possible_validation_error(request, e)
        return invitation


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IInvitation,
             permission=nauth.ACT_UPDATE,
             request_method='POST',
             name='accept')
class AcceptInvitationView(AcceptInvitationMixin,
                           AbstractAuthenticatedView):

    def _do_call(self):
        request = self.request
        invitation = self._validate_invitation(self.context)
        try:
            accept_invitation(self.context, invitation)
        except InvitationValidationError as e:
            e.field = u'invitation'
            self.handle_validation_error(request, e)
        except Exception as e:  # pragma: no cover pylint: disable=broad-except
            self.handle_possible_validation_error(request, e)
        return invitation


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IUser,
             permission=nauth.ACT_UPDATE,
             request_method='POST',
             name=REL_DECLINE_INVITATION)
class DeclineInvitationByCodeView(AcceptInvitationByCodeView):

    def _do_call(self):
        code = self.get_invite_code()
        invitation = self._do_validation(code)
        # pylint: disable=no-member
        self.invitations.remove(invitation)
        return invitation


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IInvitation,
             permission=nauth.ACT_UPDATE,
             request_method='POST',
             name='decline')
class DeclineInvitationView(AcceptInvitationView):

    def _do_call(self):
        invitation = self._validate_invitation(self.context)
        # pylint: disable=no-member
        self.invitations.remove(invitation)
        return invitation


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IUser,
             permission=nauth.ACT_READ,
             request_method='GET',
             name=REL_PENDING_INVITATIONS)
class GetPendingInvitationsView(AbstractAuthenticatedView):

    def _do_call(self):
        result = LocatedExternalDict()
        email = getattr(IUserProfile(self.context, None), 'email', None)
        # pylint: disable=no-member
        receivers = (self.context.username, email)
        items = result[ITEMS] = get_pending_invitations(receivers)
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        return result

    def __call__(self):
        return self._do_call()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IDynamicSharingTargetFriendsList,
             permission=nauth.ACT_UPDATE,
             # The creator only, not members who have read access
             request_method='POST',
             name=REL_SEND_INVITATION)
class SendDFLInvitationView(AbstractAuthenticatedView,
                            ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        result = None
        if self.request.body:
            result = super(SendDFLInvitationView, self).readInput(value)
            result = CaseInsensitiveDict(result)
        return result or {}

    def get_usernames(self, values):
        result = values.get('usernames') \
                 or values.get('username') \
                 or values.get('users') \
                 or values.get('user')
        if isinstance(result, six.string_types):
            result = result.split(',')
        return result

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def _do_validation(self, values):
        request = self.request
        usernames = self.get_usernames(values)
        if not usernames:
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Must specify a username."),
                                 'code': 'MissingUsername',
                             },
                             None)
        result = []
        for username in set(usernames):
            user = User.get_user(username)
            # pylint: disable=no-member,unsupported-membership-test
            if IUser.providedBy(user) \
                    and user not in self.context \
                    and user is not self.remoteUser:
                result.append(user.username)

        if not result:
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"No valid users to send invitation to."),
                                 'code': 'NoValidInvitationUsers',
                             },
                             None)
        return result

    def _do_call(self):
        values = self.readInput()
        users = self._do_validation(values)
        message = values.get('message')

        result = LocatedExternalDict()
        result[ITEMS] = items = []
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context

        # pylint: disable=no-member
        entity = self.context.username
        for username in users:
            invitation = JoinEntityInvitation()
            invitation.entity = entity
            invitation.message = message
            invitation.receiver = username
            invitation.sender = self.remoteUser.username
            self.invitations.add(invitation)
            items.append(invitation)
            notify(InvitationSentEvent(invitation, username))

        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result

    def __call__(self):
        return self._do_call()



def _delete_invitation(invitation, container=None):
    """
    Logic for deleting an invitation; we soft delete by setting an
    `expiryTime`. If already expired, we fully delete. If accepted
    already, we log and ignore.
    """
    if invitation.is_accepted():
        logger.info("Will not delete accepted invitation (%s)", invitation.code)
    elif invitation.is_expired():
        if container is None:
            container = component.getUtility(IInvitationsContainer)
        container.remove(invitation)
        logger.info("Deleting invitation (%s)", invitation.code)
    else:
        now = datetime.utcnow()
        ts = calendar.timegm(now.timetuple())
        # Our index normalizes to the minute, so stagger this back
        # a bit to avoid confusing result sets when querying.
        invitation.expiryTime = ts - 60
        notify(ObjectModifiedEvent(invitation))
        logger.info("Soft deleting invitation (%s)", invitation.code)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             request_method='POST',
             permission=nauth.ACT_READ,
             name=REL_DELETE_SITE_INVITATIONS)
class DeleteSiteInvitationsView(AbstractAuthenticatedView,
                                ModeledContentUploadRequestUtilsMixin):

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def __call__(self):
        if not is_admin_or_site_admin(self.remoteUser):
            return hexc.HTTPForbidden()

        values = self.readInput()
        emails = values.get('emails')
        codes = values.get('codes')
        if emails:
            invitations = get_pending_invitations(receivers=emails,
                                                  mimeTypes=(SITE_ADMIN_INVITATION_MIMETYPE,
                                                             SITE_INVITATION_MIMETYPE))
        elif codes:
            invitations = [self.invitations.get_invitation_by_code(x) for x in codes]
        for invitation in invitations:
            if invitation is not None:
                _delete_invitation(invitation, self.invitations)
        return invitations


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ISiteInvitation,
             request_method='DELETE',
             permission=nauth.ACT_READ)
class DeleteSiteInvitationView(AbstractAuthenticatedView):
    """
    Delete a specific site invitation. If no expiration date, we "soft" delete
    this by setting an expiration date of now. If already expired, we fully 
    delete the invitation.
    """

    def __call__(self):
        # Better permissioning? Is this container below a site?
        if not is_admin_or_site_admin(self.remoteUser):
            return hexc.HTTPForbidden()
        _delete_invitation(self.context)
        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             request_method='POST',
             permission=nauth.ACT_READ,  # Do the permission check in the view
             name=REL_SEND_SITE_INVITATION)
class SendSiteInvitationCodeView(AbstractAuthenticatedView,
                                 ModeledContentUploadRequestUtilsMixin):
    def __init__(self, request):
        super(SendSiteInvitationCodeView, self).__init__(request)
        self.warnings = list()
        self.invalid_emails = list()

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def check_permissions(self):
        if not is_admin_or_site_admin(self.remoteUser):
            logger.info('User %s failed permissions check for sending site invitation.',
                        self.remoteUser)
            raise hexc.HTTPForbidden()

    def _decode_cell(self, string, encoding='utf-8-sig'):
        return text_(string, encoding)

    # TODO: This closely resembles
    # TODO: nti.app.products.courseware.views.course_invitation_views.CheckCourseInvitationsCSVView.parse_csv_users
    def parse_csv(self):
        result = []
        source = get_source(self.request, 'csv', 'input', 'source')
        if source is not None:
            # Read in and split (to handle universal newlines).
            # XXX: Generalize this?
            for unused_idx, row in enumerate(csv.reader(source)):
                if not row or row[0].startswith("#"):
                    continue
                email = row[0]
                email = self._decode_cell(email)
                email = email.strip() if email else email
                realname = self._decode_cell(row[1]) if len(row) > 1 else u''
                if not email:
                    # Ignore empty email lines
                    continue
                if not isValidMailAddress(email):
                    self.invalid_emails.append(email)
                    continue
                result.append({'receiver': email, 'receiver_name': realname})
        return result

    def readInput(self, value=None):
        result = None
        if self.request.body:
            result = super(SendSiteInvitationCodeView, self).readInput(value)
            result = CaseInsensitiveDict(result)
        return result or {}

    def _validate_json_invitations(self, values):
        # Parse through the submitted emails and names to make sure all values are
        # provided and emails are valid. Because these values are coming from the
        # view, we would expect that warnings and invalid emails are rare here
        for invitation in values:
            email = invitation.get('receiver')
            realname = invitation.get('receiver_name')
            # These cases shouldn't happen
            if email is None and realname is None:
                msg = u'Missing email and name for input'
                self.warnings.append(msg)
                continue
            elif email is None:
                msg = u'Missing email for %s.' % realname
                self.warnings.append(msg)
                continue

            if not isValidMailAddress(email):
                self.invalid_emails.append(email)
                continue

    def get_site_invitations(self):
        values = self.readInput()
        json_invitations = values.get('invitations', [])
        self._validate_json_invitations(json_invitations)
        try:
            csv_invitations = self.parse_csv()
        except Exception:  # pylint: disable=broad-except
            logger.exception('Failed to parse CSV file')
            raise_json_error(
                self.request,
                hexc.HTTPUnprocessableEntity,
                {
                    'message': _(u'Could not parse csv file.'),
                    'code': 'InvalidCSVFileCodeError',
                },
                None)
        # Join csv and json invitations
        invitations = json_invitations + csv_invitations
        values['invitations'] = invitations
        return values

    def preflight_input(self, force=False):
        values = self.get_site_invitations()
        # At this point we should have a values dict containing invitation destinations and message
        if self.warnings or self.invalid_emails:
            logger.info('Site Invitation input contains missing or invalid values.')
            raise_json_error(
                self.request,
                hexc.HTTPExpectationFailed,
                {
                    'message': _(u'The provided input is missing values or contains invalid email addresses.'),
                    'code': 'InvalidSiteInvitationData',
                    'Warnings': self.warnings,
                    'InvalidEmails': self.invalid_emails
                },
                None
            )

        # We ignore users already accepted unless *only* (1) specific
        # user was invited. 
        challenge = []
        new_invitations = []
        invites = values['invitations']
        for invitation in invites:
            if get_users_by_email_in_sites(invitation['receiver']):
                challenge.append(invitation)
            else:
                new_invitations.append(invitation)
        # XXX Is there ever a valid reason to send an invite to an
        # email owned by an existing user?
        if challenge and len(invites) == 1:
            # XXX: Ideally we separate out this direct invite
            # case from the bulk, alas.
            if force:
                new_invitations = challenge
            else:
                self._handle_challenge(challenge,
                                       code=u'ExistingAccountEmail',
                                       message=_(
                                           u'%s %s will be sent to an email address'
                                           u' already associated with an account.' %
                                           (len(challenge), self.request.localizer.pluralize(u'invitation',
                                                                                             u'invitations',
                                                                                             len(challenge)))
                                       ))
        values['invitations'] = new_invitations
        return values

    def _handle_challenge(self, challenge_invitations, code, message):
        challenge = dict()
        challenge[ITEMS] = to_external_object(challenge_invitations)
        challenge[ITEM_COUNT] = challenge[TOTAL] = len(challenge_invitations)
        challenge['message'] = message
        challenge['code'] = code
        links = (
            Link(self.request.path,
                 rel='confirm',
                 params={'force': True},
                 method='POST'),
        )
        challenge[LINKS] = to_external_object(links)
        raise_json_error(self.request,
                         hexc.HTTPConflict,
                         challenge,
                         None)

    def _notify(self, invitation, email):
        notify(InvitationSentEvent(invitation, email))

    def __call__(self):
        self.check_permissions()
        force = self.request.params.get('force')
        values = self.preflight_input(force=force)
        # Default to a regular site invitation
        mimetype = values.get('mime_type') or values.get('mimeType')
        message = values.get('message')
        result = LocatedExternalDict()
        items = []
        challenge_invitations = []
        # pylint: disable=no-member
        for ext_values in values['invitations']:
            email = ext_values['receiver']
            # Check if this user already has an invite to this site
            # We are only *accepted* here if this is a direct invite that was already 
            # confirmed (e.g. forced).
            user_invitation = get_site_invitation_for_email(email)
            if user_invitation is not None:
                if      mimetype \
                    and not force \
                    and user_invitation.mime_type != mimetype:
                    # Only challenge invitations that change the user role without the force param
                    challenge_invitations.append(user_invitation)
                    continue

                # Issue a new invite with mimetype or existing mimetype
                # This is where we can update the invitation type
                ext_values[MIMETYPE] = mimetype or user_invitation.mime_type
                # Prefer given message if we have one
                ext_values['message'] = message or user_invitation.message
                if     user_invitation.is_expired() \
                    or user_invitation.is_accepted():
                    ext_values['code'] = get_random_invitation_code()
                else:
                    # Pending, re-use code
                    ext_values['code'] = user_invitation.code
                if not user_invitation.is_accepted():
                    self.invitations.remove(user_invitation)
            else:
                # New invites
                if MIMETYPE not in ext_values:
                    ext_values[MIMETYPE] = mimetype or SITE_INVITATION_MIMETYPE
                if 'message' not in ext_values:
                    ext_values['message'] = message
                ext_values['code'] = get_random_invitation_code()
            
            # XXX: we may have receiver with no message and mimetype - that's ok?
            # We default mimetype and we'll have no message.                        
            ext_values['target_site'] = getSite().__name__
            invitation = self.readCreateUpdateContentObject(self.remoteUser, externalValue=ext_values)
            items.append(invitation)
            self.invitations.add(invitation)
            self._notify(invitation, email)

        if len(challenge_invitations) > 0:
            self._handle_challenge(challenge_invitations,
                                   code=u'UpdatePendingInvitations',
                                   message=_(
                                       u'%s pending %s will be updated to a different role.' %
                                       (len(challenge_invitations),
                                        self.request.localizer.pluralize(u'invitation',
                                                                         u'invitations',
                                                                         len(challenge_invitations)))
                                   ))

        result[ITEMS] = items
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             request_method='POST',
             permission=nauth.ACT_READ,  # Do the permission check in the view
             name=REL_CREATE_SITE_INVITATION)
class CreateSiteInvitationCodeView(SendSiteInvitationCodeView):

    def _notify(self, invitation, email):
        # Don't send e-mail
        pass


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationInfoPathAdapter,
             request_method='GET')
class FetchInvitationInfo(AbstractView):

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def __call__(self, *args, **kwargs):
        # Invitation code is stored in session during the call to
        # accept the invitation, prior to the redirect to the app base.
        code = self.request.session.get(SITE_INVITATION_SESSION_KEY)

        if not code:
            logger.error(u'No code provided for fetching invitation info')
            return hexc.HTTPNotFound()

        # Retrieve the invitation, as only the code is in session
        invitation = self.invitations.get_invitation_by_code(code)

        if invitation is None:
            logger.error(u'Unable to find an invitation for code %s', code)
            return hexc.HTTPNotFound()

        if invitation.is_accepted():
            logger.error(u'Invitation for code %s has already been accepted', code)
            return hexc.HTTPNotFound()

        inv_info = IInvitationInfo(invitation)

        if inv_info is None:
            logger.error(u'Failed adapting invitation with code %s', code)
            return hexc.HTTPNotFound()

        inv_info.__name__ = 'InvitationInfo'
        inv_info.__parent__ = invitation

        return inv_info


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ISiteInvitation,
             request_method='GET',
             name=REL_ACCEPT_SITE_INVITATION)
class AcceptSiteInvitationView(AcceptInvitationMixin):

    def _login_url(self):
        return self.request.application_url + '/login/'

    def _failure_url(self):
        values = CaseInsensitiveDict(self.request.params)
        url = values.get('failure')
        return self.request.application_url + url if url else None

    def _logon_provider_url(self):
        url_provider = component.queryUtility(IChallengeLogonProvider)
        if url_provider is None:
            logger.warning('No challenge logon provider for site %s',
                           getSite())
            raise hexc.HTTPNotFound()
        return url_provider.logon_url(self.request)

    def _app_url(self):
        settings = component.getUtility(IApplicationSettings)
        web_root = settings.get('web_app_root', '/NextThoughtWebApp/')
        return self.request.application_url + web_root

    def _success_url(self):
        values = CaseInsensitiveDict(self.request.params)
        url = values.get('success')
        return (self.request.application_url + url) if url else None

    def _failure_response(self, url, message):
        return hexc.HTTPSeeOther(self._add_failure_params(url, message))

    def _add_failure_params(self, url, message):
        return safe_add_query_params(url,
                                     params={'failed': 'true',
                                             'error': message,
                                             'message': message})

    def _do_call(self, code=None, link_email=None):
        # pylint: disable=no-member
        code = self.context.code if not code else code

        # If an authenticated user has tried to accept the invitation,
        # we want to handle their invitation here and skip sending
        # them through the account creation flow
        # This allows for invitations to update the permissions
        # of an existing user
        if get_remote_user():
            remote_user = get_remote_user()
            logger.info(u'Attempting to accept invitation for authenticated user %s' % remote_user)
            try:
                accept_site_invitation_by_code(remote_user, code, link_email)
                return hexc.HTTPFound(self._success_url() or self._app_url())
            except InvitationValidationError as e:
                logger.exception(u'Failed to accept invitation for authenticated user %s' % remote_user)
                return self._failure_response(self._failure_url() or self._login_url(), str(e))

        not_valid_msg = u"Invitation code '%s' is no longer valid." % code
        invitation = self.invitations.get(code)
        if invitation is None:
            logger.error(u'No invitation for code %s' % code)
            return self._failure_response(self._failure_url() or self._login_url(), not_valid_msg)

        if invitation.is_accepted():
            logger.error(u"Invitation for code %s already accepted." % code)
            return self._failure_response(self._failure_url() or self._login_url(), not_valid_msg)

        if invitation.is_expired():
            logger.error(u"Invitation for code %s expired (expiry=%s)." % (code, invitation.expiryTime))
            return self._failure_response(self._failure_url() or self._login_url(), not_valid_msg)

        self.request.session[SITE_INVITATION_SESSION_KEY] = code
        self.request.session[SITE_INVITATION_EMAIL_SESSION_KEY] = link_email
        return hexc.HTTPFound(self._success_url() or self._logon_provider_url())

    def __call__(self):
        return self._do_call()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             request_method='GET',
             name=REL_ACCEPT_SITE_INVITATION)
class AcceptSiteInvitationByCodeView(AcceptSiteInvitationView):
    """
    An invitation view in which we must be supplied a code for
    the invitation in play.
    """

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def _get_signed_content(self):
        values = CaseInsensitiveDict(self.request.params)
        encoded_content = values.get('scode')

        if encoded_content:
            signer = component.getUtility(IInvitationSigner)

            try:
                result = signer.decode(encoded_content)
            except BadSignature:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"Invalid invitation code."),
                                     'code': 'InvalidInvitationCode'
                                 },
                                 None)

            if result:
                if result['version'] != SIGNED_CONTENT_VERSION_1_0:
                    logger.error("Invalid signed content version (%s) for 'scode' param.",
                                 result['version'])

                    raise_json_error(self.request,
                                     hexc.HTTPUnprocessableEntity,
                                     {
                                         'message': _(u"Content version for 'scode' param invalid."),
                                         'code': 'InvalidInvitationContentVersion'
                                     },
                                     None)

                return result['code'], result['email']

        return None, None

    def get_invite_code(self):
        values = CaseInsensitiveDict(self.request.params)
        result =    values.get('code') \
                 or values.get('invitation') \
                 or values.get('invitation_code') \
                 or values.get('invitation_codes')  # legacy (should only be one)
        if isinstance(result, (list, tuple)) and result:  # pragma: no cover
            result = result[0]
        return result

    def __call__(self):
        code, email = self._get_signed_content()

        if not code:
            email = None
            code = self.get_invite_code()

        if not code:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Must have an invitation code."),
                                 'code': 'MissingInvitationCodeError',
                             },
                             None)
        return self._do_call(code=code, link_email=email)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             accept='application/json',
             request_method='GET')
class GetSiteInvitationsView(AbstractAuthenticatedView,
                             BatchingUtilsMixin):
    
    _default_mimetypes = (SITE_INVITATION_MIMETYPE,
                          SITE_ADMIN_INVITATION_MIMETYPE)

    def _do_sort_receiver(self, items, reverse):
        return sorted(items, key=lambda item: item.receiver, reverse=reverse)

    def _do_sort_created_time(self, items, reverse):
        return sorted(items, key=lambda item: item.createdTime, reverse=reverse)
    
    @Lazy
    def _params(self):
        return CaseInsensitiveDict(self.request.params)
    
    @Lazy
    def site(self):
        result = self._params.get('site') or getSite().__name__
        return result

    @Lazy
    def exclude(self):
        exclude = self._params.get('exclude', '')
        exclude = exclude.strip().split(',')
        return exclude
    
    @Lazy
    def mime_types(self):
        mimetypes = [mimetype for mimetype in self._default_mimetypes 
                     if mimetype not in self.exclude]
        return mimetypes

    @Lazy
    def filter_value(self):
        return self._params.get('filter')
    
    @Lazy
    def type_filter(self):
        result = self._params.get('type_filter')
        if result:
            result = result.lower()
            if result not in ('pending', 'accepted', 'expired'):
                raise hexc.HTTPUnprocessableEntity(u'Invalid type_filter param')
        return result
    
    def get_invitations(self):
        """
        Return all invitations, filtered by type (pending, accepted, expired)
        or all.
        """
        if self.type_filter:
            type_filter = self.type_filter
            if type_filter == 'pending':
                result = get_pending_invitations(mimeTypes=self.mime_types,
                                                 sites=self.site)
            elif type_filter == 'accepted':
                result = get_accepted_invitations(mimeTypes=self.mime_types,
                                                  sites=self.site)
            else:
                result = get_expired_invitations(mimeTypes=self.mime_types,
                                                 sites=self.site)
            
        else:
            result = get_all_invitations(mimeTypes=self.mime_types,
                                         sites=self.site)
        return result
    
    def _filter_invitations(self, invitations):
        if self.filter_value:
            val = self.filter_value.lower()
            def _include(invite):
                rec_user = User.get_user(invite.receiver)
                fn = IFriendlyNamed(rec_user, '')
                realname = getattr(fn, 'realname', '')
                alias = getattr(fn, 'alias', '')
                # username, target email, user real name
                return (invite.receiver and val in invite.receiver.lower()) \
                    or (invite.original_receiver and val in invite.original_receiver.lower()) \
                    or (alias and val in alias.lower()) \
                    or (realname and val in realname.lower())
            invitations = [x for x in invitations if _include(x)]
        return invitations
    
    
    def filter_and_sort_invitations(self, items):
        items = self._filter_invitations(items)
        sort_name = self._params.get('sortOn', 'created_time')
        sort_reverse = self._params.get('sortOrder', 'ascending') == 'descending'
        if sort_name:
            try:
                sort_method = getattr(self, '_do_sort_' + sort_name)
                items = sort_method(items, sort_reverse)
            except AttributeError:
                pass
        return items

    def _do_call(self):
        result = LocatedExternalDict()
        items = self.get_invitations()
        filtered_items = self.filter_and_sort_invitations(items)
        result[ITEMS] = filtered_items

        result[TOTAL] = len(items)
        result[ITEM_COUNT] = len(filtered_items)
        result["FilteredTotalItemCount"] = len(filtered_items)
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        batch_size, batch_start = self._get_batch_size_start()
        if batch_size is not None and batch_start is not None:
            self._batch_items_iterable(result, result[ITEMS],
                                       batch_size=batch_size,
                                       batch_start=batch_start)
        return result

    def __call__(self):
        if not is_admin_or_site_admin(self.remoteUser):
            logger.exception(
                'User %s failed permissions check for site invitations.',
                self.remoteUser
            )
            raise hexc.HTTPForbidden()
        if self._params.get('site') and is_site_admin(self.remoteUser):
            # Site admins cannot filter by site name
            raise hexc.HTTPForbidden()
        return self._do_call()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             request_method='GET',
             name=REL_PENDING_SITE_INVITATIONS)
class GetPendingSiteInvitationsView(GetSiteInvitationsView):

    def get_invitations(self):
        return get_pending_invitations(mimeTypes=self.mime_types,
                                       sites=self.site)


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             context=InvitationsPathAdapter,
             accept='text/csv',
             permission=nauth.ACT_READ)
class SiteInvitationsCSVView(GetSiteInvitationsView):
    """
    Get site invitations in CSV format.
    """

    def _replace_username(self, username):
        substituter = component.queryUtility(IUsernameSubstitutionPolicy)
        if substituter is None:
            return username
        result = substituter.replace(username) or username
        return result

    def _get_email(self, user):
        addr = IEmailAddressable(user, None)
        return getattr(addr, 'email', '')

    def _format_time(self, t):
        try:
            return isodate.datetime_isoformat(datetime.fromtimestamp(t)) if t else u''
        except ValueError:
            logger.debug("Cannot parse time '%s'", t)
            return str(t)

    def _build_inv_info(self, invitation):
        sender_username = invitation.sender
        sender_user = User.get_user(sender_username)
        sender_email = sender_alias = sender_realname = u''
        if sender_user: 
            sender_username = self._replace_username(sender_username)
            sender_email = self._get_email(sender_user)
            sender_named = IFriendlyNamed(sender_user)
            sender_alias = sender_named.alias
            sender_realname = sender_named.realname
            
        # May be username of (accepted) invite or the email the invitation was 
        # sent to. 
        rec_username = invitation.receiver
        rec_user = User.get_user(rec_username)
        invitation_email = invitation.original_receiver or rec_username
        rec_alias = rec_realname = rec_username = rec_email = u''
        if rec_user: 
            rec_username = self._replace_username(rec_user.username)
            rec_email = self._get_email(rec_user)
            rec_named = IFriendlyNamed(rec_user)
            rec_alias = rec_named.alias
            rec_realname = rec_named.realname
            
        sent_time = self._format_time(invitation.sent)
        expiry_time = self._format_time(invitation.expiryTime)
        accepted_time = self._format_time(invitation.acceptedTime)
        
        result = {
            'sender username': sender_username,
            'sender email': sender_email,
            'sender alias': sender_alias,
            'sender realname': sender_realname,
            'invitation email': invitation_email,
            'target username': rec_username,
            'target email': rec_email,
            'target alias': rec_alias,
            'target realname': rec_realname,
            'sent time': sent_time,
            'accepted time': accepted_time,
            'expiration time': expiry_time,
            'site admin invitation': ISiteAdminInvitation.providedBy(invitation)
        }
        return result

    def _do_call(self):
        invitations = self.get_invitations()
        invitations = self.filter_and_sort_invitations(invitations)
        
        stream = BytesIO()
        fieldnames = ['sender username', 'sender email', 'sender alias', 'invitation email',
                      'target username', 'target email', 'target alias',
                      'sent time', 'accepted time', 'expiration time', 
                      'site admin invitation']

        csv_writer = ucsv.DictWriter(stream, fieldnames=fieldnames,
                                     extrasaction='ignore',
                                     encoding='utf-8')
        csv_writer.writeheader()
        for invitation in invitations:
            inv_info = self._build_inv_info(invitation)
            csv_writer.writerow(inv_info)

        response = self.request.response
        response.body = stream.getvalue()
        response.content_encoding = 'identity'
        response.content_type = 'text/csv; charset=UTF-8'
        response.content_disposition = 'attachment; filename="invitations_export.csv"'
        return response


@view_config(route_name='objects.generic.traversal',
             request_method='POST',
             context=InvitationsPathAdapter,
             renderer='rest',
             permission=nauth.ACT_READ,
             request_param='format=text/csv')
class SiteInvitationsCSVPOSTView(SiteInvitationsCSVView, 
                                 ModeledContentUploadRequestUtilsMixin):
    
    def readInput(self):
        if self.request.POST:
            result = {'codes': self.request.params.getall('codes') or []}
        elif self.request.body:
            result = super(SiteInvitationsCSVPOSTView, self).readInput()
        else:
            result = self.request.params
        return CaseInsensitiveDict(result)
    
    @Lazy
    def _params(self):
        return self.readInput()

    def get_invitations(self):
        codes = self._params.get('codes', ())
        included_invites = super(SiteInvitationsCSVPOSTView, self).get_invitations()
        if not codes:
            return included_invites 
        included_invites = set(included_invites)
        result = []
        invitations = component.getUtility(IInvitationsContainer)
        
        for code in codes:
            invitation = invitations.get_invitation_by_code(code)
            if invitation is None or invitation not in included_invites:
                continue
            result.append(invitation) 
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             permission=nauth.ACT_READ,
             request_method=('POST', 'PUT'),
             name=REL_GENERIC_SITE_INVITATION)
class SetGenericSiteInvitationCode(AbstractAuthenticatedView,
                                   ModeledContentUploadRequestUtilsMixin):
    # This can be disabled by using the DeclineInvitationView

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def __call__(self):
        if not is_admin_or_site_admin(self.remoteUser):
            logger.info(
                'User %s failed permissions check for creating a generic site invitation.',
                self.remoteUser
            )
            raise hexc.HTTPForbidden()
        data = self.readInput()
        code = data.get('code')
        if code is None:
            logger.info('Generic invitation code was not provided.')
            raise hexc.HTTPExpectationFailed(_(u'You must include a code to be set as the generic'))

        # Arbitrary
        if len(code) > 25:
            logger.info(
                'The provided invitation code %s was longer than 25 characters.', code
            )
            raise hexc.HTTPExpectationFailed(_(u'Your code may not be longer than 25 characters'))

        generics = get_pending_invitations(mimeTypes=GENERIC_SITE_INVITATION_MIMETYPE,
                                           sites=getSite().__name__)
        if len(generics) > 0:
            # There should only ever be only of these
            if len(generics) != 1:
                logger.warning(
                    'There is more than one generic site invitation for this site.'
                )
            for generic in generics:
                # pylint: disable=no-member
                self.invitations.remove(generic)
        # pylint: disable=no-member
        invitation = GenericSiteInvitation()
        invitation.sender = self.remoteUser.username
        invitation.code = code
        try:
            self.invitations.add(invitation)
        except DuplicateInvitationCodeError:
            logger.info('Generic code %s matched an existing invitation code.',
                        code)
            return hexc.HTTPConflict(_(u'The code you entered is not available.'))
        return invitation


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             permission=nauth.ACT_READ,
             request_method='GET',
             name=REL_GENERIC_SITE_INVITATION)
class GetGenericSiteInvitationCode(GetPendingSiteInvitationsView):
    _invitation_mime_type = GENERIC_SITE_INVITATION_MIMETYPE


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             permission=nauth.ACT_READ,
             request_method='DELETE',
             name=REL_GENERIC_SITE_INVITATION)
class DeleteGenericSiteInvitationCode(AbstractAuthenticatedView):

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def __call__(self):
        items = get_pending_invitations(mimeTypes=GENERIC_SITE_INVITATION_MIMETYPE,
                                        sites=getSite().__name__)

        if len(items) > 1:
            logger.warning('There is more than one generic site invitation.')

        for generic in items:
            # pylint: disable=no-member
            self.invitations.remove(generic)

        return hexc.HTTPNoContent()
