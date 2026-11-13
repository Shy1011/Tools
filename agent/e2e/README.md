# End-to-end checks

Start a local static server before running browser scripts:

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

The scripts in this directory use the `ego-browser` helper available in this
workspace:

- `round-01.mjs`: broad in-page API check covering curves, view, style, markers,
  cursors, cleanup, statistics, save/load and CSV import.
- `round-08.mjs`: verifies Agent state isolation from the normal localStorage.
- `round-09.mjs`: checks remaining patch/update/error paths, erase and reset.
- `round-10.mjs`: confirms the visible UI and example button still work.

Run an individual round with:

```powershell
ego-browser nodejs -e "await import('file:///C:/Users/thesh/Documents/GitHub/Tools/agent/e2e/round-01.mjs')"
```

For the local HTTP and real Edge round trip:

```powershell
python agent/e2e/http_round_trip.py
```

That test launches Edge, calls the bridge, exports PNG/CSV/XLSX, verifies the
XLSX parts and image, then imports the XLSX back into the page.
