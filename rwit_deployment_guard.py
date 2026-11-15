"""Entry-point data source enforcement for Platform Compass.

This is a routing guard, not an OS sandbox. Never deploy private data or secrets
in the demo app's environment or repository.
"""
from __future__ import annotations
import os

_VALID = {'demo', 'private_cloud', 'local'}

def select_deployment(mode: str) -> None:
    if mode not in _VALID:
        raise ValueError('Unsupported Sample Tech Community deployment')
    previous = os.environ.get('RWIT_DEPLOYMENT')
    if previous is not None and previous != mode:
        raise RuntimeError('Sample Tech Community deployment cannot be switched in the current process')
    os.environ['RWIT_DEPLOYMENT'] = mode
    os.environ['RWIT_DATA_MODE'] = 'demo' if mode == 'demo' else 'community'
    for flag in ('RWIT_LINKEDIN_LOCAL_PREVIEW', 'RWIT_MEETUP_LOCAL_PREVIEW'):
        if mode != 'local':
            os.environ.pop(flag, None)

def assert_mode(expected: str) -> None:
    if expected not in _VALID or os.environ.get('RWIT_DEPLOYMENT') != expected:
        raise RuntimeError('Sample Tech Community deployment mode mismatch')
    desired_data_mode = 'demo' if expected == 'demo' else 'community'
    if os.environ.get('RWIT_DATA_MODE') != desired_data_mode:
        raise RuntimeError('Sample Tech Community data source mismatch')
    if expected != 'local' and any(os.environ.get(flag) == '1' for flag in (
            'RWIT_LINKEDIN_LOCAL_PREVIEW', 'RWIT_MEETUP_LOCAL_PREVIEW')):
        raise RuntimeError('Local preview sources prohibited in Cloud')
