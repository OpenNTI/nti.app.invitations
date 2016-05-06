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

from zope import component

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization import internalization as obj_io

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.externalization.error import handle_validation_error
from nti.app.externalization.error import handle_possible_validation_error

from nti.app.invitations import REL_ACCEPT_INVITATION
from nti.app.invitations import REL_ACCEPT_INVITATIONS
from nti.app.invitations import REL_PENDING_INVITATIONS
from nti.app.invitations import REL_TRIVIAL_DEFAULT_INVITATION_CODE

from nti.common.maps import CaseInsensitiveDict

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDynamicSharingTargetFriendsList

from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.invitations.interfaces import IInvitations
from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import InvitationValidationError

from nti.invitations.utility import accept_invitations

from nti.invitations.utils import accept_invitation
from nti.invitations.utils import get_pending_invitations

ITEMS = StandardExternalFields.ITEMS

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IUser,
			 permission=nauth.ACT_UPDATE,
			 request_method='POST',
			 name=REL_ACCEPT_INVITATIONS)
class AcceptInvitationsView(AbstractAuthenticatedView):

	def get_invite_codes(self):
		json_body = obj_io.read_body_as_external_object(self.request)
		if 'invitation_codes' not in json_body:
			raise hexc.HTTPBadRequest()
		result = json_body['invitation_codes']
		if isinstance(result, six.string_types):
			result = result.split()
		return result

	def handle_validation_error(self, request, e):
		handle_validation_error(request, e)

	def handle_possible_validation_error(self, request, e):
		handle_possible_validation_error(request, e)
		
	def _do_call(self):
		request = self.request
		invite_codes = self.get_invite_codes()	
		try:
			if invite_codes:
				return accept_invitations(request.context, invite_codes)
		except InvitationValidationError as e:
			e.field = 'invitation_codes'
			self.handle_validation_error(request, e)
		except Exception as e:  # pragma: no cover
			self.handle_possible_validation_error(request, e)

	def __call__(self):
		"""
		Implementation of :const:`REL_ACCEPT_INVITATIONS`.
		"""
		self._do_call()
		return hexc.HTTPNoContent()

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IDynamicSharingTargetFriendsList,
			 permission=nauth.ACT_UPDATE, # The creator only, not members who have read access
			 request_method='GET',
			 name=REL_TRIVIAL_DEFAULT_INVITATION_CODE)
def get_default_trivial_invitation_code(request):
	invitations = component.getUtility(IInvitations)
	code = invitations._getDefaultInvitationCode(request.context)
	return LocatedExternalDict({'invitation_code': code})

# new views

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IUser,
			 permission=nauth.ACT_UPDATE,
			 request_method='POST',
			 name=REL_ACCEPT_INVITATION)
class AcceptInvitationView(AbstractAuthenticatedView,
						   ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		result = ModeledContentUploadRequestUtilsMixin.readInput(self, value=value)
		result = CaseInsensitiveDict(result)
		return result

	def get_invite_code(self):
		values = self.readInput()
		result = 	values.get('code') \
				or	values.get('invitation') \
				or 	values.get('invitation_code')
		return result
	
	def handle_validation_error(self, request, e):
		handle_validation_error(request, e)

	def handle_possible_validation_error(self, request, e):
		handle_possible_validation_error(request, e)
	
	def _do_validation(self):
		request = self.request
		invite_code = self.get_invite_codes()	
		if not invite_code:
			raise_json_error(
					request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _("Missing invitation code"),
						u'code': 'MissingInvitationCode',
					},
					None)
		invitations = component.getUtility(IInvitationsContainer)
		if not invite_code in invitations:
			raise_json_error(
					request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _("Invalid invitation code"),
						u'code': 'InvalidInvitationCode',
					},
					None)
		invitation = invitations[invite_code]
		if invitation.is_accepted():
			raise_json_error(
					request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _("Invitation already accepted"),
						u'code': 'InvitationAlreadyAccepted',
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
						u'message': _("Invitation is not for this user"),
						u'code': 'InvitationIsNotForUser',
					},
					None)
		return invitation

	def _do_call(self):
		request = self.request
		invitation = self._do_validation()
		try:
			accept_invitation(self.context, invitation)
		except InvitationValidationError as e:
			e.field = 'invitation'
			self.handle_validation_error(request, e)
		except Exception as e:  # pragma: no cover
			self.handle_possible_validation_error(request, e)

	def __call__(self):
		"""
		Implementation of :const:`REL_ACCEPT_INVITATION`.
		"""
		self._do_call()
		return hexc.HTTPNoContent()

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IUser,
			 permission=nauth.ACT_UPDATE,
			 request_method='GET',
			 name=REL_PENDING_INVITATIONS)
class GetPendingInvitationsView(AbstractAuthenticatedView):
		
	def _do_call(self):
		result = LocatedExternalDict()
		email = getattr(IUserProfile(self.context, None), 'email', None)
		receivers = (self.context.username, email)
		result[ITEMS] = get_pending_invitations(receivers)
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		return result

	def __call__(self):
		"""
		Implementation of :const:`REL_PENDING_INVITATIONS`.
		"""
		return self._do_call()
