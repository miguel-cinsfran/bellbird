<!-- original: es/MANUAL.md 77cf5ba9c2e1219ec33921ba98c2110cad85bb8e -->
# Bellbird, user manual

This is a translation of the Spanish original, made with artificial intelligence. If you find an error, report it at https://github.com/miguel-cinsfran/bellbird/issues. See the [original in Spanish](../es/MANUAL.md).

Reads the chat of YouTube and TikTok live streams aloud, for people who are
blind or have low vision and stream. Everything is handled with the keyboard
and tested with NVDA.

Version 2.4.0 · Windows 10 and 11 · [what's new in each version](CHANGELOG.md)

## Contents

- [What it does](#what-it-does)
- [Installation](#installation)
- [Getting started](#getting-started)
- [The chat](#the-chat)
- [Player](#player)
- [Music](#music)
- [Going live](#going-live)
- [Camera framing](#camera-framing)
- [Chat panel for streaming](#chat-panel-for-streaming)
- [Scheduled messages](#scheduled-messages)
- [Downloads and history](#downloads-and-history)
- [Spoken status](#spoken-status)
- [Asking the AI](#asking-the-ai)
- [Google session](#google-session)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [Accessibility](#accessibility)
- [Updating](#updating)
- [Configuration](#configuration)
- [Common problems](#common-problems)

## What it does

- Reads the chat of a YouTube or TikTok live stream with the Windows or
  ElevenLabs voices, with a different sound for each type of message.
- Reads and posts comments on YouTube videos.
- Plays the live stream video inside the application.
- Plays music from your folder, your playlists or YouTube while you
  stream.
- Starts and ends your live stream with OBS Studio, and describes by voice
  how the scene looks.
- Shows the chat to your viewers in a panel for OBS.
- Moderates, writes in the chat and sends scheduled messages, with your
  Google session.
- Downloads video and audio.

On TikTok it only reads: TikTok has no official way to comment or
moderate.

## Installation

Extract the ZIP to any folder and open `Bellbird.exe`. You do not need to
install anything or have administrator permissions: the ZIP brings
everything you need.

You need Windows 10 or 11, internet and at least one Windows voice (in
*Settings, Time & language, Speech*). ElevenLabs is optional and requires
your own account.

## Getting started

When the application opens, the focus is in the address field. Paste the
link of the live stream or the video and press Enter. If you have already
watched other live streams, the window offers the *Recent items* list
(`Alt+N`). Enter opens one, `Delete` removes it from the history, and the
context menu offers to open it, remove it or open the full history.

The window has three regions: connection, content and player. `F6` and
`Shift+F6` move from one to another, and `Ctrl+Tab` switches between the
chat, comments and information tabs. Each change is announced. The
Applications key opens the context menu of the chat or comment list.

## The chat

Each message is read with the chosen voice and sounds different depending on
who writes (channel owner, moderator, verified account, member) and on what
it is (Super Chat, membership, TikTok gift).

On TikTok, stickers and live questions are also read. In
*Preferences, Reading*, each TikTok notice (joins, likes, followers,
shares and treasure chests) has its mode: *Sound and speech* shows it in
the list, plays its sound and reads it; *Sound only* shows it and plays
its sound without reading it; *Off* does not show it. By default,
joins and likes are set to *Sound only*, and followers, shares and
treasure chests to *Sound and speech*. If the streamer pauses the live
stream, you hear “The TikTok live stream is paused.”, and when it resumes,
“The TikTok live stream continues.”, each one with its sound.

In the list, the arrows move from message to message and typing a few
letters jumps to the first author that starts that way. The context menu
copies the message, mutes the author for the session, sets an alias and,
with a Google session, puts them in timeout or hides them.

**Reading format**, in *Preferences, Reading*:

| Format | Example |
|---|---|
| Name and message | “Lucía: hello everyone” |
| Message then name | “hello everyone, from Lucía” |
| Message only | “hello everyone” |
| Name only | “Lucía” |

*Preferences, Filters* holds the words and users that are not read.

**Voices.** In *Preferences, Voices* you choose the engine (SAPI 5,
OneCore or ElevenLabs), the voice, the speed, the volume and the pitch, and
*Test voice* lets you hear it before saving. You can use a second voice for
Super Chats, gifts, memberships and joins. With ElevenLabs you can set a
character limit per session or use it only for important messages. If the
network fails or the balance runs out, it reads with the Windows voice and
warns you once. The key is saved in `credenciales.json`.

**Alias.** For names that are a string of letters and numbers: context menu
on a message, *Set alias*, and type how you want to hear it. It also works
for messages that were already there. Moderation still acts on the real
account. To remove it, leave the field empty.

**Writing in the chat.** Below the list is the writing box, or `Alt+Enter`
from anywhere. `Enter` sends and `Shift+Enter` inserts a line break. If
something is missing to be able to write (Google session, a YouTube live
stream with chat), the *Send* button is still reachable with Tab and its
name says what is missing. The limit is 200 characters.

**Sounds.** There is one for each thing: messages, Super Chats, members,
TikTok gifts by size, followers, joins, the connection, errors, and the
edge when you reach the start or the end of a list. `F7` mutes them all.
To silence only one, clear its check box in *Preferences, Sounds*, where
*Hear the selected sound* lets you hear each one. The sound theme is
chosen in the same category, above the list: `default`, with recorded
sounds, or `suave`, shorter and softer. To make your own, copy
`sounds/themes/default` with another name and change the `.wav` files.
`sounds/CREDITOS.md` says where each sound comes from.

**Video comments.** With a published video, the comments tab shows and
reads them. With a Google session you can comment and reply.

## Player

The live stream video plays inside the application, with libVLC. Quality is
chosen in the *Player* menu, and the on-screen buttons are hidden from that
menu or from *Preferences, Player*.

In a live stream, one-minute jumps add up and say where you land: “40
seconds behind the live stream”. With YouTube's separate tracks you can go
back up to an hour. `Ctrl+End` returns to the live stream. In a video, the
position slider arrows move ten seconds.

*Play sound only, without the picture*, in *Preferences, Player*, is checked.
With it, a recorded video opens a single audio link and jumps in less than
half a second, and the quality is not used. Cleared, you see the picture and
each jump takes a few seconds. In a live stream the way of connecting does not
change: only the picture stops showing.

A TikTok live stream cannot be paused: when you press play or pause, the
application says so and names the Mute audio shortcut, `Ctrl+M`, which
silences it without stopping it.

The audio of each YouTube video is saved in `data/cache-audio`, so that
pausing and jumping respond instantly. The last three are kept.

## Music

To play music while you stream, without opening another program. It uses
the Music folder next to the program, or the one you choose in
*Preferences, Music*. It is handled from the *Music* menu or with the
`Ctrl+Alt` shortcuts (see the [table](#music-ctrlalt)).

The *Music* window (`Ctrl+Shift+M`):

- **Collections**: *Library* is your folder, and below it are your
  playlists, each one with how many songs it has (“Library: 195”).
- **Find**: filters while you type, even if you do not type accents.
- **Songs**: Enter plays. The context menu plays now, next after the
  current song without cutting it, from there to the end, adds it to the
  queue or to a playlist, or creates a new playlist.
- **Show the queue**: what is going to play, in order.
- **Open link…**: a video or a whole YouTube playlist, which is added to
  the queue.
- **Refresh folder**: scans it again and says how many new and deleted
  songs it found.

New songs appear on their own in the list, without choosing the folder
again: the application watches it and updates it silently.

Playlists are saved as `.m3u8` files, which other players can open. When
you reopen the application, Play follows the last queue from where it was,
and says how many songs it has: if it was a search, it is not the whole
folder. To always start with the whole folder, turn off *Remember the last
playlist on open* in *Preferences, Music*.

In *Preferences, Music* you also choose shuffle, repeat (nothing, whole
queue or current song), music volume, audio output and what is said when a
song changes: nothing, the title, the title and the artist, or only the
artist. If you choose nothing, changing songs with the shortcut still says
the title. Another check box decides whether pause, resume and return to
the beginning are announced.

The *Match song volume* check box, on by default, makes all songs sound
similar, as in Spotify. Each file is measured once with ffmpeg, and its
volume is corrected when each song starts. The files are not modified:
only the result is saved in a cache. The application never measures on its
own: not when reading the folder, not when saving preferences, not when
playing with a shortcut.

When you open the *Music* window, if there are songs not yet measured, the
application asks how many there are and how much space they take, with
*Yes* and *No*. The *Do not ask again* check box saves that it should not
ask again, and the question is turned on or off in *Preferences, Music*.
The window has the *Match the volume* button, which starts measuring; while
it measures, the button changes to *Stop matching*. Progress is shown in
the window or with F2. YouTube links play at their own volume.

When one song changes to the next, the end of one fades into the beginning
of the other, without the silence that many files have at the start and
end. The fade length is chosen in *Preferences, Music*, in *Crossfade
between songs, in seconds*: from 0 to 12, with 6 by default, and 0 turns it
off. Changing songs with the shortcut makes a short fade, of half a second.
The song change sound is off by default and is turned on in the same
category.

The *Use music shortcuts in any application* check box makes them work
even when you are in OBS or in a game. It is off because, while it is on,
those keys do not reach other programs. If another program already uses
one, the application tells you which.

NVDA uses `Ctrl+Alt+arrows` to move through tables. Where it thinks there
is a table, such as the desktop or File Explorer, it keeps those keys and
the music does not receive them. There, press `NVDA+F2` and then the
shortcut: NVDA lets the next key through. In a window without tables, such
as Notepad, they work without that.

## Going live

With OBS Studio, the live stream is started and ended from the application:
to YouTube with your Google account, and to TikTok through Restream.

**Once:**

- Turn on the OBS websocket server in *Preferences, Broadcast*. If OBS is
  closed, the application opens it in the notification area without
  taking focus from the screen reader.
- For TikTok, an OBS profile called `TikTok` with Restream.
- For YouTube, the Google session started and live streams enabled on your
  channel. The application creates the OBS `YouTube` profile.
- In the *Broadcast* window (`Ctrl+Shift+T`), *Scene* section, choose
  which window is captured, for example a game. The live stream shows that
  window, but its capture carries no sound: sound comes from the desktop
  audio and the OBS microphone.

**Each time:** press **Broadcast live**, next to *Connect*.

1. Choose the destination. The one from last time is already selected, so
   Enter is enough.
2. The application prepares OBS and checks the scene: destination, format,
   sources, audio, and whether something is wrong, such as an empty scene,
   a black image or a muted microphone. If it finds problems, the button
   selected by default is *Cancel*.
3. For YouTube, in the same window you set the title, description,
   privacy and, if you want, latency, category, tags, thumbnail and
   playlist. Everything is remembered. *Unlisted* is useful for testing.
4. When the live stream goes live, the application connects the chat on its
   own and announces it: “Your YouTube live stream is already live”.
5. During the live stream it warns if the connection fails. If the internet
   drops, YouTube waits for it to return without ending the live stream.

The button changes to **End live stream**, which asks for confirmation with
*Keep broadcasting* selected by default. Closing the application does not
end the live stream: when you return, it recognizes it. `Alt+Shift+E`
copies the live stream link.

`Alt+Shift+M` mutes or unmutes the OBS microphone. When you unmute it, it
says which device it uses, for example “Microphone on: Windows default,
WO Mic Device”. If OBS uses the default, the microphone is the one Windows
has selected at that moment, and it may not be the one you expect. To keep
it from changing, choose the device in the properties of the microphone
source in OBS.
After unmuting, the application listens for three seconds. If no sound
comes in, a sound of its own plays and it says “The microphone is getting
no sound. Check which one is chosen in Windows or in OBS.”.

`Ctrl+Shift+O`, or *Show OBS* in the *Broadcast* menu, brings the OBS
window to the front, also when it is in the notification area. If OBS is
waiting for an answer, such as the safe mode question, focus goes to that
box.

**Recording the live stream.** With *Record while broadcasting* checked,
in the *Broadcast* menu, OBS starts recording when the broadcast starts
well, and stops recording when the broadcast stops. The file goes to the
OBS recordings folder. If you were already recording, that recording
continues as it was, and closing the application does not cut either of
them. If recording cannot start, the broadcast continues and a sound of its
own plays with “Broadcasting started, but recording could not start.”.
If the OBS profile records with its own encoder, the check before
broadcasting warns at the end, because recording that way puts twice the
load on the computer. In that case, to reduce the load, choose in OBS that
recording use the same quality as the broadcast. The check box is
unchecked.

Starting, pausing, resuming and stopping a recording have their own sounds.
With *Show streaming or recording in the title of the window*, in
*Preferences, Broadcast*, the title starts with that status. It is unchecked.

**How the scene looks.** The *Broadcast* window describes each source from
front to back: where it is, what size it has and whether something covers
it. The same is heard with `Ctrl+F2`. From there you can move a source to
one of nine positions (for example, bottom right), change its size, hide
it, pin it, bring it forward, move it with arrows in fine adjustment, save
a snapshot of the scene for someone to see, record, and undo everything
done since you opened the window. Each change says where the source ended
up, how much is cropped if it goes past the edge and how much another
source covers it.

Everything can still be done by hand in OBS, and the application does not
bother the OBS plugin for NVDA.

## Camera framing

If there is a camera in the OBS live scene, the app says how you look in
it: how many faces there are, whether you are centered, far away, outside
the top or bottom edge, to the side or with your head tilted, whether there
is not enough light in front or there is backlight, and whether the image
froze. Any camera that OBS shows works: webcam, capture card or the phone
used as a camera. The image is analyzed on the computer and is not sent
anywhere.

Left and right are said as the movement you have to make, for example
“Move to your left.”, not as the side of the image.

**On request.** `Ctrl+F3`, or *Announce camera framing* in the *Broadcast*
menu, says the framing at that moment.

**Automatic warnings.** `Ctrl+Shift+F3`, or the *Warn when the face leaves
the frame* check box in the same menu, turns on the warnings. With them on,
the app warns with a sound of its own when the face leaves the frame and
with another when it returns, and says nothing while it stays well. If
there is no camera in OBS or OBS is closed, it waits silently. The check
box is remembered when you reopen the app. With warnings on, `F2` also
says the camera status.

**Guiding with beeps.** Press `Ctrl+F3` twice in a row. The app pauses
chat reading and emits beeps that sound from the side toward which you have
to move, higher if you have to go up and lower if you have to go down, and
more frequent the closer you are. When you are well framed, a confirmation
plays, the framing is said and reading continues. `Ctrl+F3` stops the
guide, which also ends on its own after a minute.

If there is more than one camera in the scene, the one in front is used.
The camera is chosen in *Preferences, Camera*, with *Find cameras in OBS*,
without writing anything in `config.ini`. If the left and right
indications come out reversed, check *Invert left and right*. The warnings
are turned on from the same category.

## Chat panel for streaming

Shows the chat large, on a transparent background, for your viewers.
It is added in OBS (or Streamlabs, or Prism Live Studio) as a browser source
with this address:

    http://127.0.0.1:8730/chat

It is turned on in the *Broadcast* window. Each message appears on a card
with the initial and a color per person, and donations in gold with the
amount. It is only used with YouTube: TikTok already shows comments over
the video.

What does not fit on the OBS canvas is not broadcast, and a source that is
partly outside is cropped without warning. That is why the *Broadcast*
window says how much is cropped. If another source covers the panel, the
application brings it forward when going live and tells you which one was
covering it. `F2` says whether the panel is active and whether OBS is
showing it. The server only listens on your computer.

## Scheduled messages

They send messages to the chat every so often, for example your social
networks every ten minutes. They are configured in *Preferences, Scheduled
messages*: each one with its text, its interval (fixed or variable within a
range, from five minutes) and a check box to prepare it without sending it.

They only work on your own YouTube live stream and with a Google session.
The first one goes out after the interval, not when connecting. Sending is
not announced, because the message is already read in the chat. `F2` says
how long until the next one. YouTube usually blocks links: better the
username than the address. If YouTube returns an error, they stop and a
warning is given once, without retrying.

## Downloads and history

**Download manager** (`Ctrl+Shift+D`): videos, audio or whole playlists,
in MP4, WebM, MP3 or M4A, with audio at 192, 256 or 320 kbps. It downloads
two at a time and queues the rest. It keeps the history of what was
downloaded. The Downloads folder is next to the program. yt-dlp is updated
from *Tools, Update yt-dlp*. The channel for that update is chosen in
*Preferences, Downloads*: *Stable*, the default, or *Nightly*, with fixes
sooner and more risk of failures.

Enter on a finished download opens the file. With *Ask whether to open the
folder when the queue finishes*, in *Preferences, Downloads*, the app asks one
question when the whole queue finishes, if something downloaded correctly. It
is unchecked, because the question takes the focus.

In the search, Spacebar plays the result in the music player without
downloading it. It cuts only the current song and stays in the queue like any
other. Spacebar again pauses it.

**Live stream history** (`Ctrl+Shift+H`): what you watched, with one tab
for YouTube and another for TikTok. Ended live streams are marked.

## Spoken status

`F2` summarizes the situation: connection, title, channel, viewers, how
long it has been live, messages read, donations, the chat panel and
scheduled messages. What goes into the summary is chosen in *Preferences,
Status (F2)*, including OBS data and the song that is playing. While you
stream from the application, `F2` starts with how the live stream is
going. With the YouTube session started, it also says how many units of
the daily quota were used today from this computer, with an approximate
number that resets at midnight, Pacific time, when Google restores the
quota. Because the quota is shared among those who use the application, it
helps to know whether a quota error comes from your use or from others'.

`F3` says who sent the last message read, and `Ctrl+F2` describes the OBS
scene.

## Asking the AI

An AI looks at an OBS screenshot and tells you what is shown: whether the
camera is on, whether a source came out black, what text is on screen. It
needs OBS open and a provider key.

**Setting it up.** In *Preferences, Artificial intelligence* you choose the
provider (Google Gemini, OpenAI, Anthropic, OpenRouter, OpenCode Go,
Command Code or another OpenAI-compatible one), save its key and choose the
model. The key is kept in Windows Credential Manager, not in `config.ini`,
and the category never shows it: it only says that it is saved and its last
four characters. *Test the key* sends a short request and says whether it
works.

*Refresh model list* brings the models that accept images.
With OpenRouter and OpenCode Go, *Free only* leaves the ones that do not
charge. With Gemini what is free depends on the key, so the list tests each
model with yours and marks the ones that work. It takes about 30 seconds
and a sound plays meanwhile.

In the same category you change the instruction that accompanies each
screenshot, the response length, the time to wait and whether
“Analyzing…” is said while it waits.

**The window.** `Ctrl+Shift+I` opens it. *Add screenshot* lets you choose
the live scene or a single source. In *Message* you write the question and
`Enter` sends it. Right after adding a screenshot you can leave it empty,
and the instruction is used. The response is read when it arrives and stays
in *Conversation*, where `Enter` opens each full message. You can keep
asking about the same screenshot or add another. `Esc` cancels the current
request, and if there is none, closes the window.

**Quick question.** `Ctrl+Shift+F2` captures the live scene, sends it with
the instruction and reads the response without opening anything. The next
`Ctrl+Shift+I` opens the window with that conversation, to keep asking.

**Privacy.** The screenshot and what you type leave your computer toward
the provider. The first send warns about it and asks for confirmation only
once. Some models use what they receive for training, and the list says so
next to the name.

If the screenshot comes out black, it is not sent. This usually happens
with the NVDA screen curtain or on a computer without a monitor connected.
In OBS, change the capture method of that source to Windows 10.

## Google session

It is needed to moderate, write in the chat, comment on videos and create
the YouTube live stream. In *Preferences, API and session*, press *Sign
in* and authorize in the browser. You do not need to create anything in
Google Cloud. While Google has not finished verifying the application, it
shows an unverified app warning: open the advanced option and choose to
continue.

The daily YouTube quota is shared among those who use the application.
To have your own, follow [the API configuration guide](../CONFIGURACION_API.md)
(in Spanish), written to be read with a screen reader. Without a session,
everything else works the same.

## Keyboard shortcuts

Each family of keys is an area, and it is respected also when you customize
them. They all appear as well in the menu bar, next to their action.

### Player (Ctrl)

| Shortcut | Action |
|---|---|
| `Ctrl+P` | Play or pause |
| `Ctrl+Left arrow` / `Right arrow` | Rewind or fast forward one minute |
| `Ctrl+Up arrow` / `Down arrow` | Player volume |
| `Ctrl+End` | Go to live |
| `Ctrl+D` | Stop |
| `Ctrl+M` | Mute audio |
| `Ctrl+F` | Full screen |

### Chat (Alt)

| Shortcut | Action |
|---|---|
| `Alt+Enter` | Go to the writing box |

### Windows (Ctrl+Shift)

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+P` | Preferences |
| `Ctrl+Shift+H` | Live stream history |
| `Ctrl+Shift+T` | Broadcast |
| `Ctrl+Shift+D` | Download manager |
| `Ctrl+Shift+M` | Music |
| `Ctrl+Shift+I` | Ask the AI about the image |
| `Ctrl+Shift+O` | Show OBS |

### Live stream and OBS (Alt+Shift)

| Shortcut | Action |
|---|---|
| `Alt+Shift+C` | Connect |
| `Alt+Shift+D` | Disconnect |
| `Alt+Shift+L` | Go to the messages list |
| `Alt+Shift+E` | Copy the live stream link |
| `Alt+Shift+I` | Mark an incident in the log |
| `Alt+Shift+M` | Mute or unmute the OBS microphone |
| `Alt+Shift+A` | Turn overload warnings on or off |

### Voice and reading (F keys)

| Shortcut | Action |
|---|---|
| `F5` | Pause or resume reading |
| `F8` | Cut the current sentence |
| `F9` / `F10` | Voice speed |
| `F11` / `F12` | Voice volume |
| `F4` | Mute reading |
| `F7` | Mute sounds |
| `F2` | Status |
| `F3` | Author of the last message read |
| `Ctrl+F2` | Describe OBS scene |
| `Ctrl+Shift+F2` | Quick AI question about the scene |
| `Ctrl+F3` | Announce camera framing |
| `Ctrl+Shift+F3` | Warn when the face leaves the frame |

When you repeat a speed or volume adjustment, the first time it says the
name and the value (“Voice volume: 40%”) and after that only the value.

### Music (Ctrl+Alt)

| Shortcut | Action |
|---|---|
| `Ctrl+Alt+Spacebar` | Play or pause |
| `Ctrl+Alt+Right arrow` / `Left arrow` | Next or previous song |
| `Ctrl+Alt+Up arrow` / `Down arrow` | Music volume |
| `Ctrl+Alt+Shift+Right arrow` / `Left arrow` | Fast forward or rewind 10 seconds |
| `Ctrl+Alt+T` | What is playing |
| `Ctrl+Alt+M` | Mute the music |
| `Ctrl+Alt+D` | Stop music |
| `Ctrl+Alt+A` | Random order |
| `Ctrl+Alt+R` | Change repeat |

### Fixed

| Shortcut | Action |
|---|---|
| `F6` / `Shift+F6` | Change region |
| `Ctrl+Tab` | Change tab |
| `Alt+F4` | Exit |

### Recent chat messages (Ctrl+Shift and a number)

`Ctrl+Shift+1` reads the last chat message, `Ctrl+Shift+2` the one before
it and so on up to `Ctrl+Shift+0`, which reads the tenth from the end. By
default they work only with the application in front; the *Read recent
messages in any application* check box in *Preferences, Reading* makes
them work in any application, like the music shortcuts.

In the same category, *Read recent messages with* chooses who reads them:
the screen reader, as it comes by default, or the application voice. With
the voice, the requested message plays as soon as what is being read ends,
and then the messages that were waiting follow, in their order.

If another program already uses one of these combinations, or the music
ones, a busy tone plays and the application says which ones.

### Changing a shortcut

In *Preferences, Shortcuts*, each action has a button whose name includes
its shortcut. Activate it and press the new combination. `Enter` alone
leaves the action without a shortcut and `Esc` cancels. If the combination
does not work for that area or is already used, it says why and the button
keeps waiting. When capturing a `Ctrl+Alt` with a letter, the application
checks whether on your keyboard `AltGr` with that key writes something,
such as the at sign, and in that case asks for another one. *Reset* returns
everything to factory defaults. Nothing is saved until you press *Save*.

## Accessibility

It is the main criterion of the project.

- Each control has an accessible name and is reached with Tab or with the
  arrows.
- The menu bar is the native Windows one.
- What the application warns on its own goes by voice, by braille and with
  a sound of its own.
- It is tested with NVDA on Windows 10 and 11.

The chat panel for streaming is the only part that does not receive focus,
because it is for the viewers. The accessible chat is the list in the main
window.

## Updating

*Help, Check for updates* says whether there is a new version, shows its
what's new and installs it: the download is checked with its signature, the
application closes and reopens by itself in about a minute. The `data`
folder, downloads and your sounds are kept. If the new version does not
open, it returns by itself to the previous one. On startup, a new version is
announced only once. If there are other versions between the installed one
and the new one, the window shows the what's new of all of them, from the
newest to the oldest, each with its heading.

## Configuration

Almost everything is in *Tools, Preferences*. It is saved when you press
*Save* and *Cancel* discards it. The settings live in `data/config.ini`
and `data/sounds.ini`, which can be edited with Notepad and are regenerated
if deleted.

## Common problems

**No voices.** Add one in *Settings, Time & language, Speech*, or try the
OneCore engine in *Preferences, Voices*. Windows 11 neural voices do not
show up in SAPI 5: *TTSVoicePatcher* exposes them.

**“Windows protected your PC”.** It is SmartScreen, because the executable
is not signed. Choose *More info, Run anyway*.

**The antivirus warns.** It is a common false positive with programs
distributed this way, without an installer. Add the folder to the
exclusions.

**The chat panel is not visible.** `F2` says whether the panel is active
and whether OBS shows it. If nobody shows it, check the browser source in
OBS.

**Something fails.** *Help, Open logs folder* opens the `data` folder,
where the logs are. Errors stay in `data/bellbird.log`, and if the
application closes by itself, also in `data/bellbird-fallos.log`. The
detailed log, `data/bellbird-debug.log`, is on by default; it is turned
off in *Preferences, General*, with the *Save a detailed log for
diagnosing failures* check box. To report a failure, reproduce the
problem and send the three files.

## License

GPL-3.0 since 2.5.1. See [LICENSE](../../LICENSE). Versions up to 2.5.0
were released under the MIT license.
