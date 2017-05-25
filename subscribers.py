#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zc.intid.interfaces import IBeforeIdRemovedEvent

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.utils import get_sent_invitations


@component.adapter(IUser, IBeforeIdRemovedEvent)
def _user_removed(user, event):
    invitations = set()
    # check unaccepted invitations sent via username
    invitations.update(get_sent_invitations(user.username))
    # check unaccepted invitations sent via user's email
    profile = IUserProfile(user, None)
    email = getattr(profile, 'email', None)
    if email:
        invitations.update(get_sent_invitations(email))
    # remove unaccepted invitations
    container = component.getUtility(IInvitationsContainer)
    for invitation in invitations:
        container.remove(invitation)
