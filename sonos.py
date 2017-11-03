import soco
import soco.data_structures
import json
import datetime
import argparse
import os

def get_coordinator():
    zps = soco.discover()

    # print(dir(list(zps)[0]))
    return next(zp for zp in zps if zp.is_coordinator)

def make_playlists_dir():
    try:
        os.makedirs('./playlists')
    except OSError:
        pass

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

def dump_playlists(zp):
    for playlist in zp.get_sonos_playlists():
        print(playlist.title)

        tracks = [ track.to_dict() for track in zp.music_library.browse(playlist) ]

        with open("playlists/{}.json".format(playlist.title), "wb") as f:
            f.write(json.dumps(tracks))

def dump_queue(zp):
    timestamp = datetime.datetime.today().strftime("%Y%m%d%H%M%S")
    tracks = [ item.to_dict() for item in zp.get_queue() ]

    with open("playlists/queue.{}.json".format(timestamp), "wb") as f:
        f.write(json.dumps(tracks))

if __name__ == "__main__":
    # FIXME: this would be much nicer with sub-parsers
    #
    parser = argparse.ArgumentParser(description='SONOS queue and playlist manipulation.')
    parser.add_argument('command', action='store', type=str, choices=['dump-playlists', 'dump-queue', 'enqueue'],
                        help='what to do')
    parser.add_argument('--path', action='store', type=str, default=None,
                        help='path to playlist to enqueue')

    args = parser.parse_args()

    if args.command == 'dump-playlists':
        make_playlists_dir()
        dump_playlists(get_coordinator())
    elif args.command == 'dump-queue':
        make_playlists_dir()
        dump_queue(get_coordinator())
    elif args.command == 'enqueue':
        if args.path is None:
            parser.exit(1, "ERROR: enqueue command requires --path\n")
        elif not os.path.exists(args.path):
            parser.exit(2, "ERROR: path {} not found\n".format(args.path))

        enqueue_playlist(get_coordinator(), args.path)

    parser.exit(0)