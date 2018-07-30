#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.app.invitations import SITE_INVITATION_MIMETYPE, JOIN_ENTITY_INVITATION_MIMETYPE
from nti.appserver.logon import _create_success_response, _create_failure_response
from nti.coremetadata.interfaces import IDataserver
from nti.dataserver.users import User
from nti.dataserver.users.interfaces import IUserProfile
from nti.invitations.interfaces import MarkAsAcceptedInvitationEvent
from nti.site.site import get_component_hierarchy_names
from zope import interface, component
from pyramid import httpexceptions as hexc
from zope.cachedescriptors.property import readproperty

from nti.app.invitations.interfaces import IJoinEntityInvitation
from nti.app.invitations.interfaces import IJoinEntityInvitationActor
from nti.app.invitations.interfaces import ISiteInvitation
from nti.app.invitations.interfaces import ISiteInvitationActor

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IFriendsList

from nti.dataserver.users.entity import Entity

from nti.invitations.model import Invitation

from nti.property.property import alias

from nti.schema.fieldproperty import createDirectFieldProperties
from zope.component.hooks import getSite
from zope.event import notify

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
        # Check that this invitation is for the current site
        if invitation.target_site != getSite().__name__:
            return hexc.HTTPConflict(u'The invitation you are trying to accept is not valid for this site.')

        dataserver = component.getUtility(IDataserver)
        user = User.get_user(username=invitation.receiver, dataserver=dataserver)
        if user is not None:
            notify(MarkAsAcceptedInvitationEvent(user))
            return hexc.HTTPConflict(u'The email this invite was sent for is already associated with an account.')
        # We need to create them an NT account and log them in
        else:
            user = User.create_user(username=invitation.receiver_email,
                                    external_value={'realname': invitation.receiver_name})
            user = IUserProfile(user)
            user.email = invitation.receiver_email
            user.email_verified = True
            if user is not None:
                notify(MarkAsAcceptedInvitationEvent(user))
                return _create_success_response(request,
                                                userid=user.username)
            return _create_failure_response(request)
