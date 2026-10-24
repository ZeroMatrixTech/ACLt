# SPDX-License-Identifier: Apache-2.0
"""Pinned recovery wrapper over the unchanged v2 funding/evidence primitives."""
from pathlib import Path
import sys
BASE = Path(__file__).resolve().parent.parent/'aclt-fixed-settlement'
sys.path.insert(0,str(BASE))
from wire import *
from wire import environment as base_environment
HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))


def environment():
    return tagged('ACLt/Experiment/SettlementRecoveryEnvironment/1',encode({
        'base':base_environment(), 'wrappers':{p.name:sha(regular(p)) for p in sorted(HERE.glob('*.py'))}}))
