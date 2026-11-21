# Apple TV plugin: HomeKitLink talk to Apple TV / HomePod

HomeKitLink Siri 0.8.50 can send the Home app's camera **talk** to an Apple TV or HomePod as a live
AirPlay stream ("Talk through" in a camera's HomeKitLink settings). It works with **Apple TV plugin
1.8.8 as it is**. This note says what HomeKitLink relies on, and the changes that would make it better.

## How it works

1. You press talk on a camera in the Home app. HomeKitLink's audio proxy decrypts your voice.
2. HomeKitLink's ffmpeg turns it into a live **MP3 stream (320 kbps, 44.1 kHz stereo)**, served from the
   Indigo Mac: `http://<mac-ip>:<port>/talk-<token>.mp3`. The URL is new for every live view, and the token
   stops anything else on the network from finding it.
3. When the first audio is ready, HomeKitLink runs the Apple TV plugin's **Send Command** action:

   ```python
   atv = indigo.server.getPlugin("com.GlennNZ.indigoplugin.appleTV")
   atv.executeAction("sendCommand", props={"appleTV": str(device_id), "command": "stream_file", "args": url})
   ```

   That reaches `_handle_device_command` → pyatv `stream_file(url)`, the same path *Speak Announcement*
   uses for its MP3. pyatv's `InternetSource` is an internet-radio (IceCast) client, so it plays a
   **live** HTTP stream until the stream ends.
4. When you stop talking for 2.5 s, HomeKitLink ends the HTTP stream, so `stream_file` finishes and the
   device stops. The next talk starts a new stream and a new Send Command.

## What HomeKitLink relies on (please keep stable)

| | |
|---|---|
| Plugin id | `com.GlennNZ.indigoplugin.appleTV` |
| Action | `sendCommand` with props `appleTV` (device id as a string), `command`, `args`, where `command=stream_file`, `args=<url>` |
| Argument parsing | `_extract_command_with_args` splits on `,`. The URL never contains a comma |
| Destinations | Apple TV plugin devices whose **`RAOPPort` state is > 0**: they take AirPlay audio (Apple TV, HomePod) |
| Device address | The `IP` device prop. Used to pick the Mac's address on the route to the device |

## Delay (measured on the HomeKitLink side; AirPlay part from pyatv's code)

- HomeKitLink: about 0.6 s from the first talk packet to the Send Command (ffmpeg starting).
- pyatv reads 32 KB before playing (`HEADROOM_SIZE`): about 0.8 s at 320 kbps. That's why the bitrate is
  high; at 64 kbps it would be 4 s.
- AirPlay's own latency in pyatv: `22050 + sample_rate` frames, about **1.5 s**.
- Expect **2-3 s** from speaking to hearing it, steady for the whole talk.

## Suggested Apple TV plugin changes (optional, in order of value)

1. **Replace a running stream instead of colliding with it.** If you talk again within about 2 s of
   stopping, a new `stream_file` can arrive while the last one is still draining pyatv's buffer. Keep the
   stream task per device manager, and cancel it before starting a new one:

   ```python
   # in the device manager (where send_command creates the task)
   def send_command(self, command, args, **kwargs):
       task = self.loop.create_task(self._handle_device_command(args, command))
       if command.startswith("stream_file"):
           old, self._stream_task = getattr(self, "_stream_task", None), task
           if old is not None and not old.done():
               old.cancel()   # pyatv stops the old AirPlay session
   ```

2. **A dedicated action for other plugins**, so HomeKitLink doesn't depend on Send Command's generic
   parsing, plus a stop action:

   ```xml
   <Action id="streamAudioURL" uiPath="hidden">
       <Name>Stream Audio URL</Name>
       <CallbackMethod>streamAudioURL</CallbackMethod>
   </Action>
   <Action id="stopAudioStream" uiPath="hidden">
       <Name>Stop Audio Stream</Name>
       <CallbackMethod>stopAudioStream</CallbackMethod>
   </Action>
   ```

   ```python
   def streamAudioURL(self, action):
       """props: appleTV (device id), url, volume (optional, 0-100)."""
       dev_id, url = int(action.props["appleTV"]), action.props["url"]
       for mgr in self.appleTVManagers:
           if int(mgr.device_ID) == dev_id:
               mgr.send_command("stream_file=" + url, url)   # or call stream_file directly, as in (1)
               return
       self.logger.warning(f"Stream: Apple TV device {dev_id} isn't connected")

   def stopAudioStream(self, action):
       ...  # cancel the device manager's _stream_task, as in (1)
   ```

   If you add these, tell HomeKitLink: it will use `streamAudioURL` when it exists, and fall back to `sendCommand`.

3. **Quieter logging for streams.** `sendRemoteCommand` logs `Sending Command stream_file=http://…` at INFO
   on every talk. Debug level for `stream_file` (or for the new action) keeps the log tidy; HomeKitLink
   logs the talk itself.

4. **A device state for AirPlay audio**, e.g. `supportsAudioStream` (true when RAOP was found). Today
   HomeKitLink uses `RAOPPort > 0`, which works but is indirect.

5. **Volume (later):** a `volume` prop on the stream action (pyatv `set_volume` before streaming) so talk
   isn't too quiet or loud on a HomePod at music volume.

## Notes

- A HomePod or Apple TV that's playing music stops it for the talk; it doesn't resume afterwards.
- Talk to AirPlay is one-way: the visitor's reply comes back through the camera's own microphone, live.
- If the Apple TV plugin is disabled or the device isn't connected, HomeKitLink logs a warning and the
  camera's video and sound carry on.
