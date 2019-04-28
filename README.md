# sonos
command line utility suite for managing Sonos speakers

- cron-friendly "mute" operation. forget worrying whether you left the outdoor speakers on overnight
- cron-friendly "queue backup" operation. "Sonos Playlists" feature is extremely limited, and Sonos frequently loses
  the queue (power outage, accidental ungrouping, etc). Back up the whole queue from the commandline or cron.
- UI backup browser/restorer. Browse your queue backups and restore them to any controller in your Sonos system.

May require this patch to Soco lib: https://github.com/SoCo/SoCo/issues/660
