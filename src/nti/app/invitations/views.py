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

from six.moves import urllib_parse

from requests.structures import CaseInsensitiveDict

from z3c.schema.email import isValidMailAddress

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import IContained

from zope.event import notify

from zope.intid.interfaces import IIntIds

from zope.traversing.interfaces import IPathAdapter

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractView
from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.base.abstract_views import get_source

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.externalization.error import handle_validation_error
from nti.app.externalization.error import handle_possible_validation_error

from nti.app.invitations import MessageFactory as _
from nti.app.invitations import GENERIC_SITE_INVITATION_MIMETYPE
from nti.app.invitations import REL_ACCEPT_SITE_INVITATION
from nti.app.invitations import REL_GENERIC_SITE_INVITATION
from nti.app.invitations import REL_SEND_SITE_INVITATION
from nti.app.invitations import SITE_ADMIN_INVITATION_MIMETYPE
from nti.app.invitations import SITE_INVITATION_MIMETYPE
from nti.app.invitations import SITE_INVITATION_SESSION_KEY
from nti.app.invitations import REL_SEND_SITE_ADMIN_INVITATION
from nti.app.invitations import INVITATIONS
from nti.app.invitations import REL_SEND_INVITATION
from nti.app.invitations import REL_ACCEPT_INVITATION
from nti.app.invitations import REL_ACCEPT_INVITATIONS
from nti.app.invitations import REL_DECLINE_INVITATION
from nti.app.invitations import REL_PENDING_INVITATIONS
from nti.app.invitations import REL_PENDING_SITE_ADMIN_INVITATIONS
from nti.app.invitations import REL_PENDING_SITE_INVITATIONS
from nti.app.invitations import REL_TRIVIAL_DEFAULT_INVITATION_CODE

from nti.app.invitations.interfaces import IChallengeLogonProvider
from nti.app.invitations.interfaces import ISiteInvitation

from nti.app.invitations.invitations import GenericSiteInvitation
from nti.app.invitations.invitations import JoinEntityInvitation
from nti.app.invitations.invitations import SiteAdminInvitation
from nti.app.invitations.invitations import SiteInvitation

from nti.app.invitations.utils import pending_site_invitations_for_email

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserverFolder
from nti.dataserver.interfaces import IDynamicSharingTargetFriendsList

from nti.dataserver.users.interfaces import IUserProfile

from nti.dataserver.users.users import User

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
from nti.invitations.utils import get_pending_invitations

from nti.site.site import getSite

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
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
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Invitation already accepted."),
                                 'code': 'InvitationIsNotForUser',
                             },
                             None)
        if IDisabledInvitation.providedBy(invitation):
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
        if not invite_code \
                or invite_code not in self.invitations:
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
                    and username != self.remoteUser.username:
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


@view_config(route_name='objects.generic.traversal',
               renderer='rest',
               context=InvitationsPathAdapter,
               request_method='POST',
               permission=nauth.ACT_READ,  # Do the permission check in the view
               name=REL_SEND_SITE_INVITATION)
class SendSiteInvitationCodeView(AbstractAuthenticatedView,
                                 ModeledContentUploadRequestUtilsMixin):

    _invitation_type = SiteInvitation

    def __init__(self, request):
        super(SendSiteInvitationCodeView, self).__init__(request)
        self.warnings = list()
        self.invalid_emails = list()

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def check_permissions(self):
        if not is_admin_or_site_admin(self.remoteUser):
            logger.info(u'User %s failed permissions check for sending site invitation.' % (self.remoteUser,))
            raise hexc.HTTPForbidden()

    # TODO: This closely resembles
    # TODO: nti.app.products.courseware.views.course_invitation_views.CheckCourseInvitationsCSVView.parse_csv_users
    def parse_csv(self):
        result = []
        source = get_source(self.request, 'csv', 'input', 'source')
        if source is not None:
            # Read in and split (to handle universal newlines).
            # XXX: Generalize this?
            source = source.read()
            for idx, row in enumerate(csv.reader(source.splitlines())):
                if not row or row[0].startswith("#"):
                    continue
                email = row[0]
                email = email.strip() if email else email
                realname = row[1] if len(row) > 1 else ''
                if not email:
                    msg = u"Missing email in line %s." % (idx + 1)
                    self.warnings.append(msg)
                    continue
                if not realname:
                    msg = u"Missing name in line %s." % (idx + 1)
                    self.warnings.append(msg)
                if not isValidMailAddress(email):
                    self.invalid_emails.append(email)
                    continue
                result.append({'email': email, 'realname': realname})
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
            email = invitation.get('email')
            realname = invitation.get('realname')
            # These cases shouldn't happen
            if email is None and realname is None:
                msg = u'Missing email and name for input'
                self.warnings.append(msg)
                continue
            elif email is None:
                msg = u'Missing email for %s.' % realname
                self.warnings.append(msg)
                continue
            elif realname is None:
                msg = u'Missing name for %s.' % email
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
        except:
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

    def create_invitation(self, email, realname, message):
        invitation = self._invitation_type()
        invitation.receiver_email = email
        invitation.sender = self.remoteUser.username
        invitation.receiver_name = realname
        invitation.message = message
        self.invitations.add(invitation)
        return invitation

    def __call__(self):
        self.check_permissions()
        values = self.get_site_invitations()
        # At this point we should have a values dict containing invitation destinations and message
        if self.warnings or self.invalid_emails:
            logger.info(u'Site Invitation input contains missing or invalid values.')
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

        result = LocatedExternalDict()
        result[ITEMS] = items = []
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context

        message = values.get('message')

        # pylint: disable=no-member
        for user_dict in values['invitations']:
            email = user_dict['email']
            realname = user_dict['realname']
            pending_invitation = pending_site_invitations_for_email(email)
            # Check if this user already has an invite to this site
            # we don't want to have multiple invites for the same user floating around
            # so just send them another email
            if pending_invitation is not None:
                invitation = pending_invitation
            else:
                invitation = self.create_invitation(email, realname, message)
            items.append(invitation)
            notify(InvitationSentEvent(invitation, email))

        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ISiteInvitation,
             request_method='GET',
             name=REL_ACCEPT_SITE_INVITATION)
class AcceptSiteInvitationView(AcceptInvitationMixin):

    def _do_call(self, code=None):
        code = self.context.code if not code else code
        url_provider = component.queryUtility(IChallengeLogonProvider)
        if url_provider is None:
            logger.warn(u'No challenge logon provider for site %s' % getSite())
            return hexc.HTTPNotFound()
        self.request.session[SITE_INVITATION_SESSION_KEY] = code
        logon_url = url_provider.logon_url(self.request)
        return hexc.HTTPFound(logon_url)

    def __call__(self):
        return self._do_call()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             request_method='GET',
             name=REL_ACCEPT_SITE_INVITATION)
class AcceptSiteInvitationByCodeView(AcceptSiteInvitationView):

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def get_invite_code(self):
        values = CaseInsensitiveDict(self.request.params)
        result = values.get('code') \
                 or values.get('invitation') \
                 or values.get('invitation_code') \
                 or values.get('invitation_codes')  # legacy (should only be one)
        if isinstance(result, (list, tuple)) and result:  # pragma: no cover
            result = result[0]
        return result

    def __call__(self):
        code = self.get_invite_code()
        return self._do_call(code=code)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             permission=nauth.ACT_READ,
             request_method='GET',
             name=REL_PENDING_SITE_INVITATIONS)
class GetPendingSiteInvitationsView(AbstractAuthenticatedView):

    _invitation_mime_type = SITE_INVITATION_MIMETYPE

    def _do_call(self):
        result = LocatedExternalDict()
        site = self.request.params.get('site') or getSite().__name__
        items = get_pending_invitations(mimeTypes=self._invitation_mime_type,
                                        sites=site)
        result[ITEMS] = items
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        return result

    def __call__(self):
        if not is_admin_or_site_admin(self.remoteUser):
            logger.exception(u'User %s failed permissions check for pending site invitations.' % (self.remoteUser,))
            raise hexc.HTTPForbidden()
        return self._do_call()


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
            logger.info(u'User %s failed permissions check for creating a generic site invitation.' % (self.remoteUser,))
            raise hexc.HTTPForbidden()
        input = self.readInput()
        code = input.get('code')
        if code is None:
            logger.info(u'Generic invitation code was not provided.')
            raise hexc.HTTPExpectationFailed(_(u'You must include a code to be set as the generic'))

        # Arbitrary
        if len(code) > 25:
            logger.info(u'The provided invitation code %s was longer than 25 characters.' % (code,))
            raise hexc.HTTPExpectationFailed(_(u'Your code may not be longer than 25 characters'))

        generics = get_pending_invitations(mimeTypes=GENERIC_SITE_INVITATION_MIMETYPE,
                                           sites=getSite().__name__)
        if len(generics) > 0:
            # There should only ever be only of these
            if len(generics) != 1:
                logger.warn(u'There is more than one generic site invitation for this site.')
            for generic in generics:
                self.invitations.remove(generic)

        invitation = GenericSiteInvitation()
        invitation.sender = self.remoteUser.username
        invitation.code = code
        try:
            self.invitations.add(invitation)
        except DuplicateInvitationCodeError:
            logger.info(u'Generic code %s matched an existing invitation code.' % (code,))
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
            logger.warn(u'There is more than one generic site invitation.')

        for generic in items:
            self.invitations.remove(generic)

        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             permission=nauth.ACT_READ,
             request_method='POST',
             name=REL_SEND_SITE_ADMIN_INVITATION)
class SendSiteAdminInvitationView(SendSiteInvitationCodeView):

    _invitation_type = SiteAdminInvitation


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=InvitationsPathAdapter,
             permission=nauth.ACT_READ,
             request_method='GET',
             name=REL_PENDING_SITE_ADMIN_INVITATIONS)
class GetPendingSiteAdminInvitationsView(GetPendingSiteInvitationsView):

    _invitation_mime_type = SITE_ADMIN_INVITATION_MIMETYPE
