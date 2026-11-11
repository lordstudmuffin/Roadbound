# Roadbound Quest Log

A co-op real-life road trip game for two. An installable web app: open the site on a phone and add it to the home screen.

- `index.html`, `manifest.webmanifest`, `sw.js`, `icon-*.png`: the app, served as-is.
- `quests/`: one JSON file per quest, listed in `quests/index.json`. Adding a quest means adding a file and its id to the index.
- `src/roadbound.html` and `src/build_app.py`: the page source and the script that builds `index.html`, the manifest and the service worker from it (`python3 src/build_app.py src/roadbound.html .`).

The journal (party, progress, photos) is stored on the phone, never in this repository.
