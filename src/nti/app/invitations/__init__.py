#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory('nti.dataserver')

#: Invitations path adapter
INVITATIONS = u'Invitations'

#: The link relationship type to which an authenticated
#: user can ``POST`` data to accept outstanding invitations. Also the name of a
#: view to handle this feedback: :func:`accept_invitations_view`
#: The data should be an dictionary containing the key ``invitation``
#: whose value is an invitation code.
REL_ACCEPT_INVITATION = u'accept-invitation'

#: The link relationship type to which an anonymous, unauthenticated
#: user can ``GET`` data to accept outstanding site invitations.
REL_ACCEPT_SITE_INVITATION = u'accept-site-invitation'

#: The link relationship type to which an authenticated
#: user can ``POST`` data to decline outstanding invitations.
REL_DECLINE_INVITATION = u'decline-invitation'

#: The link relationship type to which an authenticated
#: user can ``POST`` data to send an invitation.
REL_SEND_INVITATION = u'send-invitation'

#: The link relationship type to which an authenticated
#: user can ``POST`` data to send an invitation to a site
REL_SEND_SITE_INVITATION = u'send-site-invitation'

#: The link relationship type to which an authenticated
#: user can ``POST`` a csv file to send an invitation to a site
REL_SEND_SITE_CSV_INVITATION = u'send-site-csv-invitation'

#: The link relationship type to which an authenticated
#: user with site admin permissions can ``POST`` a code
#: to be set as a generic site invitation.
REL_GENERIC_SITE_INVITATION = u'generic-site-invitation'

#: The link relationship type to which an authenticated
#: user can ``GET`` the outstanding invitations.
REL_PENDING_INVITATIONS = u'pending-invitations'

#: The link relationship to which an authenticated
#: site admin can ``GET`` the outstanding site invitations
REL_PENDING_SITE_INVITATIONS = u'pending-site-invitations'

#: The link relationship type to which an authenticated
#: user can ``POST`` data to accept outstanding invitations. Also the name of a
#: view to handle this feedback: :func:`accept_invitations_view`
#: The data should be an dictionary containing the key ``invitation_codes``
#: whose value is an array of strings naming codes.
#: See also :func:`nti.appserver.account_creation_views.account_create_view`
REL_ACCEPT_INVITATIONS = u'accept-invitations'

#: The link relationship type that will be exposed to the creator of a
#: :class:`nti.dataserver.users.friends_lists.DynamicFriendsList`. A ``GET``
#: to this link will return the invitation code corresponding to the default invitation
#: to join that group, in the form of a dictionary: ``{invitation_code: "thecode"}``
#: If the invitation does not exist, one will be created; at most one such code can exist at a time.
#: There is no way to disable the code at this time (in the future that could be done with a
#: ``DELETE`` to this link type). See also :func:`get_default_trivial_invitation_code`
REL_TRIVIAL_DEFAULT_INVITATION_CODE = u'default-trivial-invitation-code'

#: The mimeType for Site Invitations. It is defined here so that is can be used
#: elsewhere as a parameter for querying the invitation catalog
SITE_INVITATION_MIMETYPE = u'application/vnd.nextthought.siteinvitation'

#: The mimeType for Join Entity Invitations. It is defined here so that is can be used
#: elsewhere as a parameter for querying the invitation catalog
JOIN_ENTITY_INVITATION_MIMETYPE = u'application/vnd.nextthought.joinentityinvitation'

#: The mimeType for Generic Site Invitations. It is defined here so that is can be used
#: elsewhere as a parameter for querying the invitation catalog
GENERIC_SITE_INVITATION_MIMETYPE = u'application/vnd.nextthought.genericsiteinvitation'

#: The mimeType for Site Admin Invitations. It is defined here so that is can be used
#: elsewhere as a parameter for querying the invitation catalog
SITE_ADMIN_INVITATION_MIMETYPE = u'application/vnd.nextthought.siteadmininvitation'

#: The key for a request session that has a user's invitation code
SITE_INVITATION_SESSION_KEY = u'site_invitation_code'
