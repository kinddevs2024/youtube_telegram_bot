# Server deployment

This project runs separately from the Logic Coin services.

- Root: `/srv/apps/youtube-telegram-bot`
- Source: `current` -> `releases/dd8a9b5-deploy-20261109`
- Python environment: `venv`
- Unit: `youtube-telegram-bot.service`
- Secret: `shared/bot.env`, owned by root, mode 0600. Never commit its contents.
- Service account: `youtube-bot`, without a login shell.
- Runtime files: `/var/lib/youtube-telegram-bot`
- Temporary downloads: `/var/cache/youtube-telegram-bot`, cleaned after each request.

The service polls Telegram, so no public HTTP port or domain is required. It
starts after networking, restarts on failure, and is enabled at boot. The unit
limits memory to 1 GiB and CPU to one core, and protects the system filesystem.
FFmpeg and Node.js are installed on the server. The Python requirements include
yt-dlp's default dependencies and JavaScript challenge support; Node is selected
explicitly as the JavaScript runtime.

The hosted Telegram Bot API permits uploads up to 50 MB. This deployment uses a
49 MiB limit and asks the user to choose a lower quality for larger results.
Sending files of about 1 GB would require a separate local Telegram Bot API
server, which is not part of this deployment.

Administration:

```sh
sudo systemctl status youtube-telegram-bot --no-pager
sudo systemctl restart youtube-telegram-bot
sudo journalctl -u youtube-telegram-bot --since '10 minutes ago' --no-pager
```

For an update, put reviewed source in a new release directory, install its
requirements into the virtual environment, change the `current` symlink, then
restart this unit. Keep the secret file outside release directories. Do not
print the token or use it in command-line arguments.

On November 9, Telegram authentication passed for
`@ozone_school_dowlorder_bot`, with no webhook configured. The download probe
for `jNQXAC9IVRw` failed because YouTube requested sign-in to confirm the server
was not a bot. Running the service does not resolve that upstream restriction.
Provide a Netscape-format cookie file from an authorized YouTube session through
a secure file transfer. Install it as
`shared/youtube-cookies.txt` with owner `root:youtube-bot`, mode 0640, and set
`YOUTUBE_COOKIES_FILE=/srv/apps/youtube-telegram-bot/shared/youtube-cookies.txt`
in the protected `shared/bot.env`. Restart the unit and repeat the download
check. The shared directory permits only root and the service group to traverse
it; the bot token file remains root-only. yt-dlp receives a temporary private
copy of cookies so the source secret need not be writable. Cookies can expire;
never commit or log them.

Validation records are stored under `diagnostics/20261109` on the server.

## Temporary HTTPS session setup (November 9)

The temporary `youtube-bot-setup.service` serves the upload UI only on
`127.0.0.1:8794`. An nginx location include exposes it under
`/youtube-bot-setup/` on the canonical HTTPS domain. A random, unguessable URL
is stored only in root-readable `diagnostics/20261109/setup-link.txt`; it is
never committed. Its expiration is recorded in `cookie-setup-meta.json`.
The URL expires two hours after creation and permits one valid upload.
The helper service stops after 7,500 seconds and is not enabled at boot.

Upload requirements: an active YouTube session in Netscape format, up to 1 MiB.
The receiver validates its syntax, discards cookies for every other site and
expired cookies, then atomically stores a 0600 file at
`/var/lib/youtube-bot-setup/youtube-cookies.txt` inside a 0700 directory owned
by `youtube-bot`. It never provides cookie readback. Invalid capability URLs,
wrong origins, guest-only sessions and subsequent uploads are rejected.
Access logs for the endpoint are disabled; responses are not cached, and
referrers include only the origin, never the capability URL path. Chrome sends
a null Origin on form submissions under `no-referrer`, so `strict-origin` is
required for the strict form Origin check to work.

The protected bot environment now points `YOUTUBE_COOKIES_FILE` to that
private file. The bot uses anonymous requests while it is absent and picks up
the uploaded session on the next download without another restart. File receipt
does not establish that YouTube authentication/download succeeds: rerun the
short-video download probe as `youtube-bot` after the user's upload and inspect
only the pass/fail result, never cookie contents. If authentication still fails,
a new session or authorized network connection may be needed.

The upload page contains the Chrome export steps from the upstream yt-dlp
YouTube cookie guide. Keep the capability URL and cookie file out of chat logs,
Git and general access logs. It is acceptable to share the private setup link
with the authorized owner; never share the uploaded cookies. After completion,
remove `/etc/nginx/youtube-bot-setup.location`'s include from the canonical
HTTPS server block, validate nginx, reload it and stop the helper unit. Retain
the private cookie file for the bot; the upload URL's expiry does not revoke
the YouTube session.

Validation: four standard-library tests cover cookie filtering, expiry/guest
rejection, capability protection, cross-origin rejection, single upload,
no readback and private file permissions. A Chromium form upload with entirely
synthetic cookies passed. Public HTTPS GET, invalid URL rejection and Logic Coin
API health were also checked. No real YouTube cookies have been supplied yet.
