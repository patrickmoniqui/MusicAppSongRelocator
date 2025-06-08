import subprocess
import json
import tkinter as tk
from tkinter import filedialog
import os
from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from tkinter import Tk, filedialog, BooleanVar, Checkbutton, Button, Label, Entry
import csv

def get_missing_tracks():
    result = subprocess.run(
        ['osascript', 'get_missing_tracks.scpt'],
        capture_output=True, text=True
    )
    tracks = []
    for line in result.stdout.strip().splitlines():
        parts = line.split('\t')
        if len(parts) == 7:
            name, artist, album, duration, year, location, pid = parts
            try:
                duration = float(duration)
            except ValueError:
                duration = 0.0
            tracks.append({
                'title': name.strip(),
                'artist': artist.strip(),
                'album': album.strip(),
                'duration': duration,
                'year': year,
                'location': location.strip(),
                'persistent_id': pid
            })
    return tracks

def get_folder_and_match_fields_gui():
    result = {
        'folder': '',
        'recursive': True,
        'fields': {
            'artist': True,
            'album': True,
            'year': False,
            'duration': True
        }
    }

    def browse():
        path = filedialog.askdirectory()
        if path:
            path_var.set(path)

    def confirm():
        result['folder'] = path_var.get()
        result['recursive'] = recursive_var.get()
        result['fields']['artist'] = artist_var.get()
        result['fields']['album'] = album_var.get()
        result['fields']['year'] = year_var.get()
        result['fields']['duration'] = duration_var.get()
        window.destroy()

    window = tk.Tk()
    window.title("Search Setup")
    window.geometry("500x800")

    Label(window, text="Step 1: Select the folder to search in").pack(pady=(10, 5))
    path_var = tk.StringVar()
    Entry(window, textvariable=path_var, width=50).pack()
    Button(window, text="Browse...", command=browse).pack(pady=(5, 15))

    recursive_var = BooleanVar(value=True)
    Checkbutton(window, text="Search recursively", variable=recursive_var).pack()

    Label(window, text="\nStep 2: Choose which fields to match (title is always required)").pack(pady=(20, 5))

    artist_var = BooleanVar(value=True)
    album_var = BooleanVar(value=True)
    year_var = BooleanVar(value=False)
    duration_var = BooleanVar(value=True)

    Checkbutton(window, text="artist", variable=artist_var).pack(anchor="w", padx=40)
    Checkbutton(window, text="album", variable=album_var).pack(anchor="w", padx=40)
    Checkbutton(window, text="year", variable=year_var).pack(anchor="w", padx=40)
    Checkbutton(window, text="duration", variable=duration_var).pack(anchor="w", padx=40)

    Button(window, text="Start Search", command=confirm).pack(pady=20)

    window.mainloop()
    return result

def get_file_metadata(filepath):
    try:
        audio = MutagenFile(filepath, easy=True)
        if not audio or not audio.info:
            return None
        tags = audio.tags or {}

        return {
            'title': tags.get('title', [''])[0].strip(),
            'artist': tags.get('artist', [''])[0].strip(),
            'album': tags.get('album', [''])[0].strip(),
            'year': tags.get('date', ['0'])[0].strip().split("-")[0],
            'duration': round(audio.info.length, 2)
        }
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None
    
def is_match(track, file_meta, fields, max_duration_diff=1.5):
    if not file_meta:
        return False

    # Mandatory field
    if track['title'].lower() != file_meta['title'].lower():
        return False

    if fields.get('artist') and track['artist'].lower() != file_meta.get('artist', '').lower():
        return False

    if fields.get('album') and track['album'].lower() != file_meta.get('album', '').lower():
        return False

    if fields.get('year'):
        track_year = str(track.get('year', '')).strip()
        file_year = str(file_meta.get('year', '')).strip()
        if track_year and file_year and track_year != file_year:
            return False

    if fields.get('duration'):
        track_dur = round(track.get('duration', 0))
        file_dur = round(file_meta.get('duration', 0))
        if abs(track_dur - file_dur) > max_duration_diff:
            return False

    return True

def find_matches(track, folder, recursive=True):
    matched_files = []
    if recursive:
        walker = os.walk(folder)
    else:
        walker = [(folder, [], os.listdir(folder))]

    for root, _, files in walker:
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in [".mp3", ".m4a", ".flac", ".aac", ".wav"]:
                full_path = os.path.join(root, file)
                meta = get_file_metadata(full_path)
                if is_match(track, meta):
                    matched_files.append(full_path)
    return matched_files

def generate_search_string(track, fields):
    parts = [track['title'].lower()]  # title is always mandatory

    if fields.get('artist') and track['artist']:
        parts.append(track['artist'].lower())
    if fields.get('album') and track['album']:
        parts.append(track['album'].lower())
    if fields.get('year') and track.get('year'):
        parts.append(str(track['year']).lower())
    if fields.get('duration') and track.get('duration'):
        parts.append(f"{int(round(track['duration']))}")  # round to nearest sec

    return ' '.join(parts).strip()

def find_single_match(track, folder, fields, recursive=True):
    search_terms = generate_search_string(track, fields)
    matches = []

    if recursive:
        walker = os.walk(folder)
    else:
        walker = [(folder, [], os.listdir(folder))]

    for root, _, files in walker:
        for file in files:
            if not file.lower().endswith(('.mp3', '.m4a', '.flac', '.aac', '.wav')):
                continue
            if search_terms in file.lower():
                matches.append(os.path.join(root, file))

    return matches

def search_folder_with_metadata(track, folder, fields, recursive=True):
    query_parts = []

    # Title is always required
    query_parts.append(f'kMDItemTitle == "{track["title"]}"')

    if fields.get('artist') and track.get('artist'):
        query_parts.append(
        f'(kMDItemAuthors == "{track["artist"]}" || kMDItemArtist == "{track["artist"]}")')
    if fields.get('album') and track.get('album'):
        query_parts.append(f'kMDItemAlbum == "{track["album"]}"')
    if fields.get('year') and track.get('year'):
        query_parts.append(f'kMDItemRecordingYear == {track["year"]}')

    query = " && ".join(query_parts)

    try:
        result = subprocess.run(
            ['mdfind', '-onlyin', folder, query],
            capture_output=True, text=True
        )
        all_matches = result.stdout.strip().splitlines()

        if recursive:
            return all_matches
        else:
            # Filter to files directly inside `folder` (not subdirectories)
            direct_matches = [
                path for path in all_matches
                if os.path.dirname(path) == os.path.abspath(folder)
            ]
            return direct_matches

    except Exception as e:
        print(f"❌ Spotlight query failed: {e}")
        return []

def relink_track_by_pid(persistent_id, new_path):
    applescript = f'''
    on run {{thePersistentID, newPath}}
        try
            tell application "Music"
                set foundTrack to first file track of library playlist 1 whose persistent ID is thePersistentID
                set location of foundTrack to POSIX file newPath
            end tell
            return "success"
        on error errMsg
            return "error: " & errMsg
        end try
    end run
    '''

    result = subprocess.run(
        ['osascript', '-e', applescript, persistent_id, new_path],
        capture_output=True, text=True
    )

    output = result.stdout.strip().lower()
    if output == "success":
        return True
    else:
        print(f"❌ Failed to relink {persistent_id}: {output}")
        return False

def log_missing_tracks(missing_tracks, missing_log_path):
    with open(missing_log_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Title", "Artist", "Album", "Location", "Duration", "Persistent ID"])
        for track in missing_tracks:
            writer.writerow([
                track['title'],
                track['artist'],
                track['album'],
                track['location'],
                f"{track['duration']:.2f}",
                track['persistent_id']
            ])
    print(f"📄 Missing track log saved: {missing_log_path}")    

def show_summary_and_confirm(total, exact, multiple, not_found):
    result = {"relink": False}

    def do_relink():
        result["relink"] = True
        window.destroy()

    def cancel():
        result["relink"] = False
        window.destroy()

    window = Tk()
    window.title("Relink Summary")
    window.geometry("400x600")

    Label(window, text="Relink Summary", font=("Helvetica", 14, "bold")).pack(pady=(15, 5))
    Label(window, text=f"🎵 Total missing tracks: {total}").pack(pady=5)
    Label(window, text=f"✅ Exact matches found: {exact}").pack(pady=5)
    Label(window, text=f"⚠️ Multiple matches (manual): {multiple}").pack(pady=5)
    Label(window, text=f"❌ Not found: {not_found}").pack(pady=5)

    Button(window, text="Relink All Exact Matches", command=do_relink, width=25).pack(pady=(20, 5))
    Button(window, text="Cancel", command=cancel, width=25).pack()

    window.mainloop()
    return result["relink"]

# === MAIN ===

print("Fetching missing tracks from Music.app...")
missing_tracks = get_missing_tracks()
print(f"{len(missing_tracks)} missing tracks found.")

# === Dump missing tracks to log ===
missing_log_path = "missing_tracks_log.csv"
log_missing_tracks(missing_tracks, missing_log_path)

user_config = get_folder_and_match_fields_gui()
search_folder = user_config['folder']
recursive = user_config['recursive']
match_fields = user_config['fields']

print(f"Searching in: {search_folder} (recursive: {recursive})")
print(f"Matching by: title + {', '.join(k for k, v in match_fields.items() if v)}")

precheck_log_path = "music_app_relink_precheck.csv"
precheck_log = open(precheck_log_path, "w", encoding="utf-8", newline="")
csv_writer = csv.writer(precheck_log)
csv_writer.writerow(["Title", "Artist", "Album", "Status", "Match Path"])

exact_matches = []
multiple_matches = []
not_found = []

for track in missing_tracks:
    print(f"\n🔍 Looking for: {track['title']} – {track['artist']}")
    trackName = track['title']

    #matches = find_single_match(track, search_folder, match_fields, recursive)
    matches = search_folder_with_metadata(track, search_folder, match_fields, recursive)

    status = ""
    match_path = ""

    if len(matches) == 1:
        match_path = matches[0]
        status = "MATCH"
        foundTrack = track
        foundTrack['location'] = match_path
        exact_matches.append(foundTrack)
        print(f"✅ Match: {match_path}")
    elif len(matches) > 1:
        status = "MULTIPLE_MATCHES"
        multiple_matches.append(track)
        print(f"⚠️ Multiple matches found ({len(matches)}), skipping.")
    else:
        status = "NOT_FOUND"
        not_found.append(track)

    log_line = f"{track['title']}\t{track['artist']}\t{track['album']}\t{status}\t{match_path}\n"
    csv_writer.writerow([
        track['title'],
        track['artist'],
        track['album'],
        status,
        match_path
    ])

precheck_log.close()
print(f"\n📄 Precheck CSV saved: {precheck_log_path}")

# Show summary
do_relink = show_summary_and_confirm(
    total=len(missing_tracks),
    exact=len(exact_matches),
    multiple=len(multiple_matches),
    not_found=len(not_found)
)

# Perform relinking
if do_relink:
    print("\n🔗 Relinking exact matches...")
    for track in exact_matches:
        success = relink_track_by_pid(track['persistent_id'], track['location'])
        print(f"{'✅' if success else '❌'} {track['title']} → {track['location']}")
    else:
        print("❌ Relinking canceled by user.")