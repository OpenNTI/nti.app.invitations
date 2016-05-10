#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory('nti.dataserver')

#: Invitations path adapter
INVITATIONS = 'Invitations'

#: The link relationship type to which an authenticated
#: user can ``POST`` data to accept outstanding invitations. Also the name of a
#: view to handle this feedback: :func:`accept_invitations_view`
#: The data should be an dictionary containing the key ``invitation``
#: whose value is an invitation code.
REL_ACCEPT_INVITATION = 'accept-invitation'

#: The link relationship type to which an authenticated
#: user can ``POST`` data to decline outstanding invitations.
REL_DECLINE_INVITATION = 'decline-invitation'

#: The link relationship type to which an authenticated
#: user can ``POST`` data to send an invitation.
REL_SEND_INVITATION = 'send-invitation'

#: The link relationship type to which an authenticated
#: user can ``GET`` the outstanding invitations.
REL_PENDING_INVITATIONS = 'pending-invitations'

#: The link relationship type to which an authenticated
#: user can ``POST`` data to accept outstanding invitations. Also the name of a
#: view to handle this feedback: :func:`accept_invitations_view`
#: The data should be an dictionary containing the key ``invitation_codes``
#: whose value is an array of strings naming codes.
#: See also :func:`nti.appserver.account_creation_views.account_create_view`
REL_ACCEPT_INVITATIONS = 'accept-invitations'

#: The link relationship type that will be exposed to the creator of a
#: :class:`nti.dataserver.users.friends_lists.DynamicFriendsList`. A ``GET``
#: to this link will return the invitation code corresponding to the default invitation
#: to join that group, in the form of a dictionary: ``{invitation_code: "thecode"}``
#: If the invitation does not exist, one will be created; at most one such code can exist at a time.
#: There is no way to disable the code at this time (in the future that could be done with a
#: ``DELETE`` to this link type). See also :func:`get_default_trivial_invitation_code`
REL_TRIVIAL_DEFAULT_INVITATION_CODE = 'default-trivial-invitation-code'
