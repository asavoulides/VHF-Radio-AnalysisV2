# pip install websocket-client websockets
import asyncio
import sys
import time

HOST = "192.168.10.183"
PORT = 100
PATH = "/"  # change if your WS endpoint isn't root, e.g. "/ws"
URL = f"ws://{HOST}:{PORT}{PATH}"

COOKIE = "option2=0; ws3=x6JRQLjNxreydthGb1ynXw=="
ORIGIN = f"http://{HOST}:{PORT}"

# ProScan payload (note the escaped backslash)
PAYLOAD_TEXT = "C,4,\\?control=Volume,decrement"

# How many times to send the command
REPEAT_COUNT = 40


def send_volume_down(ws):
    """Send the volume down command REPEAT_COUNT times."""
    for i in range(REPEAT_COUNT):
        ws.send(PAYLOAD_TEXT)
        print(f"Sent volume down {i+1}/{REPEAT_COUNT}")
        time.sleep(0.1)  # small delay so the server doesn’t choke


def try_websocket_client_variant(header=None, origin=None, label=""):
    from websocket import create_connection, WebSocketTimeoutException

    ws = None
    try:
        ws = create_connection(
            URL,
            header=header or [],
            origin=origin,
            timeout=5,
            enable_multithread=True,
        )
        send_volume_down(ws)  # <--- changed
        try:
            _ = ws.recv()
        except WebSocketTimeoutException:
            pass
        print(f"[websocket-client:{label}] Success")
        return True
    finally:
        if ws:
            ws.close()


async def try_websockets_variant(extra_headers=None, origin=None, label=""):
    import websockets

    headers = []
    if extra_headers:
        if isinstance(extra_headers, dict):
            headers.extend(list(extra_headers.items()))
        else:
            headers.extend(extra_headers)

    async with websockets.connect(
        URL, extra_headers=headers, origin=origin, close_timeout=1
    ) as ws:
        for i in range(REPEAT_COUNT):
            await ws.send(PAYLOAD_TEXT)
            print(f"Sent volume down {i+1}/{REPEAT_COUNT}")
            await asyncio.sleep(0.1)
        try:
            reply = await asyncio.wait_for(ws.recv(), timeout=1.0)
            print(f"[websockets:{label}] Got reply: {reply!r}")
        except Exception:
            pass
        print(f"[websockets:{label}] Success")
        return True


def main():
    # Try websocket-client and websockets variants in order, same as before...
    try:
        if try_websocket_client_variant(label="no-headers"):
            return
    except Exception as e:
        print(f"[websocket-client:no-headers] {e}")

    try:
        if try_websocket_client_variant(origin=ORIGIN, label="origin-only"):
            return
    except Exception as e:
        print(f"[websocket-client:origin-only] {e}")

    try:
        if try_websocket_client_variant(
            header=[f"Cookie: {COOKIE}"], label="cookie-only"
        ):
            return
    except Exception as e:
        print(f"[websocket-client:cookie-only] {e}")

    try:
        if try_websocket_client_variant(
            header=[f"Cookie: {COOKIE}"], origin=ORIGIN, label="origin+cookie"
        ):
            return
    except Exception as e:
        print(f"[websocket-client:origin+cookie] {e}")

    try:
        asyncio.run(try_websockets_variant(label="no-headers"))
        return
    except Exception as e:
        print(f"[websockets:no-headers] {e}")

    try:
        asyncio.run(try_websockets_variant(origin=ORIGIN, label="origin-only"))
        return
    except Exception as e:
        print(f"[websockets:origin-only] {e}")

    try:
        asyncio.run(
            try_websockets_variant(
                extra_headers=[("Cookie", COOKIE)], label="cookie-only"
            )
        )
        return
    except Exception as e:
        print(f"[websockets:cookie-only] {e}")

    try:
        asyncio.run(
            try_websockets_variant(
                extra_headers=[("Cookie", COOKIE)], origin=ORIGIN, label="origin+cookie"
            )
        )
        return
    except Exception as e:
        print(f"[websockets:origin+cookie] {e}")

    print("All handshake variants failed.", file=sys.stderr)
    sys.exit(1)


def lower_system_volume():
    print(f"Lowering system volume by sending {REPEAT_COUNT} commands to {URL}")
    main()
