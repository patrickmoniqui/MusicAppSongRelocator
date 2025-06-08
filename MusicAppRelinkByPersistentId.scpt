on run {thePersistentID, newPath}
	tell application "Music"
		set foundTrack to first file track of library playlist 1 whose persistent ID is thePersistentID
		set location of foundTrack to POSIX file newPath
	end tell
end run