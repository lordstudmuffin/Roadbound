# Roadbound Quest Log

A co-op real-life road trip game for two. An installable web app: open the site on a phone and add it to the home screen.

- `index.html`, `manifest.webmanifest`, `sw.js`, `icon-*.png`: the app, served as-is.
- `quests/`: one JSON file per quest, listed in `quests/index.json`. Adding a quest means adding a file and its id to the index.
- `src/roadbound.html` and `src/build_app.py`: the page source and the script that builds `index.html`, the manifest and the service worker from it (`python3 src/build_app.py src/roadbound.html .`).

- `config.js`: the address and public key of the shared-journal database. Leave both blank to run without syncing.
- `supabase-setup.sql`: one-time database setup, pasted into the Supabase SQL Editor.

The journal (party, progress, photos) is stored on the phone and, once two phones are linked, in the database under a private journal code. It is never in this repository.
