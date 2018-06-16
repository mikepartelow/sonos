import soco
import soco.data_structures
import json
import datetime
import argparse
import os

def get_coordinator():
    zps = soco.discover()

    # print(dir(list(zps)[0]))
    return next(zp for zp in zps if zp.is_coordinator and len(zp.get_queue()))

def silence(zp_name):
    zps = soco.discover()

    for zp in zps:
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

def dump_playlists(zp, playlists_dir):
    for playlist in zp.get_sonos_playlists():
        print(playlist.title)

        tracks = [ track.to_dict() for track in zp.music_library.browse(playlist) ]

        with open("{}/{}.json".format(playlists_dir, playlist.title), "wb") as f:
            f.write(json.dumps(tracks))

def dump_queue(zp, playlists_dir):
    timestamp = datetime.datetime.today().strftime("%Y%m%d%H%M%S")
    tracks = [ item.to_dict() for item in zp.get_queue(max_items=99999) ]

    with open("{}/queue.{}.json".format(playlists_dir, timestamp), "wb") as f:
        f.write(json.dumps(tracks))

if __name__ == "__main__":
    # FIXME: this would be much nicer with sub-parsers
    #
    parser = argparse.ArgumentParser(description='SONOS queue and playlist manipulation.')
    parser.add_argument('command', action='store', type=str,
                        choices=['dump-playlists', 'dump-queue', 'enqueue', 'silence'],
                        help='what to do')
    parser.add_argument('path_or_zp', action='store', type=str,
                        help='path to playlist to enqueue, or path to directory for playlist/queue dump, or ZP to silence')

    args = parser.parse_args()

    if args.command != 'silence' and not os.path.exists(args.path_or_zp):
        parser.exit(2, "ERROR: path {} not found\n".format(args.path_or_zp))

    if args.command == 'dump-playlists':
        dump_playlists(get_coordinator(), args.path_or_zp)
    elif args.command == 'dump-queue':
        dump_queue(get_coordinator(), args.path_or_zp)
    elif args.command == 'enqueue':
        enqueue_playlist(get_coordinator(), args.path_or_zp)
    elif args.command == 'silence':
        silence(args.path_or_zp)

    parser.exit(0)
