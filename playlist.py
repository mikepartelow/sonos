import soco
import soco.data_structures
import json
import datetime

def enqueue_playlist(zp, playlist_name):
    with open("playlists/{}.json".format(playlist_name), "rb") as f:
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
    zps = soco.discover()

    # print(dir(list(zps)[0]))
    zp = next(zp for zp in zps if zp.is_coordinator)

    dump_playlists(zp)
    dump_queue(zp)

    # enqueue_playlist(zp, 'Listen')