#!/usr/bin/env python3

import os
import json
import soco
import logging
import datetime
import argparse
import soco.data_structures
from prompt_toolkit import Application
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.layout.screen import Point
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import HSplit, Window, FloatContainer

def get_coordinators():
    return (zp for zp in soco.discover() if zp.is_coordinator and len(zp.get_queue()))

def silence(zp_name):
    for zp in soco.discover():
        if zp.player_name == zp_name:
            print("silencing {}".format(zp_name))
            zp.volume = 0
            zp.mute = True


def enqueue_playlist(zp, playlist_path):
    with open(playlist_path, "rb") as f:
        playlist = json.loads(f.read())

    print(playlist[0])

    for track in playlist:
        uri = track['resources'][0]['uri']
        title = track['title']
        item_id = track['item_id']
        parent_id = track['parent_id']

        res = [soco.data_structures.DidlResource(uri=uri, protocol_info="x-rincon-playlist:*:*:*")]
        item = soco.data_structures.DidlObject(resources=res, title=title, parent_id=parent_id, item_id=item_id)

        zp.add_to_queue(item)

def dump_playlists(zps, playlists_dir):
    for zp in zps:
        for playlist in zp.get_sonos_playlists():
            zpname = zp.get_speaker_info()['zone_name']
            path = "{}/{}.{}.json".format(playlists_dir, zpname, playlist.title)

            print(playlist.title)

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

            return " {idx:>3} {ansi0}{item}{ansi1}".format(idx=idx, ansi0=ansi0, ansi1=ansi1, item=item)

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
                line_index = len(self.lines())-1
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
        name = "Yabba Dabba Doo"
        return "{name} : 'q': quit | 'z': undo | '?' help | <up>/<down> moves | <space> toggles".format(name=name)

    listview_window = Window(BrowserControl(playlists_dir))
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
    logging.basicConfig(filename='sonos.log', level=logging.DEBUG)

    # FIXME: this would be much nicer with sub-parsers
    #
    parser = argparse.ArgumentParser(description='SONOS queue and playlist manipulation.')
    parser.add_argument('command', action='store', type=str,
                        choices=['dump-playlists', 'dump-queue', 'enqueue', 'silence', 'ui', ],
                        help='what to do')
    parser.add_argument('path_or_zp', action='store', type=str,
                        help='path to playlist to enqueue, or path to directory for playlist/queue dump, or ZP to silence')

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
