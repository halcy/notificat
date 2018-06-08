# notificat.py

Prints mastodon webpushes to console

For now, adjust settings in the script file. Password is prompted on first login. Argument parsing and all that Soon.

Can either subscribe via mozillas autopush servers, or directly.

Note that to run in direct mode, your computer needs to have at least port 80 open to the world and available for use by this script, a domain name that other computers can resolve, and letsencrypts certbot-auto installed, so that maybe isn't super practical. In mozilla autopush mode, everything should Just Work.
