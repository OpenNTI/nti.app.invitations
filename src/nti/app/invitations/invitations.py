#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import six

from zope import component
from zope import interface

from zope.event import notify

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.invitations import SITE_INVITATION_MIMETYPE
from nti.app.invitations import SITE_ADMIN_INVITATION_MIMETYPE
from nti.app.invitations import JOIN_ENTITY_INVITATION_MIMETYPE
from nti.app.invitations import GENERIC_SITE_INVITATION_MIMETYPE

from nti.app.invitations.interfaces import ISiteInvitation
from nti.app.invitations.interfaces import ISiteInvitationActor
from nti.app.invitations.interfaces import ISiteAdminInvitation
from nti.app.invitations.interfaces import IJoinEntityInvitation
from nti.app.invitations.interfaces import IGenericSiteInvitation
from nti.app.invitations.interfaces import IJoinEntityInvitationActor

from nti.dataserver.authorization import ROLE_SITE_ADMIN

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IFriendsList

from nti.dataserver.users.entity import Entity

from nti.dataserver.users.interfaces import IUserProfile

from nti.dataserver.users.users import User

from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import InvitationAcceptedEvent
from nti.invitations.interfaces import InvitationEmailNotMatchingError
from nti.invitations.interfaces import InvitationSiteNotMatchingError

from nti.invitations.model import Invitation

from nti.property.property import alias

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.site.site import getSite

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IJoinEntityInvitation)
class JoinEntityInvitation(Invitation):
    createDirectFieldProperties(IJoinEntityInvitation)

    mimeType = mime_type = JOIN_ENTITY_INVITATION_MIMETYPE
JoinCommunityInvitation = JoinEntityInvitation


@interface.implementer(ISiteInvitation)
class SiteInvitation(Invitation):
    createDirectFieldProperties(ISiteInvitation)

    mimeType = mime_type = SITE_INVITATION_MIMETYPE

    __external_class_name__ = "SiteInvitation"

    __external_can_create__ = True

    Code = alias('code')

    def __setattr__(self, key, value):
        if key == "receiver" and not self.target_receiver:
            self.target_receiver = value
        super(SiteInvitation, self).__setattr__(key, value)



@interface.implementer(IGenericSiteInvitation)
class GenericSiteInvitation(SiteInvitation):
    mimeType = mime_type = GENERIC_SITE_INVITATION_MIMETYPE

    __external_class_name__ = "GenericSiteInvitation"

    _excluded_out_ivars = ('receiver',)


@interface.implementer(ISiteAdminInvitation)
class SiteAdminInvitation(SiteInvitation):
    mimeType = mime_type = SITE_ADMIN_INVITATION_MIMETYPE

    __external_class_name__ = "SiteAdminInvitation"


@interface.implementer(IJoinEntityInvitationActor)
class JoinEntityInvitationActor(object):

    def __init__(self, invitation=None):
        self.invitation = invitation

    def accept(self, user, invitation=None):
        result = True
        invitation = self.invitation if invitation is None else invitation
        entity = Entity.get_entity(invitation.entity)
        if entity is None:
            logger.warning("Entity %s does not exists", invitation.entity)
            result = False
        elif ICommunity.providedBy(entity):
            logger.info("Accepting invitation to join community %s", entity)
            user.record_dynamic_membership(entity)
            user.follow(entity)
        elif IFriendsList.providedBy(entity):
            logger.info("Accepting invitation to join DFL %s", entity)
            entity.addFriend(user)
        else:
            result = False
            logger.warning("Don't know how to accept invitation to join entity %s",
                           entity)
        return result


class SiteInvitationActorMixin(object):

    def __init__(self, invitation=None):
        self.invitation = invitation

    def user_profile(self, user):
        if isinstance(user, six.string_types):
            user = User.get_user(user)
        profile = IUserProfile(user)
        return profile

    def check_valid_invitation(self, profile, invitation, link_email):
        email = getattr(profile, 'email', '')
        # Require the email on the account to match if flag set or there's
        # no email provided with the link (and set in the session)
        if invitation.require_matching_email or not link_email:
            if not email.lower() == invitation.receiver.lower():
                raise InvitationEmailNotMatchingError
        elif link_email.lower() != invitation.receiver.lower():
            # We still require at least the link email to match
            raise InvitationEmailNotMatchingError

        if not invitation.target_site == getSite().__name__:
            raise InvitationSiteNotMatchingError


@interface.implementer(ISiteInvitationActor)
@component.adapter(ISiteInvitation)
class DefaultSiteInvitationActor(SiteInvitationActorMixin):

    def accept(self, user, invitation=None, link_email=None):
        profile = self.user_profile(user)
        self.check_valid_invitation(profile, invitation, link_email)
        invitation.accepted = True
        invitation.receiver = getattr(user, 'username', user)  # update
        notify(InvitationAcceptedEvent(invitation, user))
        return True


@interface.implementer(ISiteInvitationActor)
@component.adapter(IGenericSiteInvitation)
class DefaultGenericSiteInvitationActor(SiteInvitationActorMixin):

    def accept(self, user, invitation=None):
        generic_invitation = self.invitation if invitation is None else invitation
        invitation = SiteInvitation(receiver=getattr(user, 'username', user),
                                    sender=generic_invitation.sender,
                                    target_site=getSite().__name__,
                                    accepted=True)
        invitations = component.getUtility(IInvitationsContainer)
        invitations.add(invitation)
        notify(InvitationAcceptedEvent(invitation, user))
        return True


@interface.implementer(ISiteInvitationActor)
@component.adapter(ISiteAdminInvitation)
class DefaultSiteAdminInvitationActor(SiteInvitationActorMixin):

    def _make_site_admin(self, user, site):
        username = getattr(user, 'username', user)
        principal_role_manager = IPrincipalRoleManager(site)
        logger.info("Adding user to site admin role (site=%s) (user=%s)",
                    site.__name__,
                    username)
        # pylint: disable=too-many-function-args
        principal_role_manager.assignRoleToPrincipal(ROLE_SITE_ADMIN.id,
                                                     username)

    def accept(self, user, invitation=None, link_email=None):
        receiver_profile = self.user_profile(user)
        self.check_valid_invitation(receiver_profile, invitation, link_email)
        invitation.accepted = True
        invitation.receiver = getattr(user, 'username', user)
        self._make_site_admin(user, getSite())
        notify(InvitationAcceptedEvent(invitation, user))
        return True
