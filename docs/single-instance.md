# Single Instance

By default, launching your app twice starts two independent processes. Enable
single-instance mode to allow only one, and to route a second launch's arguments —
typically a deep link — to the copy already running.

```python
app = App(title="My App", single_instance=True)
```

## What happens

1. The first process becomes the **primary** and listens on a loopback socket.
2. A later launch finds the primary, hands it `sys.argv`, and exits.
3. The primary fires its `deeplink` hooks with any custom-scheme URL in that argv,
   exactly as it would at startup.

```python
@app.on("deeplink")
def handle(url: str):
    # Fires whether the app was launched with this URL or already running.
    print("open", url)
```

`app.run()` returns immediately without opening a window when another instance
exists, so `if __name__ == "__main__": app.run()` needs no extra handling.

## Design

| Decision | Why |
|---|---|
| Loopback TCP, not a named mutex | A mutex proves another instance exists but carries no payload, and forwarding argv is the point |
| Loopback TCP, not a Unix socket | One code path across Windows, macOS and Linux |
| Messages carry a random token | Loopback is reachable by every local process; without it any program could inject a deep link into your app |
| Lock file created `0600` | The token is what authenticates a client, so it must stay private to your user |
| Stale locks detected by connecting | A lock left by a crash names a port nobody is listening on; only a successful handshake proves a live primary |
| Lock failure never blocks startup | The app runs unguarded rather than refusing to start |

The lock file lives in `$XDG_RUNTIME_DIR/<app>/instance.lock` on Linux, or the app's
config directory on macOS and Windows.

## Related

- [Deep Linking](deeplink.md) — registering the URL scheme with the OS
