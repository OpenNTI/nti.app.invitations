#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface, component

from nti.app.invitations.interfaces import IChallengeLogonProvider

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

from nti.appserver.interfaces import IApplicationSettings

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IChallengeLogonProvider)
class ChallengeLogonProvider(SchemaConfigured):
    createDirectFieldProperties(IChallengeLogonProvider)

    def logon_url(self, request):
        settings = component.getUtility(IApplicationSettings)
        web_root = settings.get('web_app_root', '/NextThoughtWebApp/')[:-1]
        app_url = request.application_url + web_root
        return app_url
