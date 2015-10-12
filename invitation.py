#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.dataserver.users import Entity
from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IFriendsList
from nti.dataserver.interfaces import SYSTEM_USER_NAME

from nti.invitations.invitation import ZcmlInvitation

class JoinEntitiesInvitation(ZcmlInvitation):
    """
    Simple first pass at a pre-configured invitation to join existing
    entities. Intended to be configured with ZCML and not stored persistently.
    """

    creator = SYSTEM_USER_NAME

    def __init__(self, code, entities):
        super(JoinEntitiesInvitation, self).__init__()
        self.code = code
        self.entities = entities

    def _iter_entities(self):
        for entity_name in self.entities:
            entity = Entity.get_entity(entity_name)
            if entity is None:
                logger.warn("Unable to accept invitation to join non-existent entity %s",
                             entity_name)
                continue
            yield entity

    def accept(self, user):
        for entity in self._iter_entities():
            if ICommunity.providedBy(entity):
                logger.info("Accepting invitation to join community %s", entity)
                user.record_dynamic_membership(entity)
                user.follow(entity)
            elif IFriendsList.providedBy(entity):
                logger.info("Accepting invitation to join DFL %s", entity)
                entity.addFriend(user)
            else:
                logger.warn("Don't know how to accept invitation to join entity %s",
                            entity)
        super(JoinEntitiesInvitation, self).accept(user)

JoinCommunityInvitation = JoinEntitiesInvitation
