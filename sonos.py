#!/usr/bin/env python3

import os
import json
import soco
import logging
import datetime
import argparse
from soco.compat import urlparse
from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.layout.screen import Point
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.widgets import Dialog, Button
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FloatContainer, Float
from prompt_toolkit.layout.controls import FormattedTextControl
from soco.data_structures import to_didl_string, DidlMusicTrack
from prompt_toolkit.layout.containers import HSplit, Window, FloatContainer

def get_coordinators():
    return (zp for zp in soco.discover() if zp.is_coordinator)

def silence(zp_name):
    for zp in soco.discover():
        if zp.player_name == zp_name:
            logging.info("silencing {}".format(zp_name))
            zp.volume = 0
            zp.mute = True


def enqueue_playlist(zp, playlist_path):
    with open(playlist_path, "rb") as f:
        playlist = json.loads(f.read())

    logging.info(playlist[0])

    for track in playlist:
        uri = track['resources'][0]['uri']
        # don't know what this is. DO know that it is required if we want proper title/artist info in Sonos Queue.
        desc = 'SA_RINCON3079_X_'

        # Now we need to create a DIDL item id. It seems to be based on the uri
        path = urlparse(uri).path
        # Strip any extensions, eg .mp3, from the end of the path
        path = path.rsplit('.', 1)[0]
        # The ID has an 8 (hex) digit prefix. But it doesn't seem to matter what it is!
        track_id = '08675309{0}'.format(path)

        didl = DidlMusicTrack(
            item_id=track_id,
            parent_id=track['parent_id'],
            title=track['title'],
            # whatever TF this is, if it's absent, enqueued items don't have title/creator metadata
            desc='SA_RINCON3079_X_'
        )

        # have to do this all at a low, API-subverting level so that we can stuff the all important magic "desc" field in there.

        zp.avTransport.AddURIToQueue([
            ('InstanceID', 0),
            ('EnqueuedURI', uri),
            ('EnqueuedURIMetaData', to_didl_string(didl)),
            ('DesiredFirstTrackNumberEnqueued', 0),
            ('EnqueueAsNext', 1)
        ])

def dump_playlists(zps, playlists_dir):
    for zp in zps:
        for playlist in zp.get_sonos_playlists():
            zpname = zp.get_speaker_info()['zone_name']
            path = "{}/{}.{}.json".format(playlists_dir, zpname, playlist.title)

            logging.info(playlist.title)

            tracks = [ track.to_dict() for track in zp.music_library.browse(playlist) ]

            with open(path, "wb") as f:
                f.write(json.dumps(tracks).encode('utf-8'))

def dump_queue(zps, playlists_dir):
    for zp in zps:
        timestamp = datetime.datetime.today().strftime("%Y%m%d%H%M%S")
        zpname = zp.get_speaker_info()['zone_name']
        path = "{}/queue.{}.{}.json".format(playlists_dir, zpname, timestamp)

        tracks = [ item.to_dict() for item in zp.get_queue(max_items=99999) ]

        with open(path, "wb") as f:
            f.write(json.dumps(tracks).encode('utf-8'))

class OKDialog(Dialog):
    def __init__(self, title='OK', body='Dialog', button_text='OK', buttons=None, width=None):
        self.app = get_app()

        if buttons is None:
            buttons = [Button(text=button_text, handler=self.button_handler),]

        super().__init__(title=title, body=Window(content=FormattedTextControl(text=ANSI(body))), buttons=buttons, width=width)

    def button_handler(self):
        self.app.layout.container.floats.pop()
        self.app.layout.focus(self.app.layout.container.content.children[0])

    def display(self):
        self.app.layout.container.floats.append(Float(content=self))
        self.app.layout.focus(self)

class ConfirmationDialog(OKDialog):
    def __init__(self, title='Yes/No?', body='Dialog', yes_callback=None):
        self.yes_callback = yes_callback

        super().__init__(title,
                         body,
                         buttons=[Button(text='No', handler=self.no_handler), Button(text='Yes', handler=self.yes_handler)])

    def yes_handler(self):
        if self.yes_callback:
            self.yes_callback()
        super().button_handler()

    def no_handler(self):
        super().button_handler()

class CheesyPicker(OKDialog):
    def __init__(self, title='Pick One', choices=('Pepperoni', 'Mushrooms', 'Plain Cheese'), handler=None):
        self.handler = handler
        body = "\n".join("{}) {}".format(chr(ord('a') + idx), choice) for idx, choice in enumerate(choices))
        buttons = [ Button(text="{}".format(chr(ord('a') + idx)), handler=lambda: self.root_handler(choice)) for idx, choice in enumerate(choices) ]

        super().__init__(title, body, buttons=buttons)

    def root_handler(self, choice):
        logging.info("choice: %s", choice)
        super().button_handler()
        if self.handler is not None:
            self.handler(choice)

class BrowserControl(FormattedTextControl):
    def __init__(self, root_path):
        self.root_path = root_path
        self.path_stack = [self.root_path,]
        self.cursor_position = Point(0,0)
        self.cursor_stack = [self.cursor_position.y,]
        self.the_list = []

        self.fetch_list()
        super().__init__(text=self.text, get_cursor_position=lambda: self.cursor_position, key_bindings=self.build_key_bindings())

    def fetch_list(self):
        path = self.path_stack[-1]
        if os.path.isdir(path):
            self.the_list = list(reversed(sorted(os.listdir(path))))
        else:
            try:
                with open(path, "rb") as f:
                    playlist = json.loads(f.read())
                    logging.info(playlist[0])
                    self.the_list = [ "{} : {} : {}".format(t['creator'], t['album'], t['title']) for t in playlist ]
            except FileNotFoundError as e:
                return False

        return True

    def text(self):
        def decorate(item, idx):
            if idx == self.cursor_position.y:
                ansi0, ansi1 = '\x1b[7m', '\x1b[0m'
            else:
                ansi0, ansi1 = '', ''

            return " {idx:>3} {ansi0}{item}{ansi1}".format(idx=idx+1, ansi0=ansi0, ansi1=ansi1, item=item)

        return ANSI("\n".join(decorate(item, idx) for idx, item in enumerate(self.the_list)))

    def adjust_cursor_position(self, x=None, y=None):
        if y is not None:
            if y < len(self.the_list):
                self.cursor_position = Point(0, y)
        if len(self.the_list) == 0:
            self.cursor_position = Point(0, 0)
        elif self.cursor_position.y >= len(self.the_list):
            self.cursor_position = Point(0, len(self.the_list)-1)

    def build_key_bindings(self):
        kb = KeyBindings()

        @kb.add('down')
        def _(event):
            new_y = self.cursor_position.y + 1

            if new_y < len(self.the_list):
                self.adjust_cursor_position(y=new_y)

        @kb.add('up')
        def _(event):
            new_y = self.cursor_position.y - 1
            if new_y >= 0:
                self.adjust_cursor_position(y=new_y)

        @kb.add('left')
        def _(event):
            if len(self.path_stack) > 1:
                self.path_stack.pop()
                self.fetch_list()
                pos = self.cursor_stack.pop()
                self.adjust_cursor_position(y=pos)

        @kb.add('c-f')
        def _(event):
            w = event.app.layout.current_window

            if w and w.render_info:
                line_index = max(w.render_info.last_visible_line(), w.vertical_scroll + 1)
                self.adjust_cursor_position(y=line_index)
                w.vertical_scroll = line_index

        @kb.add('c-b')
        def _(event):
            w = event.app.layout.current_window

            if w and w.render_info:
                line_index = max(0, self.cursor_position.y-w.render_info.window_height+1)
                self.adjust_cursor_position(y=line_index)

        @kb.add('c-a')
        def _(event):
            self.adjust_cursor_position(y=0)

        @kb.add('c-z')
        def _(event):
            w = event.app.layout.current_window

            if w and w.render_info:
                line_index = len(self.the_list)-1
                self.adjust_cursor_position(y=line_index)
                w.vertical_scroll = line_index

        @kb.add('space')
        def _(event):
            path = os.path.join(self.root_path, self.the_list[self.cursor_position.y])
            self.path_stack.append(path)
            if self.fetch_list():
                self.cursor_stack.append(self.cursor_position.y)
                self.adjust_cursor_position(y=0)
            else:
                self.path_stack.pop()

        @kb.add('e')
        def _(event):
            path = os.path.join(*self.path_stack)
            if os.path.isdir(path):
                path = os.path.join(path, self.the_list[self.cursor_position.y])

            def confirm(zp):
                ConfirmationDialog(title="Enqueue Playlist?",
                                   body="Enqueue Playlist '{}' to '{}'?".format(os.path.basename(path), zp.get_speaker_info()['zone_name']),
                                   yes_callback=lambda: enqueue_playlist(zp, path),
                ).display()

            coordinators = list(get_coordinators())
            if len(coordinators) > 1:
                coordinator_names = [ zp.get_speaker_info()['zone_name'] for zp in coordinators ]
                CheesyPicker(title='Enqueue to Which Coordinator?',
                             choices=coordinator_names,
                             handler=confirm).display()
            else:
                confirm(coordinators[0])

        return kb

def build_key_bindings():
    kb = KeyBindings()

    @kb.add('q')
    def _(event):
        event.app.exit()

    @kb.add('?')
    @kb.add('h')
    def _(event):
        HelpDialog().display()

    return kb

def make_app(playlists_dir):
    def status_bar_text():
        name = browser_control.path_stack[-1]
        if name.endswith('.json'):
            try:
                zpname, ts = os.path.basename(name).split('.')[1:-1]
                y, mo, d, h, mi, s = ts[0:4], ts[4:6], ts[6:8], ts[8:10], ts[10:12], ts[12:14]
                name = "{} : {}/{}/{} {}:{}".format(zpname, y, mo, d, h, mi, s)
            except ValueError:
                name = os.path.basename(name)

        return "{name} : 'q': quit | <up>/<down> moves | <space> selects | 'e' enqueues".format(name=name)

    browser_control = BrowserControl(playlists_dir)
    listview_window = Window(browser_control)
    status_bar_window = Window(content=FormattedTextControl(status_bar_text), height=1, style='reverse')

    root_container = FloatContainer(
        content=HSplit([
            listview_window,
            status_bar_window,
        ]),
        floats=[
        ],
    )

    return Application(layout=Layout(root_container), full_screen=True, key_bindings=build_key_bindings())

def ui(playlists_dir):
    make_app(playlists_dir).run()

if __name__ == "__main__":
    logging.basicConfig(filename='sonos.log', level=logging.INFO)

    # FIXME: this would be much nicer with sub-parsers
    #
    parser = argparse.ArgumentParser(description='SONOS queue and playlist manipulation.')
    parser.add_argument('command', action='store', type=str,
                        choices=['dump-playlists', 'dump-queue', 'silence', 'ui', ],
                        help='what to do')
    parser.add_argument('path_or_zp', action='store', type=str,
                        help='path to directory for playlist/queue dump, or ZP to silence')

    args = parser.parse_args()

    if args.command != 'silence' and not os.path.exists(args.path_or_zp):
        parser.exit(2, "ERROR: path {} not found\n".format(args.path_or_zp))

    if args.command == 'dump-playlists':
        dump_playlists(get_coordinators(), args.path_or_zp)
    elif args.command == 'dump-queue':
        dump_queue(get_coordinators(), args.path_or_zp)
    elif args.command == 'silence':
        silence(args.path_or_zp)
    elif args.command == 'ui':
        ui(args.path_or_zp)

    parser.exit(0)

# TODO :
#   - works for multi-level subdirs (os.path.join(root_path, x) makes assumption of 1-level depth)
#   - make 'enqueue' really fast, why is it so slow?
#   - works in mac terminal - for Bryan
#   - proper README