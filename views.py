#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views relating to working with invitations.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import time
import urllib

from zope import component
from zope import interface

from zope.container.contained import Contained

from zope.event import notify

from zope.intid.interfaces import IIntIds

from zope.traversing.interfaces import IPathAdapter

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.externalization.error import handle_validation_error
from nti.app.externalization.error import handle_possible_validation_error

from nti.app.invitations import MessageFactory as _

from nti.app.invitations import INVITATIONS
from nti.app.invitations import REL_SEND_INVITATION
from nti.app.invitations import REL_ACCEPT_INVITATION
from nti.app.invitations import REL_ACCEPT_INVITATIONS
from nti.app.invitations import REL_DECLINE_INVITATION
from nti.app.invitations import REL_PENDING_INVITATIONS
from nti.app.invitations import REL_TRIVIAL_DEFAULT_INVITATION_CODE

from nti.common.maps import CaseInsensitiveDict

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserverFolder
from nti.dataserver.interfaces import IDynamicSharingTargetFriendsList

from nti.dataserver.invitations import JoinEntityInvitation

from nti.dataserver.users import User
from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.integer_strings import to_external_string
from nti.externalization.integer_strings import from_external_string

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.invitations.interfaces import IInvitation
from nti.invitations.interfaces import InvitationSentEvent
from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import InvitationValidationError

from nti.invitations.utils import accept_invitation
from nti.invitations.utils import get_pending_invitations

from nti.property.property import Lazy

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

@interface.implementer(IPathAdapter)
@component.adapter(IDataserverFolder, IRequest)
class InvitationsPathAdapter(Contained):

	def __init__(self, dataserver, request):
		self.__parent__ = dataserver
		self.__name__ = INVITATIONS

	@Lazy
	def invitations(self):
		return component.getUtility(IInvitationsContainer)

	def __getitem__(self, invitation_id):
		if not invitation_id:
			raise hexc.HTTPNotFound()
		invitation_id = urllib.unquote(invitation_id)
		result = self.invitations.get(invitation_id)
		if result is not None:
			return result
		raise KeyError(invitation_id)

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IDynamicSharingTargetFriendsList,
			 permission=nauth.ACT_UPDATE,  # The creator only, not members who have read access
			 request_method='GET',
			 name=REL_TRIVIAL_DEFAULT_INVITATION_CODE)
class GetDefaultTrivialInvitationCode(AbstractAuthenticatedView):

	def __call__(self):
		intids = component.getUtility(IIntIds)
		iid = intids.getId(self.context)
		code = to_external_string(iid)
		return LocatedExternalDict({'invitation_code': code})

class AcceptInvitationMixin(AbstractAuthenticatedView):

	def handle_validation_error(self, request, e):
		handle_validation_error(request, e)

	def handle_possible_validation_error(self, request, e):
		handle_possible_validation_error(request, e)

	@Lazy
	def invitations(self):
		return component.getUtility(IInvitationsContainer)

	def _validate_invitation(self, invitation):
		request = self.request
		if invitation.is_accepted():
			raise_json_error(
					request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _("Invitation already accepted."),
						u'code': 'InvitationIsNotForUser',
					},
					None)

		profile = IUserProfile(self.context, None)
		email = getattr(profile, 'email', None) or u''
		receiver = invitation.receiver.lower()
		if receiver not in (self.context.username.lower(), email.lower()):
			raise_json_error(
					request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _("Invitation is not for this user."),
						u'code': 'InvitationIsNotForUser',
					},
					None)
		return invitation

	def _do_validation(self, invite_code):
		request = self.request
		if not invite_code:
			raise_json_error(
					request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _("Missing invitation code."),
						u'code': 'MissingInvitationCode',
					},
					None)

		if not invite_code in self.invitations:
			raise_json_error(
					request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _("Invalid invitation code."),
						u'code': 'InvalidInvitationCode',
						u'field': 'code',
						u'value': invite_code
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
						   		 ModeledContentUploadRequestUtilsMixin):

	def get_invite_code(self):
		values = CaseInsensitiveDict(self.readInput())
		result = 	values.get('code') \
				or	values.get('invitation') \
				or 	values.get('invitation_code') \
				or 	values.get('invitation_codes')  # legacy (should only be one)
		if isinstance(result, (list,tuple)) and result:
			result = result[0]
		return result

	def get_legacy_dfl(self, code):
		try:
			iid = from_external_string(code)
			result = component.getUtility(IIntIds).queryObject(iid)
			return result if IDynamicSharingTargetFriendsList.providedBy(result) else None
		except (TypeError, ValueError):  # pragma no cover
			return None

	def handle_legacy_dfl(self, code):
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

	def accept_invitation(self, user, invitation):
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
			e.field = 'invitation'
			self.handle_validation_error(request, e)
		except Exception as e:  # pragma: no cover
			self.handle_possible_validation_error(request, e)
		return invitation

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IInvitation,
			 permission=nauth.ACT_UPDATE,
			 request_method='POST',
			 name='accept')
class AcceptInvitationView(AcceptInvitationMixin):

	def _do_call(self):
		request = self.request
		invitation = self._validate_invitation(self.context)
		try:
			accept_invitation(self.context, invitation)
		except InvitationValidationError as e:
			e.field = 'invitation'
			self.handle_validation_error(request, e)
		except Exception as e:  # pragma: no cover
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
			 permission=nauth.ACT_UPDATE,  # The creator only, not members who have read access
			 request_method='POST',
			 name=REL_SEND_INVITATION)
class SendDFLInvitationView(AbstractAuthenticatedView,
							ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		result = ModeledContentUploadRequestUtilsMixin.readInput(self, value=value)
		result = CaseInsensitiveDict(result)
		return result

	def get_usernames(self, values):
		result = 	values.get('usernames') \
				or	values.get('username') \
				or 	values.get('users') \
				or 	values.get('user')
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
			raise_json_error(
					request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _("Must specify a username."),
						u'code': 'MissingUsername',
					},
					None)
		result = []
		for username in set(usernames):
			user = User.get_user(username)
			if 		IUser.providedBy(user) \
				and user not in self.context \
				and username != self.remoteUser.username:
				result.append(user.username)

		if not result:
			raise_json_error(
					request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _("No valid users to send invitation to."),
						u'code': 'NoValidInvitationUsers',
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
