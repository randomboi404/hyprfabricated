from os import truncate
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.button import Button
from fabric.widgets.stack import Stack
from fabric.widgets.revealer import Revealer
from fabric.widgets.wayland import WaylandWindow as Window
from fabric.hyprland.widgets import ActiveWindow
from fabric.utils.helpers import FormattedString, truncate
from gi.repository import GLib, Gdk, Gtk
from modules.launcher import AppLauncher
from modules.dashboard import Dashboard
from modules.notifications import NotificationContainer
from modules.power import PowerMenu
from modules.overview import Overview
from modules.bluetooth import BluetoothConnections
from modules.corners import MyCorner
import modules.icons as icons
import modules.data as data
from modules.player import PlayerSmall
from modules.tools import Toolbox
import json

class Notch(Window):
    def __init__(self, **kwargs):
        super().__init__(
            name="notch",
            layer="top",
            anchor="top",
            margin="-40px 40px 10px 10px",
            keyboard_mode="none",
            exclusivity="normal",
            visible=True,
            all_visible=True,
        )

        self.bar = kwargs.get("bar", None)

        # Primero inicializamos NotificationContainer
        self.notification = NotificationContainer(notch=self)
        self.notification_history = self.notification.history

        # Luego inicializamos el resto de componentes que dependen de notification_history
        self.dashboard = Dashboard(notch=self)
        self.launcher = AppLauncher(notch=self)
        self.overview = Overview()
        self.power = PowerMenu(notch=self)
        self.tools = Toolbox(notch=self)
        self.bluetooth = BluetoothConnections(notch=self)

        self.active_window = ActiveWindow(
            name="hyprland-window",
            h_expand=True,
            formatter=FormattedString(
                f"{{'Desktop' if not win_title or win_title == 'unknown' else truncate(win_title, 32)}}",
                truncate=truncate,

            ),
        )
        # Add the click connection for active_window.
        self.active_window.connect("button-press-event", lambda widget, event: (self.open_notch("dashboard"), False)[1])

        # Create additional compact views:
        self.player_small = PlayerSmall()
        self.user_label = Label(name="compact-user", label=f"{data.USERNAME}@{data.HOSTNAME}")
        self.window_title_icon = Label(name="icon-label", markup=icons.desktop)
        self.window_title = Box(
            h_align="center",
            v_align="center",
            children=[
                self.window_title_icon,
                self.active_window,
            ]
        )

        self.player_small.mpris_manager.connect("player-appeared", lambda *_: self.compact_stack.set_visible_child(self.player_small))
        self.player_small.mpris_manager.connect("player-vanished", self.on_player_vanished)
        # Create a stack to hold the three views:
        self.compact_stack = Stack(
            name="notch-compact-stack",
            v_expand=True,
            h_expand=True,
            transition_type="slide-up-down",
            transition_duration=100,
            children=[
                self.user_label,
                self.window_title,
                self.player_small,
            ]
        )
        self.compact_stack.set_visible_child(self.window_title)

        self.active_window.connection.connect("event::activewindow", self.update_window_title)

        # Create the compact button and set the stack as its child
        self.compact = Gtk.EventBox(name="notch-compact")
        self.compact.set_visible(True)
        self.compact.add(self.compact_stack)
        # Se agrega el mask de smooth scroll junto a scroll y button press.
        self.compact.add_events(
            Gdk.EventMask.SCROLL_MASK |
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.SMOOTH_SCROLL_MASK
        )
        self.compact.connect("scroll-event", self._on_compact_scroll)
        self.compact.connect("button-press-event", lambda widget, event: (self.open_notch("dashboard"), False)[1])
        # Add cursor change on hover.
        self.compact.connect("enter-notify-event", self.on_button_enter)
        self.compact.connect("leave-notify-event", self.on_button_leave)

        self.tools = Toolbox(notch=self)
        self.stack = Stack(
            name="notch-content",
            v_expand=True,
            h_expand=True,
            transition_type="crossfade",
            transition_duration=100,
            children=[
                self.compact,
                self.launcher,
                self.dashboard,
                self.overview,
                self.power,
                self.tools,
                self.bluetooth,
                self.tools,
            ]
        )

        self.corner_left = Box(
            name="notch-corner-left",
            orientation="v",
            children=[
                MyCorner("top-right"),
                Box(),
            ]
        )

        self.corner_right = Box(
            name="notch-corner-right",
            orientation="v",
            children=[
                MyCorner("top-left"),
                Box(),
            ]
        )

        self.notch_box = CenterBox(
            name="notch-box",
            orientation="h",
            h_align="center",
            v_align="center",
            start_children=Box(
                children=[
                    self.corner_left,
                ],
            ),
            center_children=self.stack,
            end_children=Box(
                children=[
                    self.corner_right,
                ]
            )
        )
        self._scroll_accumulator = 0.0
        self.hidden = False
        self.scroll_threshold = 15.0  # Ajusta este valor para modificar la sensibilidad
        self._scrolling = False
        self.notification_revealer = Revealer(
            name="notification-revealer",
            transition_type="slide-down",
            transition_duration=250,
            child_revealed=False,
        )

        self.boxed_notification_revealer = Box(
            name="boxed-notification-revealer",
            orientation="v",
            children=[
                self.notification_revealer,
            ]
        )

        self.notch_complete = Box(
            name="notch-complete",
            orientation="v",
            children=[
                self.notch_box,
                self.boxed_notification_revealer,
            ]
        )

        self.hidden = False

        self._scrolling = False

        self.add(self.notch_box)
        self.add(self.notch_complete)
        self.show_all()

        self.add_keybinding("Escape", lambda *_: self.close_notch())
        self.add_keybinding("Ctrl Tab", lambda *_: self.dashboard.go_to_next_child())
        self.add_keybinding("Ctrl Shift ISO_Left_Tab", lambda *_: self.dashboard.go_to_previous_child())

    def update_window_title(self, *args):
        win_data: dict = json.loads(
            self.active_window.connection.send_command("j/activewindow").reply.decode()
        )
        win_class = win_data.get("class", "unknown")
        win_title = win_data.get("title", win_class)
        icon = icons.get_class_icon(win_class)
        self.window_title_icon.set_markup(icon)

    def on_button_enter(self, widget, event):
        window = widget.get_window()
        if window:
            window.set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2))

    def on_button_leave(self, widget, event):
        window = widget.get_window()
        if window:
            window.set_cursor(None)

    def close_notch(self):
        self.set_keyboard_mode("none")

        self.bar.revealer.set_reveal_child(True)

        if self.hidden:
            self.notch_box.remove_style_class("hideshow")
            self.notch_box.add_style_class("hidden")

        for widget in [self.launcher, self.dashboard, self.notification, self.overview, self.power, self.bluetooth, self.tools]:
            widget.remove_style_class("open")
        for style in ["launcher", "dashboard", "notification", "overview", "power", "bluetooth", "tools"]:
            self.stack.remove_style_class(style)
        self.stack.set_visible_child(self.compact)

    def open_notch(self, widget):
        self.set_keyboard_mode("exclusive")

        if self.hidden:
            self.notch_box.remove_style_class("hidden")
            self.notch_box.add_style_class("hideshow")

        widgets = {
            "launcher": self.launcher,
            "dashboard": self.dashboard,
            "overview": self.overview,
            "power": self.power,
            "bluetooth": self.bluetooth,
            "tools": self.tools,

        }

        # Limpiar clases y estados previos
        for style in widgets.keys():
            self.stack.remove_style_class(style)
        for w in widgets.values():
            w.remove_style_class("open")

        # Configurar según el widget solicitado
        if widget in widgets:
            self.stack.add_style_class(widget)
            self.stack.set_visible_child(widgets[widget])
            widgets[widget].add_style_class("open")

            # Acciones específicas para el launcher
            if widget == "launcher":
                self.launcher.open_launcher()
                self.launcher.search_entry.set_text("")
                self.launcher.search_entry.grab_focus()

            if widget == "notification":
                self.set_keyboard_mode("none")

            if widget == "dashboard" and self.dashboard.stack.get_visible_child() != self.dashboard.stack.get_children()[4]:
                self.dashboard.stack.set_visible_child(self.dashboard.stack.get_children()[0])
        else:
            self.stack.set_visible_child(self.dashboard)

        if widget == "dashboard" or widget == "overview":
            self.bar.revealer.set_reveal_child(False)
        else:
            self.bar.revealer.set_reveal_child(True)

    def toggle_hidden(self):
        self.hidden = not self.hidden
        if self.hidden:
            self.notch_box.add_style_class("hidden")
        else:
            self.notch_box.remove_style_class("hidden")
    def _on_compact_scroll(self, widget, event):
        if self._scrolling:
            return True

        children = self.compact_stack.get_children()
        current = children.index(self.compact_stack.get_visible_child())
        new_index = current

        if event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < -0.1:
                new_index = (current - 1) % len(children)
            elif event.delta_y > 0.1:
                new_index = (current + 1) % len(children)
            else:
                return False
        elif event.direction == Gdk.ScrollDirection.UP:
            new_index = (current - 1) % len(children)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            new_index = (current + 1) % len(children)
        else:
            return False

        self.compact_stack.set_visible_child(children[new_index])
        self._scrolling = True
        GLib.timeout_add(250, self._reset_scrolling)
        return True

    def _reset_scrolling(self):
        self._scrolling = False
        return False

    def on_player_vanished(self, *args):
        if self.player_small.mpris_label.get_label() == "Nothing Playing":
            self.compact_stack.set_visible_child(self.active_window)
