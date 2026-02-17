# Earth Rovers (FrodoBot) SDK - re-export from earth-rovers-sdk (hyphen not valid in Python module name)
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_hyphen_sdk = os.path.join(os.path.dirname(_here), 'earth-rovers-sdk')
if _hyphen_sdk not in sys.path:
    sys.path.insert(0, _hyphen_sdk)

import rtm_client as _rtm_client
import browser_service as _browser_service

RtmClient = _rtm_client.RtmClient
BrowserService = _browser_service.BrowserService

__all__ = ['RtmClient', 'BrowserService']
