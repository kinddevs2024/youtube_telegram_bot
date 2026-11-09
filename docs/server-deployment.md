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
