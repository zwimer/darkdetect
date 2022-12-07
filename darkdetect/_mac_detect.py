#-----------------------------------------------------------------------------
#  Copyright (C) 2019 Alberto Sottile
#
#  Distributed under the terms of the 3-clause BSD License.
#-----------------------------------------------------------------------------

import ctypes
import ctypes.util
import subprocess
import sys
import os
from pathlib import Path
from typing import Callable

try:
    from Foundation import NSDistributedNotificationCenter, NSObject
    from PyObjCTools import AppHelper
    _can_listen = True
except ModuleNotFoundError:
    _can_listen = False


try:
    # macOS Big Sur+ use "a built-in dynamic linker cache of all system-provided libraries"
    objc = ctypes.cdll.LoadLibrary('libobjc.dylib')
except OSError:
    # revert to full path for older OS versions and hardened programs
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))

void_p = ctypes.c_void_p
ull = ctypes.c_uint64

objc.objc_getClass.restype = void_p
objc.sel_registerName.restype = void_p

# See https://docs.python.org/3/library/ctypes.html#function-prototypes for arguments description
MSGPROTOTYPE = ctypes.CFUNCTYPE(void_p, void_p, void_p, void_p)
msg = MSGPROTOTYPE(('objc_msgSend', objc), ((1 ,'', None), (1, '', None), (1, '', None)))

def _utf8(s):
    if not isinstance(s, bytes):
        s = s.encode('utf8')
    return s

def n(name):
    return objc.sel_registerName(_utf8(name))

def C(classname):
    return objc.objc_getClass(_utf8(classname))

def theme():
    NSAutoreleasePool = objc.objc_getClass('NSAutoreleasePool')
    pool = msg(NSAutoreleasePool, n('alloc'))
    pool = msg(pool, n('init'))

    NSUserDefaults = C('NSUserDefaults')
    stdUserDef = msg(NSUserDefaults, n('standardUserDefaults'))

    NSString = C('NSString')

    key = msg(NSString, n("stringWithUTF8String:"), _utf8('AppleInterfaceStyle'))
    appearanceNS = msg(stdUserDef, n('stringForKey:'), void_p(key))
    appearanceC = msg(appearanceNS, n('UTF8String'))

    if appearanceC is not None:
        out = ctypes.string_at(appearanceC)
    else:
        out = None

    msg(pool, n('release'))

    if out is not None:
        return out.decode('utf-8')
    else:
        return 'Light'

def isDark():
    return theme() == 'Dark'

def isLight():
    return theme() == 'Light'


def _listen_child():
    """
    Run by a child process, install an observer and print theme on change
    """
    class Observer(NSObject):
        def callback_(self, _):
            try:
                print(theme(), flush=True)
            except IOError:
                os._exit(1)
    observer = Observer.new()  # Keep a reference of the observer to keep it alive
    NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
        observer,  # Observer must be kept alive by a different reference
        "callback:",
        "AppleInterfaceThemeChangedNotification",
        None
    )
    AppHelper.runConsoleEventLoop()


def listener(callback: Callable[[str], None]) -> None:
    if not _can_listen:
        raise NotImplementedError()
    pth = f"import sys; sys.path.insert(0, r'''{Path(__file__).parents[1]}''')"
    sig = "import signal as s; s.signal(s.SIGINT, s.SIG_IGN)"
    listen = "import darkdetect as dd; dd._mac_detect._listen_child()"
    with subprocess.Popen(
        (sys.executable, "-c", f"{pth}; {sig}; {listen}"),
        stdout=subprocess.PIPE,
        # stderr=subprocess.DEVNULL,
        universal_newlines=True,
    ) as p:
        for line in p.stdout:
            callback(line.strip())
