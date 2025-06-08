on run
	set output to ""
	tell application "Music"
		set allTracks to every file track of library playlist 1
		repeat with aTrack in allTracks
			try
				if location of aTrack is missing value then
					set trackName to my safeText(name of aTrack)
					set trackArtist to my safeText(artist of aTrack)
					set trackAlbum to my safeText(album of aTrack)
					set trackDuration to my safeText(duration of aTrack)
					set trackYear to my safeText(year of aTrack)
					set trackLoc to my safeText(location of aTrack)
					set trackID to my safeText(persistent ID of aTrack)

					set output to output & trackName & tab & trackArtist & tab & trackAlbum & tab & trackDuration & tab & trackYear & tab & trackLoc & tab & trackID & linefeed
				end if
			on error errMsg
				log "Error processing track: " & errMsg
			end try
		end repeat
	end tell
	return output
end run

on safeText(val)
	if val is missing value then
		return ""
	else
		return val as string
	end if
end safeText