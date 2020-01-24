#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from nti.app.invitations.invitations import InvitationInfo

from nti.invitations.interfaces import IInvitation

logger = __import__('logging').getLogger(__name__)


@component.adapter(IInvitation)
def invitation_info(invitation):
    return InvitationInfo(invitation)