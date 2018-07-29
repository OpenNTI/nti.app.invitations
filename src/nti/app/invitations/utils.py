#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from nti.app.invitations.interfaces import ISiteInvitation

from nti.invitations.utils import get_pending_invitations

from nti.site.site import getSite

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


def pending_site_invitations_for_user(user):
    email = getattr('email', user, user)
    current_site = getSite().__name__
    pending_invitations = get_pending_invitations([email])
    for pending in pending_invitations:
        if ISiteInvitation.providedBy(pending) and pending.site == current_site:
            return pending
