# Module 17: WebSockets

## Overview

WebSockets provide full-duplex, persistent communication over a single TCP connection. Unlike HTTP's request-response model, WebSockets allow both client and server to send messages at any time. This module covers the WebSocket protocol, handshake, framing, and building WebSocket servers.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Explain the WebSocket protocol and its advantages
2. Implement the WebSocket handshake
3. Parse and create WebSocket frames
4. Build a WebSocket server from scratch
5. Handle ping/pong, close, and fragmentation

---

## 17.1 WebSocket Protocol Overview

### Why WebSockets?

HTTP limitations for real-time:
- Request-response only (client initiates)
- Connection overhead (new connection per request)
- Header overhead (repeated headers)
- Polling wastes resources

WebSocket advantages:
- Bidirectional (server can push)
- Persistent connection
- Low overhead (2-14 byte frame header)
- Real-time communication

### Protocol Flow

```
Client                                      Server
   │                                           │
   │─────── HTTP Upgrade Request ─────────────▶│
   │                                           │
   │◀────── HTTP 101 Switching Protocols ──────│
   │                                           │
   │═══════════ WebSocket Connection ══════════│
   │                                           │
   │◀──────────── Server Message ──────────────│
   │                                           │
   │─────────── Client Message ───────────────▶│
   │                                           │
   │◀──────────── Server Message ──────────────│
   │                                           │
   │─────────── Close Frame ──────────────────▶│
   │◀────────── Close Frame ───────────────────│
   │                                           │
```

---

## 17.2 The WebSocket Handshake

### Client Request

```http
GET /chat HTTP/1.1
Host: server.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Sec-WebSocket-Protocol: chat, superchat
Origin: http://example.com
```

### Server Response

```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
Sec-WebSocket-Protocol: chat
```

### Key Calculation

```python
import hashlib
import base64

WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

def calculate_accept_key(client_key: str) -> str:
    """Calculate Sec-WebSocket-Accept from client key."""
    combined = client_key + WEBSOCKET_GUID
    sha1_hash = hashlib.sha1(combined.encode()).digest()
    return base64.b64encode(sha1_hash).decode()

# Example
client_key = "dGhlIHNhbXBsZSBub25jZQ=="
accept_key = calculate_accept_key(client_key)
# Result: "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
```

### Handshake Implementation

```python
def perform_handshake(client_socket) -> bool:
    """Perform WebSocket handshake."""
    # Read HTTP request
    data = b''
    while b'\r\n\r\n' not in data:
        chunk = client_socket.recv(4096)
        if not chunk:
            return False
        data += chunk

    # Parse headers
    headers = parse_http_headers(data.decode())

    # Validate WebSocket upgrade
    if headers.get('upgrade', '').lower() != 'websocket':
        return False
    if 'sec-websocket-key' not in headers:
        return False

    # Calculate accept key
    client_key = headers['sec-websocket-key']
    accept_key = calculate_accept_key(client_key)

    # Send response
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_key}\r\n"
        "\r\n"
    )
    client_socket.send(response.encode())
    return True

def parse_http_headers(data: str) -> dict:
    """Parse HTTP headers into dict."""
    headers = {}
    lines = data.split('\r\n')
    for line in lines[1:]:
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip().lower()] = value.strip()
    return headers
```

---

## 17.3 WebSocket Frame Format

### Frame Structure

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
|     Extended payload length continued, if payload len == 127  |
+ - - - - - - - - - - - - - - - +-------------------------------+
|                               |Masking-key, if MASK set to 1  |
+-------------------------------+-------------------------------+
| Masking-key (continued)       |          Payload Data         |
+-------------------------------- - - - - - - - - - - - - - - - +
:                     Payload Data continued ...                :
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
|                     Payload Data continued ...                |
+---------------------------------------------------------------+
```

### Opcodes

| Opcode | Type | Description |
|--------|------|-------------|
| 0x0 | Continuation | Fragment continuation |
| 0x1 | Text | UTF-8 text data |
| 0x2 | Binary | Binary data |
| 0x8 | Close | Connection close |
| 0x9 | Ping | Keep-alive ping |
| 0xA | Pong | Ping response |

### Frame Parser

```python
import struct
from dataclasses import dataclass
from typing import Optional
from enum import IntEnum


class Opcode(IntEnum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA


@dataclass
class WebSocketFrame:
    fin: bool
    opcode: Opcode
    payload: bytes

    @property
    def is_control(self) -> bool:
        return self.opcode >= 0x8


class FrameParser:
    """WebSocket frame parser."""

    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes):
        """Add data to buffer."""
        self.buffer.extend(data)

    def parse_frame(self) -> Optional[WebSocketFrame]:
        """Parse a single frame from buffer."""
        if len(self.buffer) < 2:
            return None

        # First byte: FIN + opcode
        first_byte = self.buffer[0]
        fin = bool(first_byte & 0x80)
        opcode = Opcode(first_byte & 0x0F)

        # Second byte: MASK + payload length
        second_byte = self.buffer[1]
        masked = bool(second_byte & 0x80)
        payload_len = second_byte & 0x7F

        # Calculate header size
        header_size = 2

        # Extended payload length
        if payload_len == 126:
            if len(self.buffer) < 4:
                return None
            payload_len = struct.unpack('!H', self.buffer[2:4])[0]
            header_size = 4
        elif payload_len == 127:
            if len(self.buffer) < 10:
                return None
            payload_len = struct.unpack('!Q', self.buffer[2:10])[0]
            header_size = 10

        # Mask key (if present)
        if masked:
            mask_start = header_size
            mask_end = header_size + 4
            if len(self.buffer) < mask_end:
                return None
            mask_key = self.buffer[mask_start:mask_end]
            header_size += 4

        # Check if we have full payload
        total_size = header_size + payload_len
        if len(self.buffer) < total_size:
            return None

        # Extract payload
        payload = bytes(self.buffer[header_size:total_size])

        # Unmask if necessary
        if masked:
            payload = self._unmask(payload, mask_key)

        # Remove parsed data from buffer
        del self.buffer[:total_size]

        return WebSocketFrame(fin=fin, opcode=opcode, payload=payload)

    def _unmask(self, data: bytes, mask_key: bytes) -> bytes:
        """Unmask payload data."""
        return bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))


class FrameBuilder:
    """WebSocket frame builder."""

    @staticmethod
    def build(opcode: Opcode, payload: bytes,
              fin: bool = True, mask: bool = False) -> bytes:
        """Build a WebSocket frame."""
        frame = bytearray()

        # First byte: FIN + opcode
        first_byte = (0x80 if fin else 0x00) | opcode
        frame.append(first_byte)

        # Payload length
        length = len(payload)
        if length < 126:
            frame.append((0x80 if mask else 0x00) | length)
        elif length < 65536:
            frame.append((0x80 if mask else 0x00) | 126)
            frame.extend(struct.pack('!H', length))
        else:
            frame.append((0x80 if mask else 0x00) | 127)
            frame.extend(struct.pack('!Q', length))

        # Mask key (for client frames)
        if mask:
            import os
            mask_key = os.urandom(4)
            frame.extend(mask_key)
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        frame.extend(payload)
        return bytes(frame)

    @staticmethod
    def text(data: str, fin: bool = True) -> bytes:
        """Build text frame."""
        return FrameBuilder.build(Opcode.TEXT, data.encode('utf-8'), fin)

    @staticmethod
    def binary(data: bytes, fin: bool = True) -> bytes:
        """Build binary frame."""
        return FrameBuilder.build(Opcode.BINARY, data, fin)

    @staticmethod
    def close(code: int = 1000, reason: str = '') -> bytes:
        """Build close frame."""
        payload = struct.pack('!H', code) + reason.encode('utf-8')
        return FrameBuilder.build(Opcode.CLOSE, payload)

    @staticmethod
    def ping(data: bytes = b'') -> bytes:
        """Build ping frame."""
        return FrameBuilder.build(Opcode.PING, data)

    @staticmethod
    def pong(data: bytes = b'') -> bytes:
        """Build pong frame."""
        return FrameBuilder.build(Opcode.PONG, data)
```

---

## 17.4 Complete WebSocket Server

```python
"""
Complete WebSocket server implementation.
"""

import asyncio
import hashlib
import base64
import struct
from dataclasses import dataclass
from typing import Optional, Set, Callable, Awaitable
from enum import IntEnum


WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class Opcode(IntEnum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA


@dataclass
class WebSocketFrame:
    fin: bool
    opcode: Opcode
    payload: bytes


class WebSocketConnection:
    """Single WebSocket connection handler."""

    def __init__(self, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.closed = False
        self.buffer = bytearray()
        self._fragments = []
        self._fragment_opcode = None

    async def handshake(self) -> bool:
        """Perform WebSocket handshake."""
        try:
            # Read HTTP request
            data = b''
            while b'\r\n\r\n' not in data:
                chunk = await self.reader.read(4096)
                if not chunk:
                    return False
                data += chunk

            # Parse headers
            headers = self._parse_headers(data.decode())

            # Validate
            if headers.get('upgrade', '').lower() != 'websocket':
                return False

            client_key = headers.get('sec-websocket-key')
            if not client_key:
                return False

            # Calculate accept key
            combined = client_key + WEBSOCKET_GUID
            accept_key = base64.b64encode(
                hashlib.sha1(combined.encode()).digest()
            ).decode()

            # Send response
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key}\r\n"
                "\r\n"
            )
            self.writer.write(response.encode())
            await self.writer.drain()
            return True

        except Exception:
            return False

    def _parse_headers(self, data: str) -> dict:
        headers = {}
        for line in data.split('\r\n')[1:]:
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        return headers

    async def recv(self) -> Optional[tuple[Opcode, bytes]]:
        """Receive a complete message."""
        while not self.closed:
            frame = await self._read_frame()
            if frame is None:
                return None

            # Handle control frames
            if frame.opcode == Opcode.CLOSE:
                await self._handle_close(frame)
                return None
            elif frame.opcode == Opcode.PING:
                await self._send_frame(Opcode.PONG, frame.payload)
                continue
            elif frame.opcode == Opcode.PONG:
                continue

            # Handle data frames
            if frame.opcode != Opcode.CONTINUATION:
                self._fragment_opcode = frame.opcode
                self._fragments = [frame.payload]
            else:
                self._fragments.append(frame.payload)

            if frame.fin:
                message = b''.join(self._fragments)
                opcode = self._fragment_opcode
                self._fragments = []
                self._fragment_opcode = None
                return (opcode, message)

        return None

    async def send(self, data: str | bytes):
        """Send a message."""
        if isinstance(data, str):
            await self._send_frame(Opcode.TEXT, data.encode('utf-8'))
        else:
            await self._send_frame(Opcode.BINARY, data)

    async def close(self, code: int = 1000, reason: str = ''):
        """Close the connection."""
        if not self.closed:
            payload = struct.pack('!H', code) + reason.encode('utf-8')
            await self._send_frame(Opcode.CLOSE, payload)
            self.closed = True
            self.writer.close()
            await self.writer.wait_closed()

    async def _read_frame(self) -> Optional[WebSocketFrame]:
        """Read a single frame."""
        try:
            # Read header
            header = await self.reader.readexactly(2)

            fin = bool(header[0] & 0x80)
            opcode = Opcode(header[0] & 0x0F)
            masked = bool(header[1] & 0x80)
            payload_len = header[1] & 0x7F

            # Extended length
            if payload_len == 126:
                ext = await self.reader.readexactly(2)
                payload_len = struct.unpack('!H', ext)[0]
            elif payload_len == 127:
                ext = await self.reader.readexactly(8)
                payload_len = struct.unpack('!Q', ext)[0]

            # Mask key
            mask_key = None
            if masked:
                mask_key = await self.reader.readexactly(4)

            # Payload
            payload = await self.reader.readexactly(payload_len)

            # Unmask
            if masked:
                payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

            return WebSocketFrame(fin=fin, opcode=opcode, payload=payload)

        except asyncio.IncompleteReadError:
            return None

    async def _send_frame(self, opcode: Opcode, payload: bytes, fin: bool = True):
        """Send a single frame."""
        frame = bytearray()

        # First byte
        frame.append((0x80 if fin else 0x00) | opcode)

        # Length (server doesn't mask)
        length = len(payload)
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.append(126)
            frame.extend(struct.pack('!H', length))
        else:
            frame.append(127)
            frame.extend(struct.pack('!Q', length))

        frame.extend(payload)

        self.writer.write(bytes(frame))
        await self.writer.drain()

    async def _handle_close(self, frame: WebSocketFrame):
        """Handle close frame."""
        if not self.closed:
            # Echo close frame
            await self._send_frame(Opcode.CLOSE, frame.payload)
            self.closed = True
            self.writer.close()


class WebSocketServer:
    """WebSocket server with connection management."""

    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
        self.host = host
        self.port = port
        self.connections: Set[WebSocketConnection] = set()
        self._on_connect: Optional[Callable] = None
        self._on_message: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None

    def on_connect(self, handler: Callable[[WebSocketConnection], Awaitable]):
        """Register connect handler."""
        self._on_connect = handler
        return handler

    def on_message(self, handler: Callable[[WebSocketConnection, str | bytes], Awaitable]):
        """Register message handler."""
        self._on_message = handler
        return handler

    def on_disconnect(self, handler: Callable[[WebSocketConnection], Awaitable]):
        """Register disconnect handler."""
        self._on_disconnect = handler
        return handler

    async def handle_client(self, reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter):
        """Handle a client connection."""
        conn = WebSocketConnection(reader, writer)

        # Perform handshake
        if not await conn.handshake():
            writer.close()
            return

        self.connections.add(conn)

        try:
            # Call connect handler
            if self._on_connect:
                await self._on_connect(conn)

            # Message loop
            while not conn.closed:
                result = await conn.recv()
                if result is None:
                    break

                opcode, data = result
                if self._on_message:
                    if opcode == Opcode.TEXT:
                        await self._on_message(conn, data.decode('utf-8'))
                    else:
                        await self._on_message(conn, data)

        finally:
            self.connections.discard(conn)
            if self._on_disconnect:
                await self._on_disconnect(conn)

    async def broadcast(self, message: str | bytes):
        """Send message to all connections."""
        for conn in list(self.connections):
            try:
                await conn.send(message)
            except Exception:
                pass

    async def run(self):
        """Start the server."""
        server = await asyncio.start_server(
            self.handle_client,
            self.host, self.port
        )

        print(f"WebSocket server on ws://{self.host}:{self.port}")

        async with server:
            await server.serve_forever()


# Usage example
async def main():
    server = WebSocketServer(port=8080)

    @server.on_connect
    async def on_connect(conn):
        print(f"Client connected")
        await conn.send("Welcome!")

    @server.on_message
    async def on_message(conn, message):
        print(f"Received: {message}")
        # Echo back
        await conn.send(f"Echo: {message}")
        # Broadcast to all
        await server.broadcast(f"Someone said: {message}")

    @server.on_disconnect
    async def on_disconnect(conn):
        print(f"Client disconnected")

    await server.run()


if __name__ == '__main__':
    asyncio.run(main())
```

---

## 17.5 WebSocket Close Codes

### Standard Close Codes

| Code | Name | Description |
|------|------|-------------|
| 1000 | Normal | Clean close |
| 1001 | Going Away | Endpoint going away |
| 1002 | Protocol Error | Protocol error |
| 1003 | Unsupported | Unsupported data type |
| 1006 | Abnormal | No close frame (internal) |
| 1007 | Invalid Data | Invalid UTF-8 |
| 1008 | Policy Violation | Policy violation |
| 1009 | Message Too Big | Message too large |
| 1010 | Missing Extension | Required extension missing |
| 1011 | Internal Error | Server error |

### Handling Close

```python
async def handle_close(self, frame: WebSocketFrame):
    """Parse and handle close frame."""
    code = 1005  # No status code
    reason = ""

    if len(frame.payload) >= 2:
        code = struct.unpack('!H', frame.payload[:2])[0]
        reason = frame.payload[2:].decode('utf-8', errors='replace')

    print(f"Close: {code} - {reason}")

    # Send close response
    if not self.closed:
        response = struct.pack('!H', code)
        await self._send_frame(Opcode.CLOSE, response)
        self.closed = True
```

---

## 17.6 Ping/Pong Keep-Alive

```python
class WebSocketConnection:
    """Connection with ping/pong support."""

    def __init__(self, ...):
        ...
        self._ping_task = None
        self._last_pong = time.time()

    async def start_ping(self, interval: float = 30.0, timeout: float = 10.0):
        """Start ping keep-alive."""
        self._ping_task = asyncio.create_task(
            self._ping_loop(interval, timeout)
        )

    async def _ping_loop(self, interval: float, timeout: float):
        """Send periodic pings."""
        while not self.closed:
            await asyncio.sleep(interval)

            # Check if pong received
            if time.time() - self._last_pong > interval + timeout:
                await self.close(1000, "Ping timeout")
                return

            # Send ping
            await self._send_frame(Opcode.PING, b'keepalive')

    async def _handle_pong(self, frame: WebSocketFrame):
        """Handle pong response."""
        self._last_pong = time.time()
```

---

## 17.7 Message Fragmentation

```python
class WebSocketConnection:
    """Connection with fragmentation support."""

    async def send_large(self, data: bytes, chunk_size: int = 65536):
        """Send large message in fragments."""
        opcode = Opcode.BINARY
        offset = 0

        while offset < len(data):
            chunk = data[offset:offset + chunk_size]
            is_first = offset == 0
            is_last = offset + chunk_size >= len(data)

            frame_opcode = opcode if is_first else Opcode.CONTINUATION
            await self._send_frame(frame_opcode, chunk, fin=is_last)

            offset += chunk_size

    async def recv_fragmented(self) -> Optional[bytes]:
        """Receive fragmented message."""
        fragments = []

        while True:
            frame = await self._read_frame()
            if frame is None:
                return None

            fragments.append(frame.payload)

            if frame.fin:
                return b''.join(fragments)
```

---

## 17.8 WebSocket Subprotocols

```python
async def handshake_with_subprotocol(self,
                                      supported: list[str]) -> Optional[str]:
    """Handshake with subprotocol negotiation."""
    # ... read request ...

    # Get requested protocols
    protocols_header = headers.get('sec-websocket-protocol', '')
    requested = [p.strip() for p in protocols_header.split(',')]

    # Find match
    selected = None
    for proto in requested:
        if proto in supported:
            selected = proto
            break

    # Build response
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_key}\r\n"
    )

    if selected:
        response += f"Sec-WebSocket-Protocol: {selected}\r\n"

    response += "\r\n"

    # ...
    return selected
```

---

## 17.9 WebSocket in ASGI

```python
async def websocket_app(scope, receive, send):
    """ASGI WebSocket application."""
    if scope['type'] != 'websocket':
        return

    # Wait for connection
    message = await receive()
    if message['type'] != 'websocket.connect':
        return

    # Accept connection
    await send({
        'type': 'websocket.accept',
        'subprotocol': None
    })

    try:
        while True:
            message = await receive()

            if message['type'] == 'websocket.receive':
                text = message.get('text')
                data = message.get('bytes')

                # Echo
                if text:
                    await send({
                        'type': 'websocket.send',
                        'text': f'Echo: {text}'
                    })
                elif data:
                    await send({
                        'type': 'websocket.send',
                        'bytes': data
                    })

            elif message['type'] == 'websocket.disconnect':
                break

    except Exception:
        await send({
            'type': 'websocket.close',
            'code': 1011
        })
```

---

## 17.10 Real-World Example: Chat Room

```python
"""
WebSocket chat room server.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Dict, Set


@dataclass
class User:
    conn: 'WebSocketConnection'
    name: str
    room: str


class ChatServer:
    """Multi-room chat server."""

    def __init__(self):
        self.rooms: Dict[str, Set[User]] = {}
        self.users: Dict[WebSocketConnection, User] = {}

    async def handle_connection(self, conn: WebSocketConnection):
        """Handle new connection."""
        user = None

        try:
            while True:
                result = await conn.recv()
                if result is None:
                    break

                _, data = result
                message = json.loads(data.decode())

                msg_type = message.get('type')

                if msg_type == 'join':
                    user = await self.handle_join(conn, message)
                elif msg_type == 'message' and user:
                    await self.handle_message(user, message)
                elif msg_type == 'leave' and user:
                    await self.handle_leave(user)
                    user = None

        finally:
            if user:
                await self.handle_leave(user)

    async def handle_join(self, conn: WebSocketConnection,
                         message: dict) -> User:
        """Handle join room."""
        name = message['name']
        room = message['room']

        user = User(conn=conn, name=name, room=room)
        self.users[conn] = user

        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(user)

        # Notify room
        await self.broadcast_to_room(room, {
            'type': 'user_joined',
            'name': name,
            'users': [u.name for u in self.rooms[room]]
        })

        return user

    async def handle_message(self, user: User, message: dict):
        """Handle chat message."""
        await self.broadcast_to_room(user.room, {
            'type': 'message',
            'from': user.name,
            'text': message['text']
        })

    async def handle_leave(self, user: User):
        """Handle leave room."""
        self.users.pop(user.conn, None)

        if user.room in self.rooms:
            self.rooms[user.room].discard(user)

            if not self.rooms[user.room]:
                del self.rooms[user.room]
            else:
                await self.broadcast_to_room(user.room, {
                    'type': 'user_left',
                    'name': user.name,
                    'users': [u.name for u in self.rooms[user.room]]
                })

    async def broadcast_to_room(self, room: str, message: dict):
        """Send message to all users in room."""
        if room not in self.rooms:
            return

        data = json.dumps(message)
        for user in list(self.rooms[room]):
            try:
                await user.conn.send(data)
            except Exception:
                pass


# Run chat server
async def main():
    chat = ChatServer()

    async def handle_client(reader, writer):
        conn = WebSocketConnection(reader, writer)
        if await conn.handshake():
            await chat.handle_connection(conn)

    server = await asyncio.start_server(handle_client, '0.0.0.0', 8080)
    print("Chat server on ws://localhost:8080")

    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())
```

---

## Exercises

### Exercise 17.1: Binary Protocol

Implement a WebSocket server that handles binary messages with a custom protocol:
- First 4 bytes: message type (uint32)
- Next 4 bytes: payload length (uint32)
- Remaining: payload data

### Exercise 17.2: Rate Limiting

Add rate limiting to the WebSocket server:
- Max 10 messages per second per connection
- Close connection if exceeded

### Exercise 17.3: Compression

Implement per-message deflate compression (permessage-deflate extension).

---

## Summary

You've mastered WebSockets:

1. **Handshake**: HTTP upgrade to WebSocket
2. **Framing**: Parse and build WebSocket frames
3. **Opcodes**: Text, binary, close, ping, pong
4. **Control flow**: Ping/pong, close handshake
5. **Fragmentation**: Large message handling
6. **Real-time apps**: Chat rooms, live updates

---

## Next Module

**[Module 18: Performance Engineering →](./MODULE_18_PERFORMANCE.md)**
