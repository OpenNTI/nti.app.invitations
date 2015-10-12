#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.dataserver.users import Entity
from nti.dataserver.interfaces import IEntity

from nti.invitations.interfaces import IInvitationEntityFinder

@interface.implementer(IInvitationEntityFinder)
class InvitationEntityFinder(object):
    
    def find(self, entity):
        if entity is not None and not IEntity.providedBy(entity):
            return Entity.get_entity(str(entity))
        return entity
