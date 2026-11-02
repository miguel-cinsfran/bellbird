<!-- original: es/MANUAL.md ac59f2140104aa737771ccf0c38b4f2e092dd98d -->
# Bellbird, user manual

This is a translation of the Spanish original, made with artificial intelligence. If you find an error, report it at https://github.com/miguel-cinsfran/bellbird/issues. See the [original in Spanish](../es/MANUAL.md).

Bellbird reads the chat of YouTube and TikTok live streams aloud for people who
are blind or have low vision and stream. The whole application is handled with
the keyboard and tested with NVDA.

Version 2.5.1 · Windows 10 and 11 · [what's new in each version](CHANGELOG.md)

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
- [Where preferences are saved](#where-preferences-are-saved)
- [Common problems](#common-problems)

## What it does

- Reads the chat of a YouTube or TikTok live stream with the Windows or
  ElevenLabs voices, with a different sound for each type of message.
- Reads and posts comments on YouTube videos.
- Plays the live stream video inside the application.
- Plays music from your folder, your playlists or YouTube while you stream.
- Starts and ends your live stream with OBS Studio and describes by voice how
  the scene looks.
- Shows the chat to your viewers in a panel for OBS.
- Moderates, writes in the chat and sends scheduled messages with your Google
  session.
- Downloads video and audio.

On TikTok it only reads, because TikTok has no official way to comment or
moderate.

## Installation

Extract the ZIP to any folder and open `Bellbird.exe`; you do not need to
install anything or have administrator permissions, because the ZIP brings
everything you need.

You need Windows 10 or 11, an internet connection and at least one Windows
voice, which you choose in *Settings, Time & language, Speech*;
ElevenLabs is optional and requires your own account.

## Getting started

When the application opens, the focus is in the *Link or ID* field: paste the
link of the live stream or the video and press `Enter`. If you have already
watched other live streams, the window offers the *Recent items* list
(`Alt+N`). `Enter` opens one, `Delete` removes it from the history, and the
context menu offers to open it, remove it or open the full history.

The window has three regions, *Connection*, *Content* and *Player*, and `F6`
and `Shift+F6` move from one to another, while `Ctrl+Tab` switches between the
chat, comments and information tabs. Each change of region or tab is announced.
The Applications key opens the context menu of the chat or comment list.

## The chat

Each message is read with the chosen voice and sounds different depending on
who writes: channel owner, moderator, verified account or member. It also
changes depending on what it is: Super Chat, membership or TikTok gift.

On TikTok, stickers and live questions are also read. In *Preferences*, on the
*Reading* category, the *Live events* group has one list per event:
*Super Chats and gifts*, *Memberships*, *Live joins*, *Likes*, *New followers*, *Shared live
streams* and *Treasure chests*. Each list chooses between *Main voice*,
*Secondary voice*, *Sound only* and *Off*. *Main voice* and *Secondary voice*
show it in the list, play its sound and read it; *Sound only* shows it and
plays its sound without reading it; *Off* does not show it. By default, joins
and likes are set to *Sound only*, and the rest to *Main voice*. Below *Likes*
there is a counter, *Group likes for, in seconds*, that decides how many
seconds the likes of the same person are grouped before the total is
announced. The secondary voice and its settings are chosen in *Preferences*,
on the *Voices* category. If the streamer pauses the live stream, you hear
“The TikTok live stream is paused.”, and when it resumes, “The TikTok live
stream continues.”, each one with its sound.

In the list, the arrows move from message to message and typing a few letters
jumps to the first author that starts that way. The context menu copies the
message, mutes the author for the session, sets an alias and, with a Google
session, puts the author in timeout or hides the author on the YouTube channel.

### Reading format

The reading format is chosen in *Preferences*, on the *Reading* category, and
decides which part of each message is read.

| Format | Example |
|---|---|
| Name and message | “Lucía: hello everyone” |
| Message then name | “hello everyone, from Lucía” |
| Message only | “hello everyone” |
| Name only | “Lucía” |

The words and users that are not read are configured in *Preferences*, on the
*Filters* category.

### Voices

Bellbird can read the chat with three voice engines: SAPI 5 and OneCore, which
come with Windows, and ElevenLabs, which needs an account. To choose the
engine, the main voice, the speed, the volume and the pitch, open
*Preferences* and go to the *Voices* category. The *Test voice* button plays a
sample before saving. The *Secondary voice* group chooses the voice for the
events set to that mode in *Preferences*, on the *Reading* category: *Voice*,
*Speed (0 to 100)*, *Volume (0 to 100)* and *Test secondary voice*. With
*Same as the main voice*, the secondary voice plays with the main voice and its
own settings. With ElevenLabs, *Backup Windows voice* chooses the voice that
plays if the network fails or the balance runs out, and *Same as the main voice
backup* follows the main voice backup. You can also set a character limit per
session or use ElevenLabs only for important messages. If the network fails or
the balance runs out, the application reads with the Windows voice and warns
you once. The key is saved in `credenciales.json`.

### Alias

The alias is for names that are a combination of letters and numbers. Open the
context menu of a message, choose *Set alias* for <author>… and type how you
want to hear it. The alias also applies to messages that were already there,
and moderation still acts on the real account. To remove it, leave the field
empty.

### Writing in the chat

The writing box comes after the list in the Tab order, and `Alt+Enter` moves
the focus to it from anywhere. `Enter` sends the message and `Shift+Enter`
inserts a line break. If something is missing to be able to write, such as the
Google session or a YouTube live stream with chat, the *Send* button is still
reachable with Tab and its name says what is missing. The limit is 200
characters.

### Sounds

There is a sound for each thing: messages, Super Chats, members, TikTok gifts
by size, followers, joins, the connection, errors and the edge when you reach
the start or the end of a list. `F7` mutes them all. To silence only one, clear
its check box in *Preferences*, on the *Sounds* category, where
*Play the selected sound* plays each one. The sound theme is chosen in the same
category, before the list of check boxes: *Default*, with recorded sounds, or
*Soft*, shorter and softer. To make your own, copy `sounds/themes/default` with another
name and change the `.wav` files, and `sounds/CREDITOS.md` says where each
sound comes from.

### Video comments

With a published video, the comments tab shows the comments and reads them.
With a Google session you can comment and reply.

## Player

The live stream video plays inside the application, with libVLC. Quality is
chosen in the *Player* menu, and the on-screen buttons are hidden from that
menu or from *Preferences*, on the *Player* category.

In a live stream, one-minute jumps add up and say where you land, for example
“40 seconds behind the live stream”. With YouTube's separate tracks you can go
back up to an hour, and `Ctrl+End` returns to the live stream. In a video, the
position slider arrows move ten seconds.

The *Play sound only, without the picture* check box, in *Preferences*, on the
*Player* category, is checked. With it, a recorded video opens a single link
and jumps in less than a second, and the quality is not used. If the audio
track is larger than 10 MB, that link has somewhat lower sound quality.
Cleared, you see the picture and each jump takes a few seconds. In a live
stream the way of connecting does not change: only the picture stops showing.

A TikTok live stream cannot be paused: when you press play or pause, the
application says so and names the Mute audio shortcut, `Ctrl+M`, which
silences it without interrupting it.

The audio of each YouTube video is saved in `data/cache-audio`, so that pausing
and jumping respond instantly, and the last three are kept.

## Music

To play music while you stream, without opening another application, use the
Music folder next to the application, or the one you choose in *Preferences*,
on the *Music* category. Music is handled from the *Music* menu or with the
`Ctrl+Alt` shortcuts (see the [table](#music-ctrlalt)).

The *Music* window (`Ctrl+Shift+M`):

- *Collections*: *Library* is your folder and, next, your playlists, each one
  with how many songs it has (“Library: 195”).
- *Find*: filters while you type, even if you do not type accents.
- *Songs*: `Enter` plays. The context menu plays now, next after the current
  song and without interrupting it, or plays from there to the end. It also
  adds the song to the queue or to a playlist, or creates a new playlist.
- *Show the queue*: what is going to play, in order.
- *Open link…*: a video or a whole YouTube playlist, which is added to the
  queue.
- *Refresh folder*: scans it again and says how many new and deleted songs it
  found.

New songs appear on their own in the list, without choosing the folder again:
the application watches the folder and updates it without warning.

Playlists are saved as `.m3u8` files, which other players can open. When you
reopen the application, Play follows the last queue from where it was and says
how many songs it has, which may not be the whole folder if it was a search.
To always start with the whole folder, turn off
*Remember the last playlist on open* in *Preferences*, on the *Music* category.

In *Preferences*, on the *Music* category, you also choose shuffle, repeat
(nothing, whole queue or current song), music volume and audio output. To
choose what is said when a song changes, you have nothing, the title, the title
and the artist, or only the artist. If you choose nothing, changing songs with
the shortcut still says the title. Another check box decides whether pause,
resume and return to the beginning are announced.

The *Match song volume* check box, on by default, makes all songs sound similar,
as in Spotify. Each file is measured once with ffmpeg and its volume is
corrected when each song starts. The files are not modified: only the result is
saved in a cache. The application never measures on its own, not when reading
the folder, not when saving preferences, not when playing with a shortcut.

When you open the *Music* window, if there are songs not yet measured, the
application asks how many there are and how much space they take, with *Yes*
and *No*. The *Do not ask again* check box saves that it should not ask again,
and the question is turned on or off in *Preferences*, on the *Music* category.
The window has the *Match the volume* button, which starts measuring; while it
measures, the button changes to *Stop matching*. Progress is shown in the
window or with `F2`, and YouTube links play at their own volume.

When one song changes to the next, the end of one fades into the beginning of
the other, without the silence that many files have at the start and end. The
fade length is chosen in *Preferences*, on the *Music* category, in
*Crossfade between songs, in seconds*: from 0 to 12, with 6 by default, and 0
turns it off.
Changing songs with the shortcut makes a short fade, of half a second. The song
change sound is off by default and is turned on in the same category.

The *Use music shortcuts in any application* check box makes the shortcuts work
even when you are in OBS or in a game. It is off because, while it is on, those
keys do not reach the other applications. If another application already uses
one of them, the application tells you which one.

NVDA uses `Ctrl+Alt+arrows` to move through tables. Where it thinks there is a
table, such as the desktop or File Explorer, NVDA keeps those keys and the music
does not receive them. In that case, press `NVDA+F2` and then the shortcut, and
NVDA lets the next key through. In a window without tables, such as Notepad,
the shortcuts work without that.

## Going live

With OBS Studio, the live stream is started and ended from the application: to
YouTube with your Google account, and to TikTok through Restream.

### Before going live for the first time

Before going live for the first time, turn on the OBS WebSocket server in
*Preferences*, on the *Broadcast* category. If OBS is closed, the application
opens it in the notification area without moving the focus away from the screen
reader.

For TikTok you need an OBS profile called `TikTok` with Restream, and for
YouTube, the Google session started and live streams enabled on your channel;
the `YouTube` OBS profile is created by the application.

In the *Broadcast panel* (`Ctrl+Shift+T`), press *Arrange scene…* and choose
which window is captured, for example a game. The live stream shows that
window, but its capture does not carry sound: the sound comes from the desktop
audio and the OBS microphone.

### To go live

To go live, press *Broadcast live*, next to *Connect*.

1. Choose the destination. The one from last time is already chosen, so you
   only need to press `Enter`.
2. The application prepares OBS and checks the scene: destination, format,
   sources, audio and whether something is wrong, such as an empty scene, a
   black image or a muted microphone. If it finds problems, the button chosen
   by default is *Cancel*.
3. For YouTube, in the same window you type the title, the description, the
   privacy and, if you want, the latency, the category, the tags, the thumbnail
   and the playlist. The application remembers everything. *Unlisted* is for
   testing.
4. When the live stream goes on air, the application connects the chat on its
   own and announces it: “Your YouTube live stream is now on air”.
5. During the live stream, the application warns if the connection fails. If
   the internet connection is lost, YouTube waits for it to come back without
   ending the live stream.

The button changes to *End live stream*, which asks for confirmation with
*Keep broadcasting* chosen by default. Closing the application does not
interrupt the live stream: when you come back, the application recognizes it,
and `Alt+Shift+E` copies the live stream link.

`Alt+Shift+M` mutes or turns on the OBS microphone. When you turn it on, the
application says which device it uses, for example “Microphone on: Windows
default, WO Mic Device”. If OBS uses the default device, the microphone is the
one Windows has chosen at that moment and may not be the one you expect. To
keep it from changing, choose the device in the properties of the microphone
source in OBS. After you turn it on, the application listens for three seconds.
If no sound comes in, it plays its own warning and says “The microphone is not
receiving sound. Check which one is chosen in Windows or in OBS.”.

`Ctrl+Shift+O`, or *Show OBS* in the *Broadcast* menu, brings the OBS window to
the front, also when it is in the notification area. If OBS is waiting for an
answer, such as the safe mode question, the focus goes to that dialog box.

### Recording the live stream

With *Record while broadcasting* checked, in the *Broadcast* menu, OBS starts
recording when the broadcast starts well and stops recording when the broadcast
stops. The file is saved in the OBS recordings folder. If you were already
recording, that recording continues as it was, and closing the application does
not interrupt either one. If the recording cannot start, the broadcast
continues and it plays its own warning with “The broadcast started, but the
recording could not start.”. If the OBS profile records with its own encoder,
the check before broadcasting warns at the end, because recording that way
loads the computer twice. In that case, to load it less, choose in OBS that the
recording uses the same quality as the broadcast, and the check box is cleared
by default.

Starting, pausing, resuming and stopping the recording have their own sounds.
With *Show streaming or recording in the title of the window*, in *Preferences*,
on the *Broadcast* category, the title starts with that state, and the check box
is cleared by default.

You can also record without opening the panel. To start or stop recording, use
*Start or stop recording* in the *Broadcast* menu with `Alt+Shift+G`. To pause
or resume, use *Pause or resume recording* with `Alt+Shift+P`, which announce
and sound the same as the panel buttons. If no recording is in progress, pausing
says so and changes nothing in OBS. If OBS does not pause the recording, the
application says so: some profiles may not allow it.

When you stop the recording, from the application or because the broadcast
ended, you hear “Recording saved” with the file name. *Saved recordings…*, in
the *Broadcast* menu and in the panel, lists what was recorded that way, from
newest to oldest. From there you can open the file with `Enter`, open its
folder, copy the path or remove it from the list with `Delete`. Removing it from
the list does not delete the file, and what is stopped from the OBS window does
not appear in the list.

### The broadcast panel

The *Status* field says whether everything is ready or what to check, the
current scene, the microphone and the recording. From the panel the live stream
is started and ended the same way as with the button in the main window. It also
records, mutes or chooses the microphone and changes the current scene. Only
what is useful at that moment appears: *TikTok user* with TikTok,
*Show chat on video* with YouTube and *Pause recording* while recording, and
`Enter` never starts or ends a live stream.

### Arrange scene

The *Arrange scene* window opens from the panel and lets you adjust the scene
sources. The *Scene description* field says each source, where it is, what size
it has and whether something covers it, and the same is heard with `Ctrl+F2`.
Here you can choose which window is captured and move a source to one of the
nine positions, for example *Center*, or change its size. You can also hide it,
lock it, bring it to the front, move it with arrows, save an image of the scene
for someone to see and undo everything done since you opened the window.
Choosing another scene does not change what the viewers see. Each change says
where the source ended up, how much is cropped if it goes outside the video and
what covers it, and the *Help* button explains each control.

Everything can still be done by hand in OBS, and the application does not
interrupt the OBS plugin for NVDA.

## Camera framing

If there is a camera in the live OBS scene, the application says how you look in
it. It reports how many faces there are, whether you are centered, far away,
outside the top or bottom edge, sideways or with your head tilted, whether
there is light in front or backlight, and whether the image froze. Any camera
that OBS shows works: webcam, capture card or the phone used as a camera. The
image is analyzed on the computer and is not sent anywhere.

Left and right are said as the movement you have to make, for example “Move to
your left.”, not as the side of the image.

### Announcing the framing on request

To know the framing at a given moment, press `Ctrl+F3` or choose
*Announce camera framing* in the *Broadcast* menu.

### Automatic warnings

The *Warn when the face leaves the frame* check box, in the *Broadcast* menu, or
`Ctrl+Shift+F3`, turns on the warnings. With the warnings on, the application
warns with its own sound when the face leaves the frame and with another when
it comes back, and says nothing while it stays well. If there is no camera in
OBS or OBS is closed, it waits without doing anything. The check box is
remembered when you open the application again, and with the warnings on, `F2`
also says the camera status.

### Beep guide

Press `Ctrl+F3` twice in a row. The application pauses chat reading and plays
beeps that sound from the side you have to move to. They are higher if you have
to go up, lower if you have to go down and faster the closer you are. When you
are well framed, a confirmation sounds, the framing is said and reading
continues. `Ctrl+F3` stops the guide, which also ends on its own after a minute.

If there is more than one camera in the scene, the one in front is used. The
camera is chosen in *Preferences*, on the *Camera* category, with
*Find cameras in OBS*, without writing anything in `config.ini`. If the left and
right indications come out reversed, check *Invert left and right*. The warnings are
turned on from the same category.

## Chat panel for streaming

It shows the chat large, with a transparent background, for your viewers. It is
added in OBS (or Streamlabs, or Prism Live Studio) as a browser source with this
link:

    http://127.0.0.1:8730/chat

It is turned on with *Show chat on video*, in the *Broadcast panel*, and if the
current scene does not have the source, it adds it. Each message appears on a
card with the initial and a color for each person, and donations in gold with
the amount. It is only used with YouTube: TikTok already shows the comments over
the video.

What does not fit in the video is not broadcast, and a source that is partly
outside is cropped without warning. OBS calls that rectangle the canvas, and
that is why *Arrange scene* says how much is cropped. If another source covers
the panel, the application puts it in front when going on air and tells you
which one was covering it. `F2` says whether the panel is active and whether OBS
is showing it, and the server only listens on your computer.

## Scheduled messages

They send messages to the chat every so often, for example your social networks
every ten minutes. They are configured in *Preferences*, on the
*Scheduled messages* category: each one with its text, its interval (fixed or
variable within a range, from five minutes) and a check box to leave it ready
without sending it.

They only work on your own YouTube live stream and with a Google session. The
first one goes out after the interval, not when connecting, and sending is not
announced, because the message is already read in the chat. `F2` says how long
is left for the next one, and YouTube usually blocks links, so the user name is
better than the link. If YouTube returns an error, the messages stop and a
warning is given once, without retrying.

## Downloads and history

### Download manager

The *Download manager* (`Ctrl+Shift+D`) downloads videos, audio or whole
playlists, in MP4, WebM, MP3 or M4A, with audio at 192, 256 or 320 kbps. It
downloads two at a time, queues the rest and saves the history of what was
downloaded. The Downloads folder is next to the application, and yt-dlp is
updated from *Tools*, *Update yt-dlp*. The update channel is chosen in
*Preferences*, on the *Downloads* category: *Stable*, the default, or *Nightly*,
with fixes earlier and more risk of errors.

`Enter` on a finished download opens the file. With
*Ask whether to open the folder when the queue finishes*, in *Preferences*, on
the *Downloads* category, the application asks one question when the whole
queue finishes, if something downloaded correctly. It is cleared by default, because the question takes the
focus.

In the search box, Space plays the result in the music without downloading it:
it interrupts only the current song and leaves it in the queue as one more, and
Space again pauses it.

### Live stream history

The *Live stream history* (`Ctrl+Shift+H`) shows what you watched, with a tab
for YouTube and another for TikTok, and finished live streams appear marked.

## Spoken status

`F2` summarizes the situation: connection, title, channel, viewers, how long it
has been on air, messages read, donations, the chat panel and scheduled
messages. What goes into the summary is chosen in *Preferences*, on the
*Status (F2)* category, including the OBS data and the song that is playing.
While you stream from the application, `F2` starts with how the live stream is
going. With
the YouTube session started, it also says how many units of the daily quota were
used today from this computer. The number is approximate and resets at midnight,
Pacific time, when Google restores the quota. Because the quota is shared among
those who use the application, it helps to know whether a quota error comes from
your use or from others.

If you press `F2` twice in a row, in under half a second, the *Session status*
window opens with a list: one line for each part of the status, including those
that are not in the spoken summary. Browse it with the arrow keys and close it
with `Esc` or *Close*.

`F3` says who sent the last message read, and `Ctrl+F2` describes the OBS scene.

## Asking the AI

An artificial intelligence looks at a screenshot of OBS and tells you what it
sees: whether the camera is on, whether a source came out black or what text is
on screen. It needs OBS open and a provider key.

### Setting up artificial intelligence

In *Preferences*, on the *Artificial intelligence* category, you choose the
provider (Google Gemini, OpenAI, Anthropic, OpenRouter, OpenCode Go, Command
Code or another compatible with OpenAI), save its key and choose the model. The
key is kept in the Windows Credential Manager, not in `config.ini`, and the
category never shows it: it only says that it is saved and its last four
characters. The *Test the key* button sends a short request and says whether it
works.

The *Refresh model list* button brings the models that accept images. With
OpenRouter and OpenCode Go, the *Free only* check box leaves those that do not
charge. With Gemini, what is free depends on the key, so the list tests each
model with yours and marks the ones that work. It takes about 30 seconds and a
warning sounds in the meantime.

In the same category you change the instruction that goes with each screenshot,
the length of the response, the waiting time and whether “Analyzing…” is said
while it waits.

### The Ask the AI window

`Ctrl+Shift+I` opens the window, where the *Add screenshot* button lets you
choose the live scene or a single source. In the *Message* field you type the
question and `Enter` sends it. Right after adding a screenshot you can leave it
empty, and the instruction is used. The response is read when it arrives and
stays in *Conversation*, where `Enter` opens each full message. You can keep
asking about the same screenshot or add another. `Esc` cancels the request in
progress and, if there is none, closes the window.

### Quick query

`Ctrl+Shift+F2` captures the live scene, sends it with the instruction and reads
the response without opening anything. The next `Ctrl+Shift+I` opens the window
with that conversation, to keep asking.

### Privacy

The screenshot and what you type leave your computer and go to the provider. The
first send warns you and asks for confirmation once. Some models use what they
receive for training, and the list says so next to the name.

If the screenshot comes out black, it is not sent. This usually happens with the
NVDA screen curtain or on a computer with no monitor connected. In OBS, change
the capture method of that source to Windows 10.

## Google session

The Google session is needed to moderate, write in the chat, comment on videos
and create the YouTube live stream. In *Preferences*, on the *API and session*
category, press *Sign in* and authorize in the browser, without creating
anything in Google Cloud. While Google has not finished verifying the
application, it shows an unverified application notice: open the advanced option
and choose to continue.

The daily YouTube quota is shared among those who use the application. To have
your own, follow [the API setup guide](../CONFIGURACION_API.md), written to be
read with a screen reader. Without a session, everything else works the same.

## Keyboard shortcuts

Each family of keys is an area, and that is respected also when customizing the
shortcuts. They all also appear in the menu bar, next to their action.

### Player (Ctrl)

| Shortcut | Action |
|---|---|
| `Ctrl+P` | Play or pause |
| `Ctrl+Left Arrow` / `Right Arrow` | Back or forward 1 minute |
| `Ctrl+Up Arrow` / `Down Arrow` | Raise or lower player volume |
| `Ctrl+End` | Go to live |
| `Ctrl+D` | Stop video |
| `Ctrl+M` | Mute or unmute audio |
| `Ctrl+F` | Full screen |

### Chat (Alt)

| Shortcut | Action |
|---|---|
| `Alt+Enter` | Go to the writing box |

### Windows (Ctrl+Shift)

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+P` | Open Preferences |
| `Ctrl+Shift+H` | Open the live stream history |
| `Ctrl+Shift+T` | Open Broadcast |
| `Ctrl+Shift+D` | Open Download manager |
| `Ctrl+Shift+M` | Open the music window |
| `Ctrl+Shift+I` | Ask the AI about the image |
| `Ctrl+Shift+O` | Show OBS |

### Live stream and OBS (Alt+Shift)

| Shortcut | Action |
|---|---|
| `Alt+Shift+C` | Connect |
| `Alt+Shift+D` | Disconnect |
| `Alt+Shift+L` | Go to the list of the current panel |
| `Alt+Shift+E` | Copy the live stream link |
| `Alt+Shift+I` | Mark an incident |
| `Alt+Shift+M` | Mute the OBS microphone |
| `Alt+Shift+G` | Start or stop recording |
| `Alt+Shift+P` | Pause or resume recording |
| `Alt+Shift+A` | Turn overload warnings on or off |

### Voice and reading (F keys)

| Shortcut | Action |
|---|---|
| `F5` | Pause or resume reading |
| `F8` | Stop current voice |
| `F9` / `F10` | Lower or raise voice speed |
| `F11` / `F12` | Lower or raise voice volume |
| `F4` | Mute reading |
| `F7` | Mute sounds |
| `F2` | Announce the status. Twice in a row, open the list |
| `F3` | Announce the author of the last message |
| `Ctrl+F2` | Describe the OBS scene |
| `Ctrl+Shift+F2` | Quick query to the AI about the scene |
| `Ctrl+F3` | Announce camera framing |
| `Ctrl+Shift+F3` | Warn when the face leaves the frame |

When you repeat a speed or volume adjustment, the first time it says the name
and the value (“Voice volume: 40%”) and after that only the value.

### Music (Ctrl+Alt)

| Shortcut | Action |
|---|---|
| `Ctrl+Alt+Space` | Play or pause the music |
| `Ctrl+Alt+Right Arrow` / `Left Arrow` | Next song or previous song |
| `Ctrl+Alt+Up Arrow` / `Down Arrow` | Raise or lower the music volume |
| `Ctrl+Alt+Shift+Right Arrow` / `Left Arrow` | Fast-forward or rewind the music 10 seconds |
| `Ctrl+Alt+T` | Announce current song |
| `Ctrl+Alt+M` | Mute or restore the music sound |
| `Ctrl+Alt+D` | Stop music |
| `Ctrl+Alt+A` | Shuffle the music |
| `Ctrl+Alt+R` | Change the music repeat mode |

### Fixed

| Shortcut | Action |
|---|---|
| `F6` / `Shift+F6` | Next or previous region |
| `Ctrl+Tab` | Change tab |
| `Alt+F4` | Exit the application |

### Recent chat messages (Ctrl+Shift and a number)

`Ctrl+Shift+1` reads the last chat message, `Ctrl+Shift+2` the one before and so
on up to `Ctrl+Shift+0`, which reads the tenth from the end. By default, these
shortcuts only work with the application in front; the
*Read recent messages in any application* check box in *Preferences*, on the
*Reading* category makes them work in any application, like the music
shortcuts.

In the same category, *Read recent messages with* chooses who reads them: the
screen reader, as it comes by default, or the application voice. With the voice,
the requested message plays as soon as what is being read finishes, and then the
messages that were waiting follow, in their order.

If another application already uses one of these combinations, or the music
ones, a busy tone sounds and the application says which ones.

### Changing a shortcut

In *Preferences*, on the *Shortcuts* category, each action has a button whose
name includes its shortcut. Activate it and press the new combination: `Enter`
only leaves the action without a shortcut and `Esc` cancels. If the combination
does not work for that area or is already used, it says why and the button keeps
waiting. When you capture a `Ctrl+Alt` with a letter, the application checks
whether on your keyboard `AltGr` with that key types something, such as the at
sign, and in that case it asks for another one. The
*Reset shortcuts to factory defaults* button returns everything to factory
defaults, and nothing is saved until you press *Save*.

## Accessibility

Accessibility is the main criterion of the project.

- Each control has an accessible name and is reached with Tab or with arrows.
- The menu bar is the native Windows one.
- What the application announces on its own goes by voice, by braille and with
  its own sound.
- It is tested with NVDA on Windows 10 and 11.

The chat panel for streaming is the only part that does not receive focus,
because it is for the viewers, and the accessible chat is the list in the main
window.

## Updating

The *Help*, *Check for updates* command says whether there is a new version,
shows what is new and installs it. The download is checked with its signature,
and the application closes and opens again on its own in about a minute. The
`data` folder, downloads and your sounds are kept, and if the new version does
not open, it goes back to the previous one on its own. When it starts, a new
version is announced once. If there are other versions between the installed
one and the new one, the window shows what is new in all of them, from newest to
oldest, each one with its heading.

In *Preferences*, on the *General* category, *Update channel* chooses which
versions are offered. *Stable*, the factory option, offers only stable versions,
and *Beta* also offers test versions, which may bring defects.

## Where preferences are saved

Almost everything is in *Preferences*, in the *Tools* menu, and it is saved when
you press *Save*, while *Cancel* discards it. Preferences live in
`data/config.ini` and `data/sounds.ini`, which can be edited with Notepad and are
regenerated if they are deleted.

## Common problems

### No voices

Add a voice in *Settings, Time & language, Speech*, or try the OneCore engine in
*Preferences*, on the *Voices* category. Windows 11 neural voices do not appear
in SAPI 5: *TTSVoicePatcher* exposes them.

### “Windows protected your PC”

This notice is SmartScreen, because the executable is not signed. Choose
*More information*, *Run anyway*.

### The antivirus warns

It is a common false positive with applications distributed this way, without an
installer, so add the folder to the exclusions.

### The chat panel is not visible

`F2` says whether the panel is active and whether OBS shows it. If nobody shows
it, check the browser source in OBS.

### If something does not work

The *Help*, *Open logs folder* command opens the `data` folder, where the logs
are. Errors are saved in `data/bellbird.log`, and if the application closes on
its own, also in `data/bellbird-fallos.log`. The detailed log,
`data/bellbird-debug.log`, is on by default; it is turned off in *Preferences*,
on the *General* category, with the *Save a detailed log for diagnosing errors*
check box. To report an error, reproduce the problem and send the three files.

## License

Bellbird uses the GPL-3.0 license from version 2.5.1, and you can read
[LICENSE](../../LICENSE). Versions up to 2.5.0 were published with the MIT
license.
