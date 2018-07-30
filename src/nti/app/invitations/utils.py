#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from nti.app.invitations import SITE_INVITATION_MIMETYPE

from nti.invitations.utils import get_pending_invitations

from nti.site.site import getSite

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


def pending_site_invitations_for_email(user):
    email = getattr(user, 'email', user)
    current_site = getSite().__name__
    pending_invitations = get_pending_invitations(receivers=email,
                                                  mimeTypes=SITE_INVITATION_MIMETYPE)
    for pending in pending_invitations:
        if pending.target_site == current_site:
            return pending
