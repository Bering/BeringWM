import os
import sys
import traceback
import Xlib.rdb, Xlib.X, Xlib.XK
import utils

MAX_EXCEPTIONS = 25
RELEASE_MODIFIER = Xlib.X.AnyModifier << 1

class NoUnmanagedScreens(Exception):
    pass

class BeringWM:
    def __init__(self, display):
        self.ShouldQuit = False
        self.display = display
        self.drag_window = None
        self.drag_offset = (0, 0)

        if display is not None:
            os.environ['DISPLAY'] = display.get_display_name()
        
        self.enter_codes = set(code for code, index in self.display.keysym_to_keycodes(Xlib.XK.XK_Return))
        self.A_Q_codes = set(code for code, index in self.display.keysym_to_keycodes(Xlib.XK.XK_Q))
        self.A_C_codes = set(code for code, index in self.display.keysym_to_keycodes(Xlib.XK.XK_C))
        self.A_R_codes = set(code for code, index in self.display.keysym_to_keycodes(Xlib.XK.XK_R))

        self.screens = []
        for screen_id in range(0, display.screen_count()):
            if self.hook_to_screen(screen_id):
                self.screens.append(screen_id)

        if len(self.screens) == 0:
            raise NoUnmanagedScreens()

        self.windows = {}
        self.capture_all_windows()

        self.display.set_error_handler(self.x_error_handler)

        self.event_dispatch_table = {
            Xlib.X.CreateNotify: self.handle_create_notify,
            Xlib.X.DestroyNotify: self.handle_destroy_notify,
            Xlib.X.ConfigureRequest: self.handle_configure_request,
            Xlib.X.ConfigureNotify: self.handle_configure_notify,
            Xlib.X.MapRequest: self.handle_map_request,
            Xlib.X.MapNotify: self.handle_map_notify,
            Xlib.X.MappingNotify: self.handle_mapping_notify,
            Xlib.X.UnmapNotify: self.handle_unmap_notify,
            Xlib.X.ReparentNotify: self.handle_reparent_notify,
            Xlib.X.ClientMessage: self.handle_client_message,

            Xlib.X.MotionNotify: self.handle_mouse_motion,
            Xlib.X.ButtonPress: self.handle_mouse_press,
            Xlib.X.ButtonRelease: self.handle_mouse_release,
            Xlib.X.KeyPress: self.handle_key_press,
            Xlib.X.KeyRelease: self.handle_key_release,
        }

    def hook_to_screen(self, screen_id):
        '''
        Setup substructure redirection and grab keys. Returns True on success.
        '''

        # Setup substructure redirection on the root window
        screen = self.display.screen(screen_id)
        root_window = screen.root

        error_catcher = Xlib.error.CatchError(Xlib.error.BadAccess)
        mask = Xlib.X.SubstructureRedirectMask
        root_window.change_attributes(event_mask=mask, onerror=error_catcher)

        self.display.sync()
        error = error_catcher.get_error()
        if error:
            return False

        # Register global keybindings
        for code in self.enter_codes:
            root_window.grab_key(
                code,
                Xlib.X.Mod1Mask & ~RELEASE_MODIFIER,
                1,
                Xlib.X.GrabModeAsync,
                Xlib.X.GrabModeAsync
            )
        for code in self.A_Q_codes:
            root_window.grab_key(
                code,
                Xlib.X.Mod1Mask & ~RELEASE_MODIFIER,
                1,
                Xlib.X.GrabModeAsync,
                Xlib.X.GrabModeAsync
            )
        for code in self.A_C_codes:
            root_window.grab_key(
                code,
                Xlib.X.Mod1Mask & ~RELEASE_MODIFIER,
                1,
                Xlib.X.GrabModeAsync,
                Xlib.X.GrabModeAsync
            )
        for code in self.A_R_codes:
            root_window.grab_key(
                code,
                Xlib.X.Mod1Mask & ~RELEASE_MODIFIER,
                1,
                Xlib.X.GrabModeAsync,
                Xlib.X.GrabModeAsync
            )

        return True

    def x_error_handler(self, err, request):
        sys.stderr.write('X protocol error: {0}'.format(err))

    def capture_window(self, screen, window):
        """
        Draw a frame around a window and subscribe to substructure redirection
        """

        print('Capturing window {0}/{1} {2} {3}... '.format(window.owner, window.id, window.get_wm_class(), window.get_wm_name()), end="")

        a = window.get_attributes()

        if a.override_redirect:
            print("(override_redirect) ", end="")

        if a.map_state != Xlib.X.IsViewable:
            print("Not viewable")
            return

        g = window.get_geometry()

        frame = screen.root.create_window(
            x=g.x,y=g.y, width=g.width, height=g.height, depth=screen.root_depth, border_width=2,
            border_pixel=screen.white_pixel, event_mask=Xlib.X.SubstructureRedirectMask | Xlib.X.SubstructureNotifyMask
        )

        self.windows[frame.id] = window

        # TODO: add_to_save_set(window)?

        window.reparent(frame, 0, 0)

        # TODO: frame.set_wm_class, set_wm_name, etc?

        frame.map()

        frame.grab_button(3, 0, True,
            Xlib.X.ButtonMotionMask | Xlib.X.ButtonReleaseMask | Xlib.X.ButtonPressMask,
            Xlib.X.GrabModeAsync,
            Xlib.X.GrabModeAsync,
            Xlib.X.NONE,
            Xlib.X.NONE,
            None)
        
        print("Captured")

    def capture_all_windows(self):
        """
        Capture all the windows of all the screens
        """
        
        if len(self.windows):
            print("There are captive windows already!")
            return
        
        for screen_id in self.screens:
            screen = self.display.screen(screen_id)
            for window in screen.root.query_tree().children:
                self.capture_window(screen, window)

    def release_window(self, screen, frame):
        """
        Remove the frame around a captured window
        """

        window = self.windows[frame.id]

        print('Releasing window {0}/{1}... '.format(window.owner, window.id), end="")

        g = frame.get_geometry()
        window.reparent(screen.root, g.x, g.y)

        # TODO: Remove from saveset?

        frame.unmap()
        frame.destroy()

        del self.windows[frame.id]

        print("Released")
    
    def release_all_windows(self):
        """
        Release all the windows we have captured
        """
        print("Releasing all windows...")
        for screen_id in self.screens:
            screen = self.display.screen(screen_id)
            print(" Screen", screen_id)
            for frame in screen.root.query_tree().children:
                print("  Release window from frame {0}? ".format(frame.id), end="")
                if frame.id in self.windows:
                    self.release_window(screen, frame)
                else:
                    print("not a frame")

    def main_loop(self):
        '''
        Loop until Alt+Q or Ctrl+C or exceptions have occurred more than MAX_EXCEPTION times.
        '''
        self.Errors = 0
        ShouldReallyQuit = False
        while ShouldReallyQuit == False:

            if self.ShouldQuit == True:
                self.release_all_windows()
                while self.display.pending_events():
                    self.handle_event()
                ShouldReallyQuit = True
            
            else:
                self.handle_event()

    """
    Handle the next event in the queue. Blocks if there are no events in the queue.
    """
    def handle_event(self):
        try:
            event = self.display.next_event()
            if event.type in self.event_dispatch_table:
                handler = self.event_dispatch_table[event.type]
                handler(event)
            else:
                print('unhandled event: {event}'.format(event=event))
        except (KeyboardInterrupt):
            self.ShouldQuit = True
        except (SystemExit):
            self.release_all_windows()
            raise
        except:
            self.Errors += 1
            if self.Errors > MAX_EXCEPTIONS:
                self.release_all_windows()
                raise
            traceback.print_exc()
        
    def handle_create_notify(self, event):
        pass

    def handle_destroy_notify(self, event):
        pass

    def handle_configure_request(self, event):
        window = event.window
        args = { 'border_width': 3 }
        if event.value_mask & Xlib.X.CWX:
            args['x'] = event.x
        if event.value_mask & Xlib.X.CWY:
            args['y'] = event.y
        if event.value_mask & Xlib.X.CWWidth:
            args['width'] = event.width
        if event.value_mask & Xlib.X.CWHeight:
            args['height'] = event.height
        if event.value_mask & Xlib.X.CWSibling:
            args['sibling'] = event.above
        if event.value_mask & Xlib.X.CWStackMode:
            args['stack_mode'] = event.stack_mode
        window.configure(**args)

    def handle_configure_notify(self, event):
        pass

    def handle_map_request(self, event):
        event.window.map()
        screen = self.display.screen(0) # TODO This will always map new windows on the left monitor... not good!
        self.capture_window(screen, event.window)

    def handle_map_notify(self, event):
        pass

    # TODO: Why?
    def handle_mapping_notify(self, event):
        self.display.refresh_keyboard_mapping(event)

    def handle_unmap_notify(self, event):
        window = event.window
        print('Unmapping window {0}/{1}... '.format(window.owner, window.id), end="")
        
        if window not in self.windows.values():
            print("Not Framed")
            return

        screen = self.display.screen(0) # TODO This won't work if there are more than one monitor... not good!
        frame = event.event
        self.release_window(screen, frame)

    def handle_reparent_notify(self, event):
        pass

    def handle_client_message(self, event):
        pass

    def handle_mouse_motion(self, event):
        '''
        Right click & drag to move window.
        '''
        if event.state & Xlib.X.Button3MotionMask:
            if self.drag_window is None:
                # Start right-drag
                self.drag_window = event.window
                g = self.drag_window.get_geometry()
                self.drag_offset = g.x - event.root_x, g.y - event.root_y
            else:
                # Continue right-drag
                x, y = self.drag_offset
                self.drag_window.configure(x=x + event.root_x, y=y + event.root_y)

    def handle_mouse_press(self, event):
        if event.detail == 3:
            # Right-click: raise window
            event.window.configure(stack_mode=Xlib.X.Above)

    def handle_mouse_release(self, event):
        self.drag_window = None

    def handle_key_press(self, event):
        if event.state & Xlib.X.Mod1Mask and event.detail in self.enter_codes:
            print('Spawning terminal')
            utils.system(['/usr/bin/alacritty'])
        elif event.state & Xlib.X.Mod1Mask and event.detail in self.A_Q_codes:
            self.ShouldQuit = True
        elif event.state & Xlib.X.Mod1Mask and event.detail in self.A_C_codes:
            self.capture_all_windows()
        elif event.state & Xlib.X.Mod1Mask and event.detail in self.A_R_codes:
            self.release_all_windows()
        else:
            print("Key pressed but not handled:", event.state, Xlib.XK.keysym_to_string(self.display.keycode_to_keysym(event.detail, 2)))

    def handle_key_release(self, event):
        pass

