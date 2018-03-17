#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from requests.structures import CaseInsensitiveDict

from zope import component

from zope.intid.interfaces import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.invitations.views import InvitationsPathAdapter

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.invitations.index import get_invitations_catalog

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.utils import get_invitations
from nti.invitations.utils import get_expired_invitations
from nti.invitations.utils import get_pending_invitations
from nti.invitations.utils import delete_expired_invitations

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


@view_config(context=InvitationsPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_NTI_ADMIN,
               name='AllInvitations')
class AllInvitationsView(AbstractAuthenticatedView,
                         BatchingUtilsMixin):

    _DEFAULT_BATCH_SIZE = 20
    _DEFAULT_BATCH_START = 0

    def __call__(self):
        values = CaseInsensitiveDict(self.request.params)
        senders = values.get('sender') or values.get('senders')
        receivers = values.get('receiver') or values.get('receivers')
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        items = get_invitations(receivers=receivers, senders=senders)
        self._batch_items_iterable(result, items)
        result[TOTAL] = len(items)
        return result


@view_config(context=InvitationsPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_NTI_ADMIN,
               name='PendingInvitations')
class GetPendingInvitationsView(AbstractAuthenticatedView):

    def __call__(self):
        values = CaseInsensitiveDict(self.request.params)
        usernames = values.get('receiver') \
                 or values.get('username') \
                 or values.get('receivers') \
                 or values.get('usernames')
        if isinstance(usernames, six.string_types):
            usernames = usernames.split(",")
        usernames = None if not usernames else set(usernames)
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        items = result[ITEMS] = get_pending_invitations(usernames)
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(context=InvitationsPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               permission=nauth.ACT_NTI_ADMIN,
               name='ExpiredInvitations')
class GetExpiredInvitationsView(AbstractAuthenticatedView):

    def __call__(self):
        values = CaseInsensitiveDict(self.request.params)
        usernames = values.get('username') or values.get('usernames')
        if isinstance(usernames, six.string_types):
            usernames = usernames.split(",")
        usernames = None if not usernames else set(usernames)
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        items = result[ITEMS] = get_expired_invitations(usernames)
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(context=InvitationsPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               permission=nauth.ACT_NTI_ADMIN,
               name='DeleteExpiredInvitations')
class DeleteExpiredInvitationsView(AbstractAuthenticatedView,
                                   ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        if self.request.body:
            result = super(DeleteExpiredInvitationsView, self).readInput(value)
            result = CaseInsensitiveDict(result)
        else:
            result = CaseInsensitiveDict(self.request.params)
        return result

    def __call__(self):
        values = self.readInput()
        usernames = values.get('username') or values.get('usernames')
        if isinstance(usernames, six.string_types):
            usernames = usernames.split(",")
        usernames = None if not usernames else set(usernames)
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context
        items = result[ITEMS] = delete_expired_invitations(usernames)
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(context=InvitationsPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="RebuildInvitationsCatalog",
               permission=nauth.ACT_NTI_ADMIN)
class RebuildInvitationsCatalogView(AbstractAuthenticatedView):

    def _process_meta(self, package):
        try:
            from nti.metadata import queue_add
            queue_add(package)
        except ImportError:
            pass

    def __call__(self):
        count = 0
        intids = component.getUtility(IIntIds)
        # remove indexes
        catalog = get_invitations_catalog()
        for index in catalog.values():
            index.clear()
        # reindex
        container = component.getUtility(IInvitationsContainer)
        for invitation in list(container.values()):
            doc_id = intids.queryId(invitation)
            if doc_id is None:
                continue
            count += 1
            catalog.index_doc(doc_id, invitation)
            self._process_meta(invitation)
        result = LocatedExternalDict()
        result[ITEM_COUNT] = result[TOTAL] = count
        return result
