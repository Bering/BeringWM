"""
BeringWM
Bering's Window Manager.

Author: bering@ringlogic.com
"""

import os
import sys
import traceback
import Xlib.rdb, Xlib.X, Xlib.XK
import beringwm

VERSION = (0, 2)
REQUIRED_XLIB_VERSION = (0, 14)

def main():
    if Xlib.__version__ < REQUIRED_XLIB_VERSION:
        sys.stderr.write('Xlib version 0.14 is required, {ver} was found\n'.format(ver='.'.join(str(i) for i in Xlib.__version__)))
        return 2

    try:
        display, appname, resource_database, args = Xlib.rdb.get_display_opts(Xlib.rdb.stdopts)
    except Xlib.error.DisplayConnectionError:
        sys.stderr.write("Can't connect to display " + os.environ['DISPLAY'] + "\n")
        return 2
    
    try:
        wm = beringwm.BeringWM(display)
    except beringwm.NoUnmanagedScreens:
        sys.stderr.write('No unmanaged screens found\n')
        return 2

    try:
        wm.main_loop()
        return 0
    except Xlib.error.ConnectionClosedError:
        sys.stderr.write('Display connection closed by server\n')
        return 3
    except KeyboardInterrupt:
        print('Exited normally')
        return 0
    except SystemExit:
        raise
    except:
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    
    # force using Zephyr's display during development
    os.environ["DISPLAY"] = ":1"
    
    print("Starting Bering's WM on display", os.environ["DISPLAY"])
    sys.exit(main())
