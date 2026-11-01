<!-- original: es/CHANGELOG.md c1e42294988447ccdc7675e806675de1886fde4f -->
# What's new in Bellbird

This is a translation of the Spanish original, made with artificial intelligence. If you find an error, report it at https://github.com/miguel-cinsfran/bellbird/issues. See the [original in Spanish](../es/CHANGELOG.md).

What changes in each version, in plain language. Technical details are in
the git history.

## 3.0.0, unreleased

The app is now called Bellbird, after the bellbird, the national bird of
Paraguay.

### The new name

- The program is now `Bellbird.exe`, and the ZIP and its folder carry the
  name Bellbird with the version number.
- A shortcut to `YTChatTTS.exe` stops working after updating. If you opened
  the app from a shortcut, delete it and create a new one from
  `Bellbird.exe`, inside the app folder.
- Sources that the app created in OBS keep their name, so the scenes you
  already have keep working.

### What's new

- Camera framing. `Ctrl+F3` says how you look in the camera of the OBS
  live scene: whether you are centered, far away, outside the edge or with
  little light, and where to move. `Ctrl+Shift+F3` turns on warnings with
  their own sound when the face leaves the frame and when it returns.
  Pressing `Ctrl+F3` twice, beeps guide you until you are well framed. The
  image is analyzed on the computer, without sending it anywhere. The
  camera, the warnings and the left-right inversion are chosen in the new
  *Camera* category of Preferences.
- `Ctrl+Shift+O`, or *Show OBS* in the *Broadcast* menu, brings the OBS
  window to the front, also when it is in the notification area. If OBS is
  waiting for an answer, such as the safe mode question, focus goes to that
  box.
- If OBS is open but not responding, the app no longer asks you to check
  that it is open: it says it may be waiting for an answer and that you
  choose *Show OBS*.
- *Record while broadcasting*, in the *Broadcast* menu. With the check box
  checked, OBS starts recording when the broadcast starts well, and stops
  recording when the broadcast stops. If you were already recording, that
  recording continues as it was. It is unchecked.
- If recording cannot start, the broadcast continues and the app warns
  with its own sound.
- With that check box checked, the check before broadcasting warns if the
  OBS profile records with its own encoder. In that case, broadcasting and
  recording at the same time puts twice the load on the computer.
- *Choose microphone…*, in the *Broadcast* menu, opens a box with the OBS
  microphone source and the device it uses. When you press *Apply*, OBS
  changes the device and the app says whether sound is coming in. The
  shortcut to mute the microphone uses that source from then on.
- On TikTok, likes are written in the chat list, one row per person: “Ana
  sent 15 likes”. Before, they only played a sound.
- Each TikTok live stream notice has its mode in *Preferences*, *Reading*
  category: joins, likes, followers, shares and treasure chests. Each one
  can be read aloud, only shown with its sound, or not shown. By default,
  followers, shares and treasure chests are read, and joins and likes are
  only shown. If you already had join or like reading checked, it is
  respected.
- The chat list has the *Notices* filter, which shows only those TikTok
  notices.
- The app is also in English. The language is chosen in *Preferences*,
  *General* category, and applies on restart. When saving, a box offers
  *Restart now* or *Later*. By default it uses the Windows language.
- Without a connection, the main window shows the *Recent streams* list
  with the last ten live streams and videos, from YouTube and TikTok.
  Enter on one reopens it.
- The history and recent streams show the short date, such as 10/27/2026,
  instead of 2026-10-27.
- The app texts use Windows terms, such as *Delete* and *Enter*, and
  shorter phrases. Some names change: *Download manager*, *Read aloud*,
  *API key*, and *voice* where it used to say TTS. Each section of
  *Preferences* is called a category, as in NVDA.
- The moderation actions in the chat context menu are named as on YouTube:
  *Put in timeout* for 5 minutes and *Hide on the YouTube channel*, which
  can be undone from YouTube Studio.
- In the music window, the button that reads the folder again is called
  *Refresh folder*, with the letter Z. Notices say *link* instead of
  *address*, *application* instead of *program* and *Esc* instead of
  *Escape*.
- With the YouTube session started, `F2` says how many units of the daily
  quota were used today from this computer. The number is approximate, and
  because the quota is shared among those who use the application, it helps
  to know whether a quota error comes from your use or from others'. It can
  be removed from the summary in *Preferences, Status (F2)*.
- If there are other versions between the installed one and the new one,
  the update window shows the what's new of all of them, from the newest to
  the oldest, each with its heading and version number.

### The Download manager, renewed

- The window has two tabs. *Search on YouTube* opens first, with the focus
  in the field. *Downloads* has the queue and the history.
- In the *Search or paste link* field, words search YouTube and a link goes
  to the queue, whether from YouTube or another supported site. *View
  supported sites* opens the list of sites. The field remembers recent
  searches.
- Results show title, channel, duration, views and date, and the *Details*
  box has the full data of the selected one. *Amount* chooses how many
  results arrive, and *Show more* brings another batch.
- The *Show filters* check box adds type (videos, playlists, channels or
  live), duration, date and order.
- Enter on a video downloads it without asking and says “Downloading” or
  “Queued” with the title. Enter on a playlist or a channel shows its
  videos. Backspace returns to the results, and *Add whole playlist*
  downloads it completely.
- Spacebar listens to the result without downloading it, and Spacebar again
  pauses it. If music was playing, it pauses while you listen and then
  returns.
- The context menu of a result lets you add it to the queue, listen to it,
  download it as audio or as video without changing the chosen format,
  open it in Bellbird, add it to the music, view its contents, copy the
  link and open it in the browser.
- Before adding something, the app warns if it is already in the history.
  An ongoing live stream is not downloaded, and the app says so.
- The *Downloads* tab has a single list, and *Show* chooses what is shown:
  all, in progress, waiting, completed or with errors, each with its
  amount. With the Applications key or `Shift+F10` the menu opens to open
  the file or its folder, retry, download again, copy the link, cancel and
  delete. Delete removes the selected download from the list.
- While downloading, the *Status* column says the speed and the time left.
  In a playlist it also says which video it is on, such as “video 3 of 10”.
  The *Progress* column shows a bar next to the percentage.
- *Choose format…*, in the context menu of a video, shows the resolutions
  that video has with its size, such as “1080p 60 fps, MP4, 255 MB”, and an
  audio-only option. The chosen one downloads without changing *Format* or
  *Quality*. Checking the formats takes a few seconds, and the app warns
  with a sound.
- *Format* has nine options: original video, MP4 or WebM, and original
  audio, MP3, M4A, Opus, FLAC or WAV. *Quality* changes with the format:
  resolution for video and kbps for audio. The file keeps the title and the
  video data, and the thumbnail when the format allows it.
- Audio is also downloaded on sites that do not separate it from video,
  such as Dailymotion or Twitch.
- *Preferences* has the new *Downloads* category: folder, numbering the
  files of a playlist, simultaneous downloads, speed limit, own folder for
  each playlist and file names.
- When you exit the app with unfinished downloads, the question says how
  many will be canceled. It appears even if you have turned off the
  confirmation on exit.
- Search, adding to the queue, processing, the end of the queue and a
  download that ended halfway have their own sounds, in both themes.
- The package brings the program YouTube now asks for to read its videos,
  so downloads and the player get all formats. Opening a video or starting
  a download takes about a second and a half longer.
- In *Preferences*, *Downloads* category, *yt-dlp update channel* chooses
  between *Stable* and *Nightly*. *Nightly* brings fixes for YouTube a few
  days earlier, and may bring new failures.

### Application appearance

- The window, the streaming chat panel and the documentation change
  colors, with a palette inspired by the bellbird: cool white and
  turquoise. All text still meets the minimum contrast.
- All windows use the same colors. Fields and lists are white, the main
  button of each window is turquoise with white text, and group titles are
  also turquoise.
- In Broadcast, Preferences and YouTube live stream, each button is next
  to the field it acts on, and the buttons of the same section are in one
  row. The Live stream history is larger and shows full titles.
- All Preferences labels end with a colon. In Scheduled messages the list
  has its label, and the intervals are called “Minimum interval” and
  “Maximum interval”. In Music, showing the filters is a check box, as in
  Downloads.
- The status bar says “Speed”, “Volume” and “Super Chats” instead of
  abbreviations. In Broadcast, the TikTok user can only be typed when the
  destination is TikTok.

### Fixes

- When TikTok slows down repeated requests, the app no longer takes it for
  a live stream that does not appear. When broadcasting it warns that
  TikTok is rate-limiting requests, with its own sound. When connecting to
  the chat it says so, instead of a technical error, and waits half a
  minute before retrying.
- F2 says the singular when there is only one: “1 gift”, “1 Super Chat”
  and “1 read”.
- Two TikTok errors are understood better: “TikTok is not responding for
  now” and “TikTok returned an error”, instead of naming internal parts.
- Canceling a download that already finished says “The download already
  finished”, instead of announcing that it was canceled.
- When closing Preferences without saving after testing a voice, the test
  voice no longer stays open.
- When the TikTok chat reconnects, the list is no longer emptied and the
  video does not start again on its own.
- In *Downloads*, the status of a waiting download is read “queued”,
  without the underscore.
- In *Downloads*, the link of a video opened from a playlist downloads only
  that video, and not the whole playlist.
- In *Downloads*, each download waiting for its turn uses the format and
  folder that existed when it was added, even if you later change the
  options.
- No access letter repeats in the *Preferences* categories or in the
  broadcast, comments, history and downloads boxes. *Cancel download*
  moves to the letter A and *Clear history* to H.
- The access letters of each *Preferences* category no longer repeat
  those of *Save* and *Cancel*, nor do those of the main window repeat the
  one of *Link or ID*. *Send* changes in the live stream chat (Alt+N),
  *Read recent messages with* (Alt+R), and in *API and session* and
  *Scheduled messages* the save buttons (Alt+A), *API key* (Alt+V),
  *OAuth client ID* (Alt+O) and *Add* (Alt+R).

## 2.5.1, October 2026

Music and TikTok live stream fixes, and filters for the library.

### License

- **The application moves to the GPL-3.0 license.** Anyone who uses this
  code in another program must publish theirs under the same license.
  Versions up to 2.5.0 remain under the MIT license.

### Music

- **Music and the player no longer share the volume.** Before, muting the
  video or the live stream with Ctrl+M also muted the music, and pausing one
  could affect the other. Now each one has its own volume.
- **Matching also raises quiet songs.** Before it only lowered loud ones,
  and with music volume at 100 it could not raise any. It raises each song
  as far as its peak allows, without distorting.
- **The crossfade between songs no longer causes volume jumps.** The
  ending song goes down from its own volume. Also, changing songs in the
  middle of a crossfade no longer leaves the previous one playing.
- **The search filters by the start of each word.** When you type “a”,
  songs with a word that starts with “a” come up, not every song with an a
  in the middle. Several words are searched in any order: “lou oj” finds
  “Ojos” by Lou Cornago.
- **Filters and order.** The “Show filters” button opens two boxes:
  “Show”, to see all songs or those of one artist, and “Sort by”, with
  collection order, title, artist, newest first or duration. They combine
  with Find, they say how many songs remain and they are remembered for
  next time. A song with several artists appears under each one. With the
  filters hidden, all songs are shown.
- **Your own playlists.** In the playlist editor, Enter checks and unchecks
  the song, same as Spacebar. “New playlist” and “Edit playlist” offer the
  folder songs even if a playlist is selected in Collections. If a playlist
  is missing a song because its file is gone, the warning says which one,
  and it is not repeated when browsing Collections.

### Lists throughout the application

- **Typing several letters in a row jumps to the item that starts that
  way.** Before it only worked in the chat and in comments. Now also in
  the history, the AI conversation, scheduled messages and music
  playlists.

### TikTok

- **If the live stream cannot be opened, it says so.** Before you heard
  “End of the video” even if the live stream had never started playing.
  Now it warns with an error sound that it could not be opened, and the log
  notes the reason so the cause can be found.

## 2.5.0, October 2026

Asking an AI what is shown in the broadcast, and transitions between songs.

### Asking the AI

- **A window to ask what is shown, with Ctrl+Shift+I.** Add a screenshot of
  the live scene or of an OBS source and ask whatever you want: whether the
  camera is on, whether something came out black, what text is on screen.
  The response is read when it arrives and stays in the conversation so you
  can keep asking.
- **Quick question with Ctrl+Shift+F2.** Captures the live scene, sends it
  and reads the response without opening any window. The default question
  asks first for problems in the scene and then describes it.
- **Artificial intelligence page in Preferences.** You choose the provider
  (Google Gemini, OpenAI, Anthropic, OpenRouter, OpenCode Go, Command Code
  or another OpenAI-compatible one), save the key and choose the model. The
  key is kept in Windows Credential Manager. The model list brings only
  those that accept images, and with OpenRouter and OpenCode Go it can show
  only the free ones.
- **Their own warnings.** A melody plays while it waits, and there are
  sounds for the request sent, the response, the failure and the
  cancellation. If the screenshot comes out black, it is not sent, and it
  says why: the scene has no capture or a source has nothing chosen to
  capture.
- **The first send asks for confirmation**, because the screenshot and what
  you type leave your computer toward the provider.

### Music

- **Crossfade between songs.** The end of a song blends with the beginning
  of the next, and the silence that many files have at the start and end is
  skipped. It lasts 6 seconds by default; it is changed in Preferences,
  Music page, from 0 to 12, and 0 turns it off. Changing songs with the
  shortcut makes a short fade, of half a second.
- **Volume matching corrects by the right amount.** Before it exaggerated
  the difference between songs. Also, it no longer measures on its own:
  when opening the Music window it asks whether to measure the pending
  songs, and the window has a button to start and stop.
- **The song change sound is off by default** and, if you turn it on, it is
  softer and lower.
- **The folder is watched.** New songs appear on their own in the list. The
  Music window has the Refresh folder button, and the default folder is
  Music, next to the program.
- **When resuming, it says how many songs the queue has**, for example
  “Resuming 6: evergreen”. With “Remember the last playlist on open”,
  Play follows the last queue, which may be a search and not the whole
  folder.
- **More formats:** aiff, aif, mka and webm.

### Chat and reading

- **The ten most recent messages, with Ctrl+Shift and a number.** 1 reads
  the last one and 0 the tenth from the end. A Preferences check box,
  Reading page, makes them work in any application.
- **With the screen reader or with the application voice.** On the same
  page you choose who reads them. With the voice, the requested message
  plays before the ones that are waiting, and then those follow in their
  order.
- **When the application opens, the address field is empty.** The last
  address is no longer remembered from one time to the next. To return to a
  live stream there is the History.

### Broadcast

- **The microphone says which device it uses.** When you unmute it with
  Alt+Shift+M, for example: “Microphone on: Windows default, WO Mic
  Device”. If OBS uses the default, it says so, because that microphone
  changes when Windows chooses another.
- **Warning if the microphone is getting no sound.** After unmuting, the
  application listens for three seconds. If nothing comes in, its own sound
  plays and it says “The microphone is getting no sound. Check which one
  is chosen in Windows or in OBS.”.
- **The Broadcast window explains what is shown in the live stream**: the
  window chosen in Window to capture. That capture carries no sound, which
  comes from the desktop audio and the OBS microphone.
- **The chat panel appears in OBS again after restarting the
  application.** If OBS opened before the application, the chat did not
  appear in the live stream until the source was reloaded by hand. Now the
  application reloads it on its own when the panel is turned on.
- **The TikTok user works with uppercase letters.** TikTok only recognizes
  the user in lowercase, and with an uppercase letter the application did
  not find the live stream. Now it turns it to lowercase on its own, also
  the one already saved.
- **The TikTok chat connects even if the live stream takes time to show
  up.** When going live, TikTok sometimes says for a few seconds that there
  is no live stream, and the application gave up. Now it tries again until
  it appears.
- **F2 says how many viewers there are now on TikTok and how many
  passed.** Before it counted as viewers everyone who had entered since
  the beginning, and the number only went up. Now it says, for example,
  “12 viewers now, 108 in total”.
- **A TikTok live stream is not paused in the player.** TikTok does not
  keep what was broadcast, so resuming meant opening it again and it got
  stuck. Now pause warns that it cannot and says the Mute audio shortcut,
  which silences the live stream without stopping it.
- **More TikTok events.** Comments made only with stickers are read (“Ana:
  sticker”) and questions (“Ana: Question: ...”). When TikTok pauses the
  live stream or resumes it, its own sound plays for each case and it is
  said. New check box in Preferences, Read who likes: checked, in addition
  to the sound “Ana sent 15 likes” is read. It is unchecked because in
  large live streams likes do not stop.

### Sounds and windows

- **Sounds page in Preferences**, to silence each sound separately.
- **Busy tone** when another program already uses one of the shortcuts that
  work in any application. Before, the error sound played.
- **The windows that stayed gray** (Preferences, the update ones, Broadcast
  to and the AI ones) use the colors of the main window. With Windows high
  contrast nothing changes.
- **Download errors** say the reason in plain language.
- **Texts that were cut off**: the Send button when you cannot write in the
  chat, the voice speed and volume in the status bar, and the fields of the
  YouTube live stream dialog, which stayed stuck to the scroll bar. The help
  text of the main window is no longer cut off when disconnecting from a
  live stream. In Preferences, Status (F2), the viewers check box now says
  “Viewers now and in total”.

### To find problems

- The diagnostic log notes which sound played, which shortcut or menu
  command was used and what type each chat event was, without the message
  text or who wrote it. The list of internal processes is no longer
  repeated every 30 seconds when it did not change.
- **The detailed log is on** in a new installation. Anyone who had already
  turned it off in Preferences keeps it off.
- **Help, Open logs folder** opens the folder where the logs are, to send
  them when something fails.
- The failure file no longer grows without end: when it passes 1 MB it is
  saved separately and a new one starts.

## 2.4.1, October 2026

- **The automatic update no longer stops when closing the previous
  version.** The installer waited a minute and showed “the application did
  not close in time” even though YTChat TTS had already closed. It happened
  when another program, such as the screen reader or the antivirus, was
  still watching the process. Now it detects the close immediately. From
  2.3.4 or 2.4.0 it updates the usual way.

## 2.4.0, October 2026

Music while you stream, without opening another program.

### Music

- **A Music menu with its shortcuts.** Ctrl+Alt+Spacebar plays or pauses,
  Ctrl+Alt+Right arrow and Ctrl+Alt+Left arrow go to the next or previous
  song, Ctrl+Alt+Up arrow and Ctrl+Alt+Down arrow raise and lower the music
  volume, and Ctrl+Alt+T says what is playing. Ctrl+Alt+M mutes the music,
  Ctrl+Alt+D stops it, Ctrl+Alt+A changes shuffle, Ctrl+Alt+R changes
  repeat, and Ctrl+Alt+Shift+Right arrow and Ctrl+Alt+Shift+Left arrow
  fast forward and rewind 10 seconds. The first time it may take a few
  seconds to prepare, and it announces it.
- **Your Windows Music folder, or the one you choose.** If you do not
  choose another one in Preferences, Music page, the Windows Music folder
  is used, even if you moved it to another drive. That page also has
  shuffle, repeat the whole queue or the current song, music volume
  (separate from voice and player) and which audio output it plays on.
- **What is said when a song changes.** Choose between nothing, the title,
  the title and the artist, or only the artist. With “Nothing” only the
  song change sound plays, if you leave it on, but when you change songs
  with the shortcut the title is said, because you asked for it. Another
  check box decides whether “Music paused”, “Music resumed” and “From the
  beginning” are announced.
- **The Music window, with Ctrl+Shift+M.** Searches your folder while you
  type, even if you do not type accents. Plays the chosen song or the whole
  result, adds it to the queue, shows the queue and jumps to any song with
  Enter. With “Play next”, the chosen song plays when the current one ends,
  without cutting anything, and then the queue continues where it was.
  While it is open, the music shortcuts keep working.
- **Title and artist of each file.** Songs first appear with the file name
  and, a few seconds later, with the title and artist that the file itself
  brings, without the song you are on moving. The second time you open the
  folder they already appear that way from the start.
- **Your own playlists, in the same window.** In the Collections list,
  “Library” is your folder and below it are your playlists, each with how
  many songs it has. Create one with “Add to a playlist” and “New
  playlist…” from the menu of a song, rename and delete them, remove songs
  with Delete and move them with Alt+Up arrow and Alt+Down arrow. You can
  also save the playing queue as a playlist. They are saved as .m3u8 files,
  which other players can open.
- **YouTube links and playlists.** In the Music window, “Open link…”
  accepts a video or a whole YouTube playlist and adds its audio to the
  queue. Shuffle also works for those playlists.
- **Matching song volume.** All songs sound similar, as in Spotify: each
  file is measured once, in the background, and the volume is corrected
  when each song starts. The first time its own sound plays and it says how
  many songs are going to be measured. Progress appears in the Music window
  and in F2, and it is turned off with a check box on the Music page.
- **F2 says what is playing**, if you leave it on on the “Status (F2)”
  page.
- **Resumes where it left off.** When you open YTChat and press Play, it
  follows the last queue from the song it was on. It does not start playing
  on its own.
- **Shortcuts in any application**, optional. With the check box on the
  Music page, music shortcuts work even when you are in OBS or in a game.
  It is off because while it is on those keys do not reach other programs.
  Where NVDA thinks there is a table, such as the desktop, it keeps
  Ctrl+Alt+arrows: there press NVDA+F2 before the shortcut.

### Shortcuts

- **Each family of keys, an area.** Ctrl is the player, Alt the chat,
  Ctrl+Shift opens windows, Alt+Shift is the live stream and OBS, the F
  keys are voice and Ctrl+Alt is music. That is why some default ones
  change: connect and disconnect move to Alt+Shift+C and Alt+Shift+D, go to
  the messages list to Alt+Shift+L, the OBS microphone to Alt+Shift+M,
  mark an incident to Alt+Shift+I, copy the link to Alt+Shift+E and the
  download manager to Ctrl+Shift+D. If you had changed one, yours is
  respected.
- **Keys with their English name** on the Shortcuts page of Preferences
  and when capturing a combination.
- **Ctrl+Alt with letters and numbers.** In Preferences, Shortcuts page,
  the music ones accept Ctrl+Alt with a letter or a number. When capturing
  it, the application checks your keyboard: if AltGr with that key writes
  something, such as the at sign on the Latin American keyboard, it tells
  you and asks for another one, so you can keep typing that character in
  the chat.

### Chat

- **A connection drop no longer closes the live stream.** Before, if the
  connection to the chat dropped, when it came back on its own the
  application read messages but did not let you write or moderate. Now it
  warns “Lost connection to the chat”, retries after 1, 2, 5 and 10 seconds,
  and then according to the “Maximum wait between tries” in Preferences.
  When it returns it says “Chat reconnected.” and everything continues as
  before the drop.
- **Messages are not repeated after a drop.** What was already read is not
  read again when reconnecting.

### Screens

- **The YouTube live stream window fits on short screens.** On a screen
  768 pixels high, the Broadcast and Cancel buttons were cut off. Now the
  fields scroll and those buttons always stay in view.
- **Read-only fields are reached with Tab.** The volume matching progress
  in the Music window and the thumbnail in the YouTube live stream window
  were skipped when moving with Tab.
- **Full names in Preferences.** The page list no longer cuts “Reading
  queue”, “Interface and sounds” or “Scheduled messages”.

## 2.3.4, October 2026

Fixes that came out of a test live stream.

### Broadcast

- **A single warning when OBS cannot keep up, and it can be turned off.**
  Before, two long phrases played every minute while playing. Now it is a
  single one, “OBS cannot keep up: 16 percent of frames are dropped”, and
  it is not repeated before five minutes. Ctrl+Shift+A turns it off and on
  again, and it is saved. It is also in the Broadcast menu and on the
  Broadcast page of Preferences. Network and reconnection warnings always
  continue.
- **Copying the link of a private live stream.** Ctrl+Shift+E now copies
  the link of the private or made-for-kids live stream that the application
  creates. Before it said that no live stream was connected.

### Chat

- **The chat stops retrying a live stream that already ended.** If the chat
  stayed connected to a live stream that had ended, it repeated without end
  “Disconnected” and “Retrying in 15 seconds (attempt 1 of 20)”. Now the
  application checks whether the live stream is still live. If it ended, it
  says it once, “The live stream ended. Chat disconnected”, with the end of
  live stream sound, and stops trying. If it is still live, it retries as
  before, and the limit of twenty attempts is now met.

## 2.3.3, October 2026

A fix that completes the Stop change from 2.3.2.

- **The live stream button waits for OBS.** While Stop waits for OBS to
  confirm, the button says *Stopping the live stream* instead of offering
  *Broadcast live* again. If you press it during that time, it warns that it
  is waiting for OBS and does not try another broadcast, which OBS rejected
  with “Cannot switch destinations while broadcasting.” The same in the
  Broadcast window. When OBS confirms, the button returns on its own to
  *Broadcast live*.

## 2.3.2, October 2026

Fixes for broadcasting with an unstable network and an option for the
player to use less.

### Broadcast

- **Stop waits for OBS to confirm.** Before it said “Broadcast stopped”
  instantly, even if OBS took almost a minute to stop with the network
  down. Now it says it when OBS really stopped. If it takes more than three
  seconds, it warns that it is waiting. If after ninety seconds OBS is
  still broadcasting, it says so for you to stop it in OBS.
- **The YouTube live stream ends even if the network drops.** If YouTube
  does not confirm the end, the application tries again on its own every
  fifteen seconds for ten minutes, and warns with a new sound when it
  succeeds. If it does not succeed, it tries again the next time you open
  YTChat, without asking you.
- **Warning when OBS reconnects, and when it returns.** The reconnection
  warning existed but could never play. Now it plays when the connection to
  the service drops and, with another new sound, when the connection
  returns.
- **Warning when the computer cannot keep up.** If frames are lost because
  the computer cannot encode or draw the scene, it says so with the
  percentage and suggests closing programs. It is different from the slow
  network warning.
- Each type of warning is repeated at most once per minute.

### Player

- **Play only the audio.** New check box in Preferences, Player page. With
  it, the player does not decode the picture of anything it plays, live
  streams or YouTube and TikTok videos, and the video card is left free for
  OBS. It is unchecked.

### To find problems

- The log saves each thing the application announces, and what the check of
  live streams left on air decided when opening. Chat messages are not
  saved.

## 2.3.1, October 2026

Updater fixes and a new General page in Preferences.

### Updates

- **The second update no longer fails.** Before extracting a new version,
  the application deletes what the previous update left, and that step
  always failed. The fix travels inside this version: to go from 2.3.0 to
  2.3.1 you still have to delete the `data\actualizacion\nueva` folder by
  hand before updating. The following ones no longer need it.
- **The update window is fully visible.** It was small, and the what's new
  and the *Later* button were not visible. Now it grows with its content,
  puts the buttons in a row and can be enlarged.

### Preferences

- **General page, the first in the list.** It gathers *Check for updates at
  startup* and the detailed log, which were in Connection and Diagnostics,
  and adds:
  - Ask before exiting if there is a connected chat or a broadcast in
    progress.
  - Remember the last address: when opening, the field brings the last live
    stream you connected to.
  - Play the startup sound.
  - Open the data folder.
  - Export and import preferences, to move them to another computer or save
    a copy. The keys of your accounts are not exported.
  - Reset all preferences to factory values.
- Before importing or resetting, a copy of the current preferences is saved
  in the data folder.
- The Diagnostics page disappears.

## 2.3.0, October 2026

More voices to read the chat and more options when creating a YouTube live
stream.

### Voices

- **Voices page in Preferences.** There you choose the voice engine, the
  voice, the speed, the volume and the pitch. *Test voice* lets you hear
  how it sounds before saving, and when saving the change is applied
  without restarting.
- **Three voice engines.** The usual Windows voices (SAPI 5), the Windows
  OneCore voices, and ElevenLabs, which generates the voice on the internet
  with your account key.
- **ElevenLabs does not leave the chat mute.** If the internet drops, the
  key does not work or the balance runs out, the message is read with the
  Windows voice and the application warns you once. You can set a character
  limit per session and use it only for Super Chats, members, treasure
  chests, the channel owner and moderators. *Check key* tells you how many
  voices your account has and how many characters you used this month.
- **Your voice no longer changes on its own when installing another one.**
  Before the voice position in the list was saved, and a new voice shifted
  the list. Now the name is saved. The first time you open this version,
  your saved voice converts on its own.
- **Speed goes from 0 to 100.** F9 and F10 move it by 5 and the application
  says the number. The speed you had sounds the same as before.
- **Announcements come back on their own if you restart the screen
  reader.** If you open or restart NVDA or JAWS with the application
  already open, announcements play again a few seconds later.

### Preferences

- **Save is instant and audible.** Before it took a moment and the warning
  was lost when the window closed. Now it saves everything at once, the
  sound plays when you press *Save* and, back in the main window, the
  application says “Preferences saved” along with any other warning.

### Updates and warnings

- **If there is a new version, its window opens when the application
  starts.** It shows the what's new and has two buttons: *Download and
  install* and *Later*. With *Later* it closes and the next time you open
  the application it asks again. Before it only said it by voice once, and
  if you were reading something else with the reader, you missed it.
- **The what's new is read well.** It no longer starts with blank lines or
  brings asterisks, each point goes on a single line with its bullet and the
  cursor stays at the beginning.
- **When an update finishes, a window opens with the result.** If at that
  moment there is a connected chat, a broadcast or another window open, it
  waits for you to finish so it does not pull you out of place.
- **Each warning has its sound.** Download started, finished, with error
  and canceled; live stream on air, broadcast stopped and problem in the
  broadcast; update available and ready; and a little bell for general
  warnings, such as discarded messages. Before several used the same sound
  and you had to wait to hear the text to know what happened.
- **The “suave” theme no longer repeats sounds.** Ten events that sounded
  like another one now have their own sound.
- **On startup it no longer says “Preparing the player” or “Player
  ready”.** The player is prepared the same way, silently.

### Sounds

- **The “suave” theme sounds different again.** Since 2.2.0 its sounds were
  a copy of the “default” theme. Now they are their own sounds, shorter and
  softer. It is chosen in *Preferences, Interface and sounds*.

### YouTube live stream

- **The live stream window has more options,** and all are remembered for
  next time:
  - normal, low or ultra-low latency. With ultra-low the chat arrives
    almost at the moment;
  - made for kids. If you check it, YouTube turns off the live stream
    chat;
  - allow rewinding the live stream;
  - category and tags;
  - thumbnail, a JPG or PNG image up to 2 MB that you choose with the
    Windows box;
  - a playlist of your channel, so the live stream is saved in it. The
    playlists are brought with the “Load lists” button.
- **If YouTube does not accept the thumbnail, the category, the tags or the
  list,** the live stream goes out anyway and the application tells you
  why.

## 2.2.1, October 2026

Fixes to update without hitches and a lighter package.

- **OBS no longer blocks updates.** The OBS that the application opened
  used files from the YTChat folder, and as long as it stayed open the
  update could not replace them. Now OBS uses its own.
- **If an update cannot finish because a file is in use,** the warning says
  it may be OBS and that you close it before trying again. This also works
  to go from 2.2.0 to this version: if you opened OBS from 2.2.0, close it
  before updating.
- **The package goes down from 175 to 147 MB.** It no longer brings
  documents from other Google services or a library that the application
  does not use.

## 2.2.0, October 2026

This version lets you start and end a YouTube or TikTok live stream from the
application itself, without opening OBS or the Restream page. Signing in
with Google no longer requires creating your own credentials. The
application updates on its own, the sounds are new recordings and there are
different sounds depending on who writes and what happens in the live
stream.

### Going live

- **Broadcast live button in the main window.** When you press it, you
  choose the destination, YouTube or TikTok, with the one from last time
  already selected. The application opens OBS if needed, without taking
  focus from the screen reader, switches to the profile for that
  destination and reads a check before going live: format, scene, sources,
  audio and any problem, such as an empty scene or a muted microphone.
  While broadcasting, the same button says **End live stream**.
- **YouTube without touching the YouTube page.** A single window asks for
  the title, the description and the privacy (public, unlisted or private),
  and shows the OBS check. When you press *Broadcast*, the application
  creates the live stream on the channel, loads the key into OBS, starts
  broadcasting, waits for YouTube to show it and connects the chat on its
  own. The title and description are remembered for next time.
- **TikTok through Restream.** The application uses the OBS profile called
  `TikTok`, waits for TikTok to show the live stream and connects the chat.
- **Choosing what is broadcast.** In the *Broadcast* window
  (`Ctrl+Shift+T`) you choose the window that the scene captures, for
  example a game. That window is ordered by sections and its fields say
  what to do when something is missing.
- **`Ctrl+Shift+E` copies the link of the connected live stream**, to pass
  it to someone.
- **`F2` first says what state the live stream is in** that the application
  supervises, and whether TikTok or YouTube already shows it.
- **`F2` says how to return to the live stream** when the player is behind:
  “10 seconds behind the live stream. Press Ctrl+End to return to the live
  stream.”, with the shortcut you have configured.
- **An internet drop does not end the YouTube live stream.** If OBS loses
  the connection, for example when changing Wi-Fi, YouTube waits for the
  signal to return instead of closing the live stream, and the application
  warns that OBS is reconnecting. When finishing from the application or
  from OBS, the application closes the live stream on YouTube.
- **The chat panel is not left covered.** If another source in the scene,
  such as a screen or camera capture, is over the panel, the application
  brings it forward when going live and during the live stream, and says
  which source was covering it.
- **`Ctrl+F2` describes the OBS scene:** what sources it has, which one is
  in front, where each one is, whether it is visible and what covers it.
  The *Broadcast* window shows the same in its own section, *How the scene
  looks*, and the panel status has its own label.
- **A live stream is not left on air without video.** When opening the
  application, if you have a YouTube live stream on air while OBS is not
  broadcasting, for example because you closed OBS after closing the
  application, it asks whether to end it.
- **The list of windows to capture no longer brings untitled windows**,
  which were read as “(null)”.

### Signing in with Google

- **Without your own credentials.** Before you had to create a project in
  Google Cloud and load its client. Now it is enough to press *Sign in* in
  *Preferences, API and session*: the application brings its own client.
  Google shows an unverified app warning, which is passed with *Advanced
  options* and *Continue*. Anyone who already had their own credentials
  keeps using them.

### Updates

- **The application updates on its own.** In *Help, Check for updates* a
  window says whether there is a new version, shows its what's new in a box
  that can be scrolled, and downloads and installs it with a button. The
  application closes and reopens in about a minute. If the new version does
  not open, it returns on its own to the previous one and says so on
  startup. The configuration, the session, the history, the downloads and
  the sounds you have changed are kept.
- **Warning on startup.** If there is a new version, it is announced only
  once.
- **Updating yt-dlp has its own window,** with the status, a progress bar
  and each step announced: searching, downloading and the result.

### Sounds

- **New sounds.** All sounds are new recordings, in the public domain,
  chosen one by one so they can be told apart. The `sounds/CREDITOS.md`
  file says where each one came from.
- **A sound depending on who writes.** Messages from the channel owner, a
  moderator, a verified account and a member sound different from a common
  message.
- **Edge.** When you reach the start or the end of the chat, comments or
  history list with the arrows, a dull thud plays.
- **End of the live stream.** When a TikTok live stream ends, a door closing
  plays, and not the disconnection sound.

### TikTok live streams

- **More things from the live stream.** In addition to the chat and gifts,
  it reads who follows the channel, who shares the live stream and who
  sends a treasure chest, each one with its sound. Likes only play a sound,
  at most one every three seconds, so they do not cover the chat.
- **Gifts sound according to their size:** a coin for the small ones,
  several for the medium ones and a shower of coins with a melody for the
  large ones.
- **Whoever joins the live stream has their own sound,** a door opening,
  when joins are turned on in *Preferences, Reading*.
- **Old messages are not read when connecting.** TikTok sends the last
  messages of the live stream when connecting. Messages from before the
  connection were already discarded, and now also those that TikTok marks
  as old.

### Other changes

- **`F3` says the author of the last message read.**
- **The application no longer closes on its own when ending a live
  stream.** It was caused by the failure log itself, which noted too much.
- **Scheduled messages are only sent to your own live stream.** Before they
  were sent to any connected YouTube live stream with the session started,
  also to another channel's. Also, what you change in Preferences is applied
  without restarting, a new message is born active and the first one does
  not go out suddenly when connecting.
- **When browsing the sound themes in Preferences, a sample plays** of each
  one, without changing the theme until you accept.
- **When adjusting the same value several times, only the number is
  said.** The first time, for example, “Voice volume: 40%”, and the
  following ones only “45%”, as long as you stay with the same control
  within the minute. When you move to another one, such as speed, it says
  the name again. In the player volume slider the number is no longer heard
  twice.
- **Sounds no longer slow down the window,** and the player takes less time
  to start the first time.
- **The configuration accepts `%`, `#` and `;`** in texts, for example in a
  live stream title, without losing them when saving.

## 2.1.0, October 2026

This version adds a chat panel for the broadcast, the ability to write in the
chat from the application itself and a window to compose the OBS scene
without seeing the screen. The player obeys much better, downloads are
ordered and warn when they finish, and the application data moves to its own
folder.

### Player

- **The player obeys instantly.** After fast forwarding or rewinding, pause
  and play were lost for ten or twenty seconds: “pause” was announced three
  times in a row and the video kept playing. In YouTube videos the audio
  travels separately from the video, and both reached the player over the
  network: the audio slowed everything else down. Now the audio is saved
  first on disk, in the `cache-audio` folder inside the `data` folder, and
  all commands are obeyed. By the way, the video starts showing in less
  than a second instead of six.
- **Live streams no longer freeze every minute and a half.** The video and
  audio of a live stream arrived separately and the player lost sync
  between them every 60 or 90 seconds, stopping for 25 to 50 seconds. Now
  they are joined before playing, with ffmpeg, a program included in the
  application. If ffmpeg takes time to start, the player waits for it to be
  ready instead of failing silently. If the live stream drops, it says so
  and reconnects on its own, up to twice.
- **Rewind and fast forward work in live streams.** The one-minute buttons
  and the ten-second arrows did nothing when the live stream arrives with
  separate tracks. Now each jump restarts the video and audio join a few
  seconds before the live edge, with a cut of two or three seconds.
  Consecutive arrows add up, and each one announces where you land: “20
  seconds behind the live stream”, “Live”. In live streams with separate
  tracks you can go back up to an hour, which is what YouTube keeps. Moving
  the slider or asking for a percentage is not available in these live
  streams, and the application says so.
- **Live streams that YouTube serves with video and audio together also
  move, with less margin.** They only allow going back about 30 seconds.
  When a live stream does not allow jumps, the arrows say so instead of
  failing with a confusing warning.
- **Go to live with `Ctrl+End`.** After rewinding, the *Player* menu has
  “Go to live”, with `Ctrl+End`, which returns to the live edge at once. If
  you are already live, it says so.
- **The slider and `F2` say how far behind the live stream you are.**
  Before the slider said “Live” even if you had gone back. Now it says “40
  seconds behind the live stream”, and `F2` announces it too when you are
  behind.
- **Rewinding in a live stream no longer jumps two hours back.** The player
  used a wrong duration, and a one-minute rewind ended at the beginning of
  the live stream window.
- **Seeking with the video loading or stopped says the reason.** If you ask
  for a jump while the video is loading, it says “Loading video” and not
  that it cannot fast forward. With the video stopped it says “The video is
  stopped”. It works for live streams and for recorded videos.
- **Moving the video while paused saves the destination.** If you move the
  video while paused, when you resume it continues from the new position
  and not from the beginning.
- **Videos split into tracks play.** Some recorded videos arrive with video
  and audio in separate tracks. Now they play, and you can jump without
  waiting for the download to finish. If a video does not start playing, it
  is loaded again once before warning that it could not be played.
- **The video of live streams loads again.** YouTube stopped offering a
  single stream with picture and sound together and the application kept
  waiting for it. Now it joins video and audio when they arrive separately,
  and if it still cannot, it notes in the log what it found.
- **The video cache respects its limit.** A video that does not fit in the
  configured limit is no longer downloaded entirely: the download stops
  right away and leaves no files. The cache downloads videos at 720p, and
  the remains of interrupted downloads are deleted on their own.
- **The audio cache can no longer hang.** If the audio download stops
  advancing, it is cut by time.
- **Pressing many times to fast forward no longer desyncs the player.**
  Some presses were lost and the announced time went back on its own. And
  pressing play or pause while the video was loading made it start from
  zero.
- **The video cuts less.** The network buffer was very small and any
  connection fluctuation interrupted playback.

### Chat and voice

- **Pausing reading (`F5`) really pauses the current sentence**, and while
  it is paused, voice, speed and volume changes are handled.
- **The first message after reconnecting is no longer cut.** A pending mute
  order was applied to the next message.
- **A configured voice that no longer exists does not prevent starting the
  application.** The first available one is used and it is noted in the log.
- **Warnings are no longer cut in half, not even in menus.** Before the
  text of a warning was lost if another key was pressed right away. Now it
  is heard entirely. The only ones that do not interrupt are those that
  repeat on their own: the warning that a video is still loading and the
  one that OBS is being queried.
- **Long sounds from custom themes are no longer cut at 5 seconds.**
- **Super Chats in yen, won or rupees add up well.** “¥1,000” added 1.
- **When reconnecting to a different live stream, nothing from the previous
  chat reaches the new one.** Scheduled messages and the writing box can no
  longer end up in the chat that closed, nor the comments of the previous
  video in the new one.
- **Reconnecting for real counts.** With unstable Wi-Fi, five micro-drops
  spread over hours used up the attempts even if each reconnection had
  worked. Now only consecutive failures count. The default values are 15
  seconds between tries and 20 attempts, about five minutes in total, and
  they are changed in *Preferences, Connection*.
- **It warns when messages are being lost.** If more chat comes in than the
  voice can read, the application discards the oldest. Now it says so once
  per session, reminds you that those messages are still written in the
  chat list and suggests turning on reading only the name, which is what
  makes the voice keep up. `F2` can also say how many are going, if that
  data is turned on in *Preferences*.
- **One more way to have the chat read to you: first the message, then who
  wrote it.** In *Preferences, Reading*, next to the three that already
  existed. You hear “hello everyone, from Lucía”. It is useful when many
  messages arrive in a row: you hear the content before the name and can
  decide whether it interests you without waiting.
- **Aliases for names that are impossible to hear.** Many YouTube names are
  strings of letters and numbers that the voice reads entirely in each
  message. Now a short name can be set for them: in the chat list, context
  menu on a message and *Set alias*. From that moment, that user is read
  and shown with the alias. To remove it, open the same thing and leave the
  field empty. The real name is not lost: timeout, hiding, muting and
  replying still act on the real account.
- **Voice failures are noted.** If the synthesizer fails when announcing
  something, before there was not even a trace.

### TikTok

- **TikTok live streams reconnect with version 6.6.6 of the library.** With
  the version that the project installs today, the connection stayed at
  “Connecting to the TikTok live stream” without reaching anything. Now it
  connects, and if something fails while preparing, it says so instead of
  staying silent. A user who is not live is reported as such.

### YouTube

- **If the YouTube session expires, the application says it by voice.**
  Before Google's technical text was read and the application kept believing
  there was a session. Now it warns, deletes the expired session and asks
  you to sign in again in *Preferences, API and session*. If the failure
  came from something you did, it offers to open that category. Scheduled
  messages only warn.
- **Signing in again after signing out works again.** Before Google returned
  an incomplete permission and moderating, commenting or writing in the chat
  failed with a format error.
- **Moderation acts on the user in the selected row.** Before moderation
  looked for the user by the visible name.
- **You can now write in the live chat.** Below the message list there is a
  writing box with its *Send* button. `Enter` sends the message and
  `Shift+Enter` inserts a line break. After sending it, the box is emptied
  and focus stays inside, so the next one can be written without tabbing.
  When the connection or the Google session is missing, the box and the
  button are still reached with Tab, and the reason is part of the button
  name.
- **When you cannot write in the chat, it now says why.** It distinguishes
  whether the API key is missing, whether the video does not exist, whether
  it is not a live stream or whether the live stream has chat turned off.
- **Commenting and replying on videos.** In the *Comments* tab, the *Comment
  on the video* and *Reply* buttons open the same box in a window.
- **Posting a comment and replying to one already work.** They did nothing:
  the text was written, *Publish* was pressed, the window closed and nothing
  was sent or warned.
- **In a video with comments closed it no longer lets you write one.**
  Before you could write it entirely and only when publishing did you find
  out that you could not.
- **`Enter` copies the selected message, and `Alt+Enter` opens the writing
  box.** Before, in the chat and comment lists, `Enter` did nothing.
- **Connecting became fast again.** It had become slow, from twenty to
  thirty seconds on some computers.
- **Disconnecting while it says “Connecting…” is possible**, and closing
  the application does not wait for a YouTube query to finish.
- **`F2` says how many people are watching the live stream and how long it
  has been broadcasting.** The viewer number was wrong and said zero even
  if there were people. Now it is correct and updates on its own every
  minute.
- **The API configuration guide is rewritten.** Each step gives the exact
  address of the corresponding Google Cloud screen, and the points where it
  is easy to get stuck with a screen reader are explained.

### OBS and broadcast

- **A chat panel for viewers to see.** Messages appear on a page with a
  transparent background that can be added to the broadcast, so that
  whoever watches the live stream reads the chat without leaving the video.
  The panel is turned on in the *Broadcast* window, with the *Chat panel for
  streaming* check box, which opens from the *Broadcast, Streaming panel…*
  menu or with `Ctrl+Shift+T`. If it is left on when closing the
  application, it turns on by itself when opening it again.
- **The chat panel does not repeat messages or show old ones.** Turning it
  on and off quickly does not repeat messages, and if the application closes
  it stops showing the ones it had received.
- **Composing the scene without seeing the screen.** In the *Broadcast*
  window you choose the scene and **any of its sources** (the chat panel,
  the camera, the game capture), move it to any of the nine usual
  positions, change its size, show or hide it, pin it so it does not move by
  accident and put it in front of the rest.

  Each change is announced aloud with what you need to know: what position
  it ended in, what size it has, what part of the screen it takes, whether
  it goes past the edge and, above all, **whether another source is
  covering it and how much**. That is the question that cannot be answered
  by looking.

  There is also a fine adjustment mode: it is turned on with a button and
  from there the arrows move the panel, in normal steps, large with
  `Control` or one pixel with `Shift`. `Enter` confirms and `Esc` undoes.
  And a button saves a snapshot of the scene, to show it to someone who
  sees.

  That way a complete scene can be built blind: the game in the center, the
  camera in a smaller frame at the top right and the chat in a corner.
- **Broadcast, record and put a scene on air from the same window.** There
  are buttons to start and stop the broadcast and the recording, pause, and
  put the chosen scene on air. `F2` can also say whether OBS is
  broadcasting, recording or with a scene on air, if that data is turned on
  in *Preferences, Status (F2)*.
- **Mute the OBS microphone with `Ctrl+Shift+M`.** The application checks
  and toggles the mute of the microphone source chosen in *Preferences,
  Broadcast*.
- **The chat panel check box works even if OBS is not there.** Before it
  stopped responding if OBS did not answer, even though the panel does not
  need OBS for anything.
- **The OBS server is turned on from here.** *Preferences, Broadcast*,
  *Enable the OBS websocket server* button, without having to look for it in
  the OBS menus.
- **When OBS cannot be turned on, it says why.** Before an empty message
  came out.
- **Browsing a drop-down no longer changes anything.** In the *Broadcast*
  window, going through the nine positions with the arrows moved the panel
  inside OBS once per arrow, live. Now the position is chosen and applied
  with its button.
- **The *Broadcast* window explains where the panel is in plain language.**
  Before it mixed three percentages that measured different things. There
  is a new button that explains in what order the window is used.
- **The *Broadcast* window does not get stuck** if the chosen source has
  disappeared in OBS or if OBS closes the connection: it warns and lets you
  continue. “Apply size” on a scaled panel no longer shrinks it to half.
- **OBS: the broadcast time was a thousand times larger.** One minute was
  announced as “16 hours 40 minutes”.

### Downloads

- **At most two downloads at a time.** Before, queuing ten downloads
  launched them all at once. Now two run, the rest wait “queued”, in the
  order they were requested, and they can be canceled while waiting.
- **Canceling no longer leaves programs open.** When canceling a download,
  or when closing the application, the programs that were downloading the
  file, including ffmpeg, close with it.
- **The name of each download is that of the final file.** Before the name
  of a temporary chunk was announced. And “Enumerate” no longer puts “NA -
  ” in front of single videos.
- **Finished downloads have their own history.** The queue and the history
  are in two tabs of the manager, and the history is kept between sessions.
  When reopening the window, the progress of downloads in progress is still
  there.
- **Downloads warn when they finish**, whether the manager is open or
  closed, and the queue is no longer forgotten when closing the window.
- **The Downloads folder is always next to the application.** Before it
  depended on where the program was opened from.
- **In downloads, progress is read first.** The columns became progress,
  status and name, which is the order that matters.

### Preferences and shortcuts

- **Preferences is browsed with a list of categories**, not with tabs. With
  a screen reader, the arrows announce each category as you pass through
  it. There are thirteen, arranged by topic.
- **Preferences saves safely and warns if it could not save.** Before it
  wrote directly on the configuration file and announced “Preferences
  saved” no matter what happened. Now, if the disk does not accept the
  write, it says so with the error sound: the options stay applied until
  closing the application, but they will be lost when it closes.
- **Shortcuts are changed in a single step, and applied when you press
  *Save*.** The action button is activated and the combination is pressed,
  without leaving the list. The window warns that the change is applied when
  you press *Save*, and *Cancel* discards it. `Enter` alone leaves the
  action without a shortcut and `Esc` cancels. If the combination is not
  valid or is already in use, the reason is given by voice and in an
  on-screen warning, and the button keeps waiting for another.
- **Reset the shortcuts.** A button at the end of the list returns all
  customizable combinations to their original values, and it is also
  applied when you press *Save*.
- **Three new shortcuts to open windows**: `Ctrl+Shift+P` opens
  Preferences, `Ctrl+Shift+H` the live stream history and `Ctrl+Shift+I`
  marks an incident in the log.
- **Nine options that existed and could not be touched.** How the reading
  queue behaves when the chat speeds up, automatic reconnection, the chat
  panel port, the OBS microphone that the shortcut mutes, and the detailed
  log, which until now was only turned on by editing a file by hand.
- **Number counters can be rewritten without deleting first.** When you
  enter one, its content is selected.
- **New light palette, with cream and sage green tones.** The main window
  now has a minimum size, and long warnings fit the width instead of going
  out of the window.
- **The texts that the screen reader reads have their accents.** Fifteen
  were written without them, so they were heard badly pronounced: “maxímo”
  for “máximo”, “transmisiòn” for “transmisión”.
- **Preferences: the Shortcuts category is fully visible.** Before two
  thirds of the buttons were outside the window. Now the window can be
  enlarged.
- **Windows high contrast mode is respected.** The application stopped
  applying its fixed colors over the system theme.

### Data and installation

- **Data moves on its own to the `data` folder.** The configuration,
  credentials, history, aliases, scheduled messages and logs were next to
  the program. When opening the new version, those files move to the `data`
  folder without doing anything. The Downloads folder stays next to the
  program.
- **The files that the application saves are written safely.** This is the
  case of the history, credentials, scheduled messages and OBS
  configuration: a close halfway no longer leaves them empty.
- **Two defects of unexpected closes on exit were addressed.** The player
  left loose ends when closing, which match the abrupt closes that appeared
  in the log. It cannot be considered cured until it is used for a while,
  but the log now leaves a trace of that close instead of staying silent.
- **The detailed log is off.** It is a diagnostic option and it was on by
  default, which made the log file grow without need.
- **The diagnostic log stopped filling with noise.** Nine out of ten lines
  were from internal libraries, and with a long session that noise erased
  the beginning of the file, which is exactly where the problem usually is.
- **The failure file no longer scares.** It collects internal Windows
  events, and many are harmless. Now each startup writes a line that
  explains it and says which is the signal that the session ended well.
- **A black window no longer opens on startup.** It appeared for an instant
  and stole focus from the screen reader. Now the query is done in the
  background.

## 2.0.1, August 2026

A fixes version. It does not bring big new features: it makes the ones that
already existed bother less and warn better.

- **Diagnostics stopped talking on its own.** Every thirty seconds it
  announced by voice how many live threads there were. It was information to
  fix problems, not to listen to while watching a live stream. Now it is
  still saved in the log, but silently.
- **The player controls are no longer mute.** Pressing play, mute or seek
  without a loaded video did absolutely nothing, not even say it. Now they
  answer “No video is loaded” or “The player is not available”, as the case
  may be.
- **The player shortcuts always work.** They were off until you connected
  to something, so the seven Control combinations seemed broken.
- **It warns when you press play.** Before there was a long silence while
  it loaded, which seemed like it had blocked. Now it says “Loading video”.
- **Clear warnings when the network fails.** Before, if YouTube did not
  answer or the video was private, nothing was heard. Now it says it in
  words: that the network is not responding, that the video is not
  available, or that you have to wait a few minutes because too many
  requests were made.
- **Preferences shortcuts are grouped.** The twenty buttons were loose; now
  the reader announces which group each one belongs to, “Player” or
  “Connection and chat”.
- **yt-dlp can be updated from the application.** Tools menu → Update
  yt-dlp. It is the piece that breaks when YouTube changes something
  inside, and until now you had to wait for a new version of the whole
  program. It checks which version is published, compares it with the
  installed one and downloads it only if needed, verifying that the file is
  authentic.
- **Downloads use that same yt-dlp.** Before the download manager carried
  its own copy inside, which stayed old even if you updated. Now everything
  uses the same one, and the version the application shows is the real one.
- **A leak that made the chat read twice inside was fixed.** If you
  reconnected to another live stream without disconnecting first, the
  previous connection stayed alive asking YouTube for messages forever,
  silently, until closing the program.
- **The downloads folder is no longer saved on its own.** A path from the
  machine where the program was built was written into the configuration.
- A menu entry that no longer led anywhere was removed, and warnings also
  come out on the braille line.

## 2.0.0, July 2026

- **TikTok live streams, now polished.** The first version premiered them
  and this one makes them reliable: all comments are read with their
  author, the live stream video is heard, and F2 shows live viewers.
  Optional: read who joins the live stream (off by default, in Preferences
  → Reading).
- **Live stream history** (File menu): saves what you have watched, in two
  tabs (YouTube and TikTok), to return to a live stream with Enter without
  remembering the link. Live streams are marked as such, because when they
  end they may stop existing.
- **Letter search in the chat and comments**: type a few letters in a row
  (“mig”) and jump to the message that starts that way, announcing it. It
  wraps around the list if needed and warns if there are no matches.
- **Second voice for events** (optional): Super Chats, gifts and new
  members can be read with a voice different from the one for messages.
- **Shortcuts captured by pressing them**: in Preferences → Shortcuts you
  no longer write the combination by hand; you press the action button and
  then the keys, and the app checks on its own that it is valid and does not
  clash with another.
- **Configurable spoken status (F2)**: it says the live stream data (title,
  channel, viewers, messages read, contributions…) and in Preferences →
  Status you choose exactly what it counts.
- **Smoother chat with the screen reader**: browsing the list with the
  arrows while messages arrive no longer blocks.
- **Consistent menus**: actions that need a connection are disabled when
  there is none, and disconnecting is instant (before it could freeze the
  window for a few seconds).
- **More robust YouTube reconnection**: a network error that left the
  connection broken until reconnecting by hand now recovers on its own.
- **Polished player**: resuming a live stream after pausing it returns to
  the current moment, full screen carries the video title, and in live
  streams “Live” is shown instead of a confusing progress bar.

## 1.0.0, July 2026

First version. Reading of the YouTube Live chat with SAPI5 voices; video
comments with reading, replying and posting; integrated video player with
keyboard-manageable full screen; moderation and sending to the chat with the
official API; video information tab; and TikTok live streams (read only).
Keyboard-navigable interface, with voice and braille announcements.
