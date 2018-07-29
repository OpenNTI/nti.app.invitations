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
from nti.invitations.interfaces import MarkAsAcceptedInvitationEvent
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
from zope.event import notify

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IJoinEntityInvitation)
class JoinEntityInvitation(Invitation):
    createDirectFieldProperties(IJoinEntityInvitation)

    mimeType = mime_type = JOIN_ENTITY_INVITATION_MIMETYPE
JoinCommunityInvitation = JoinEntityInvitation


@interface.implementer(ISiteInvitation)
class JoinSiteInvitation(JoinEntityInvitation):
    createDirectFieldProperties(ISiteInvitation)

    mimeType = mime_type = SITE_INVITATION_MIMETYPE

    receiver_email = alias('receiver')
    entity = alias('site')

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

    def __init__(self, site):
        self.site = site

    def accept(self, request, invitation):
        dataserver = component.getUtility(IDataserver)
        user = User.get_user(username=invitation.receiver, dataserver=dataserver)
        if user is not None:
            notify(MarkAsAcceptedInvitationEvent(user))
            return hexc.HTTPConflict(u'The email this invite was sent for is already associated with an account.')
        # We need to create them an NT account and log them in
        else:
            # TODO Is this the behavior we want?
            # TODO could also redirect to account creation
            user = User.create_user(username=invitation.receiver_email,
                                    external_value={'realname': invitation.receiver_name})
            if user is not None:
                notify(MarkAsAcceptedInvitationEvent(user))
                return _create_success_response(request,
                                                userid=user.username)
            return _create_failure_response(request)
