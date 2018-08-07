#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from zope import component
from zope import interface

from zope.cachedescriptors.property import readproperty

from nti.app.invitations import JOIN_ENTITY_INVITATION_MIMETYPE
from nti.app.invitations import SITE_INVITATION_MIMETYPE

from nti.app.invitations.interfaces import IJoinEntityInvitation
from nti.app.invitations.interfaces import IJoinEntityInvitationActor
from nti.app.invitations.interfaces import ISiteInvitation
from nti.app.invitations.interfaces import ISiteInvitationActor
from nti.app.invitations.interfaces import IVerifyAndAcceptSiteInvitation
from nti.app.invitations.utils import pending_site_invitations_for_email

from nti.appserver.logon import _create_failure_response
from nti.appserver.logon import _create_success_response

from nti.coremetadata.interfaces import IDataserver
from nti.coremetadata.interfaces import IUser

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IFriendsList

from nti.dataserver.users import User

from nti.dataserver.users.entity import Entity

from nti.dataserver.users.interfaces import IUserProfile

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
class JoinSiteInvitation(Invitation):
    createDirectFieldProperties(ISiteInvitation)

    mimeType = mime_type = SITE_INVITATION_MIMETYPE

    receiver_email = alias('receiver')

    @readproperty
    def receiver_name(self):
        return getattr(self.receiver, 'realname', None)


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


@interface.implementer(ISiteInvitationActor)
class DefaultSiteInvitationActor(object):
    # TODO This actor is not intended to be used in production as is

    def __init__(self, site):
        self.site = site

    def accept(self, request, invitation):
        if invitation.target_site != getSite().__name__:
            logger.exception(u'Invalid site invitation')
            return hexc.HTTPConflict(u'The invitation you are trying to accept is not valid for this site.')
        if invitation.IsGeneric:
            # TODO this could be a redirect to account creation page
            logger.exception(u'Unsupported invitation type (generic).')
            return hexc.HTTPNotImplemented(u'Generic invitation codes are not yet supported for this site.')

        dataserver = component.getUtility(IDataserver)
        user = User.get_user(username=invitation.receiver, dataserver=dataserver)
        if user is not None:
            accepter = IVerifyAndAcceptSiteInvitation(user)
            accepter.accept(invitation)
            return hexc.HTTPConflict(u'The email this invite was sent for is already associated with an account.')
        # We need to create them an NT account and log them in
        else:
            user = User.create_user(username=invitation.receiver_email,
                                    external_value={'realname': invitation.receiver_name})
            user = IUserProfile(user)
            user.email = invitation.receiver_email
            user.email_verified = True
            if user is not None:
                accepter = IVerifyAndAcceptSiteInvitation(user)
                accepter.accept(invitation)
                return _create_success_response(request,
                                                userid=user.username)
            return _create_failure_response(request)


@component.adapter(IUser)
@interface.implementer(IVerifyAndAcceptSiteInvitation)
class VerifyAndAcceptSiteInvitation(object):

    def __init__(self, user):
        self.user = user

    def accept(self, invitation=None):
        # If we get passed an invitation then we can just update it and be done
        # otherwise try to fuzzy match the newly created user to an invite
        user = IUserProfile(self.user, None)
        email = getattr(user, 'email', None)
        invitation = pending_site_invitations_for_email(email) if invitation is None else invitation
        if invitation is not None and not invitation.IsGeneric:
            invitation.accepted = True
            invitation.receiver = getattr(user, 'username', user)  # update
        # The user may have gotten here through a generic invitation or our fuzzy match didn't work
        # Let's go ahead and create an invitation for them so that it is documented they accepted an
        # invitation to this site
        elif invitation.IsGeneric:
            invitation = JoinSiteInvitation(receiver=user,
                                            target_site=getSite(),
                                            accepted=True)
        accepter = IVerifyAndAcceptSiteInvitation(user)
        accepter.accept(invitation)
