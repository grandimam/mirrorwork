# Module 2: Socket Programming Fundamentals

## Overview

A socket is the programmer's interface to the network. Every web server, every web client, every networked application—they all use sockets. In this module, you'll move from understanding protocols abstractly to manipulating them directly in Python.

By the end of this module, you'll have written a TCP server and client from scratch, understood what happens inside the kernel when you call socket functions, and built the foundation for everything that follows.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Explain what a socket is at the kernel level (file descriptors, buffers)
2. Use the complete socket API: socket(), bind(), listen(), accept(), connect(), recv(), send(), close()
3. Understand and configure socket options (SO_REUSEADDR, SO_REUSEPORT, TCP_NODELAY)
4. Implement blocking and non-blocking socket operations
5. Distinguish between address families and socket types
6. Build a working echo server and client
7. Debug socket-level issues using system tools

---

## 2.1 What is a Socket?

### The Conceptual Model

A socket is an endpoint for communication. Think of it as a combination of:
- An IP address (which machine)
- A port number (which application on that machine)
- A protocol (TCP or UDP)

### The Kernel Reality

In Unix-like systems (Linux, macOS), a socket is a **file descriptor**—an integer that references a kernel data structure.

```
User Space                    Kernel Space
───────────────────────────────────────────────────────
                              ┌──────────────────────┐
  fd = 3 ──────────────────▶  │   Socket Structure   │
                              │  ──────────────────  │
                              │  Local IP:Port       │
                              │  Remote IP:Port      │
                              │  State (ESTABLISHED) │
                              │  Receive Buffer ───────▶ [incoming data]
                              │  Send Buffer    ───────▶ [outgoing data]
                              │  Options             │
                              └──────────────────────┘
```

When you call `recv()`, you're reading from the receive buffer. When you call `send()`, you're writing to the send buffer. The kernel handles actually moving data across the network.

### File Descriptors

Everything in Unix is a file—including sockets. Standard file descriptors:

| fd | Name | Purpose |
|----|------|---------|
| 0 | stdin | Standard input |
| 1 | stdout | Standard output |
| 2 | stderr | Standard error |
| 3+ | (varies) | Files, sockets, pipes, etc. |

```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print(sock.fileno())  # Prints the file descriptor number, e.g., 3
```

### Kernel Buffers

Each socket has two buffers managed by the kernel:

**Receive Buffer (SO_RCVBUF):**
- Holds incoming data from the network
- When you call `recv()`, data is copied from here to your application
- If full, kernel tells sender to slow down (TCP flow control)

**Send Buffer (SO_SNDBUF):**
- Holds outgoing data waiting to be transmitted
- When you call `send()`, data is copied from your application to here
- `send()` returns when data is in the buffer, NOT when it reaches the destination

```
Your Code                    Kernel                     Network
─────────────────────────────────────────────────────────────────

send(data) ───────▶ [Send Buffer] ───────────────────▶ packets out
                         │
                         │ (kernel sends when ready,
                         │  handles retransmissions)

recv() ◀─────────── [Recv Buffer] ◀─────────────────── packets in
                         │
                         │ (kernel reassembles,
                         │  handles ACKs)
```

---

## 2.2 The Socket API

### Creating a Socket: socket()

```python
import socket

# Create a TCP socket (IPv4)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Create a UDP socket (IPv4)
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Create a TCP socket (IPv6)
sock6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
```

Parameters:
- **family**: Address family (AF_INET for IPv4, AF_INET6 for IPv6, AF_UNIX for local)
- **type**: Socket type (SOCK_STREAM for TCP, SOCK_DGRAM for UDP)
- **proto**: Protocol (usually 0, auto-selected based on type)

### Binding to an Address: bind()

For servers, we need to specify which address and port to listen on:

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind to all interfaces on port 8080
sock.bind(('0.0.0.0', 8080))

# Bind to localhost only on port 8080
sock.bind(('127.0.0.1', 8080))

# Bind to a specific interface
sock.bind(('192.168.1.100', 8080))

# Let the OS choose an available port
sock.bind(('0.0.0.0', 0))
print(sock.getsockname())  # See what port was assigned
```

**Address meanings:**
- `0.0.0.0` — All IPv4 interfaces (external and local)
- `127.0.0.1` — Loopback only (localhost)
- `::` — All IPv6 interfaces
- `::1` — IPv6 loopback

### Listening for Connections: listen()

After binding, tell the kernel we're ready to accept connections:

```python
sock.listen(128)  # backlog of 128 pending connections
```

**The backlog parameter:**

This is the size of the **pending connection queue**—connections that have completed the TCP handshake but haven't been `accept()`ed yet.

```
                    ┌─────────────────────────────────────────┐
                    │           Pending Connection Queue       │
  New connection ─▶ │  [conn1] [conn2] [conn3] ... [connN]    │ ─▶ accept()
  (completed         │                                         │
   handshake)        └─────────────────────────────────────────┘
                                      │
                              backlog size
```

If the queue is full, new connections may be dropped or receive a RST.

**Historical note:** Linux actually has two queues (SYN queue and accept queue). The backlog mainly controls the accept queue. See `tcp_max_syn_backlog` and `somaxconn` kernel parameters.

### Accepting Connections: accept()

Block until a client connects, then return a new socket for that connection:

```python
# This blocks until a client connects
client_sock, client_addr = sock.accept()

print(f"Connection from {client_addr}")  # e.g., ('192.168.1.50', 54321)

# client_sock is a NEW socket, specific to this client
# sock continues listening for more connections
```

**Key insight:** `accept()` creates a new socket. The original socket continues listening. This is how a server handles multiple clients.

```
                                    ┌─────────────────────┐
                                    │   Listening Socket  │
                                    │   fd=3              │
                                    │   0.0.0.0:8080      │
                                    └──────────┬──────────┘
                                               │
                                               │ accept()
                                               │
                     ┌─────────────────────────┼─────────────────────────┐
                     │                         │                         │
                     ▼                         ▼                         ▼
          ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
          │ Connection Socket│      │ Connection Socket│      │ Connection Socket│
          │ fd=4             │      │ fd=5             │      │ fd=6             │
          │ client1:54321    │      │ client2:54322    │      │ client3:54323    │
          └──────────────────┘      └──────────────────┘      └──────────────────┘
```

### Connecting to a Server: connect()

For clients:

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to server at 192.168.1.100 port 8080
sock.connect(('192.168.1.100', 8080))

# Now we can send and receive
```

`connect()` initiates the TCP three-way handshake. It blocks until the handshake completes (or fails).

### Reading Data: recv() and read()

```python
# Receive up to 4096 bytes
data = client_sock.recv(4096)

# data is bytes, may be less than 4096
# Empty bytes (b'') means connection closed

if not data:
    print("Connection closed by peer")
```

**Critical understanding:**

`recv()` does NOT guarantee you get all the data you're expecting. TCP is a byte stream, not a message stream.

```python
# Client sends: b"Hello, World!"

# Server might receive:
data = sock.recv(4096)  # b"Hello, "  (first recv)
data = sock.recv(4096)  # b"World!"   (second recv)

# Or all at once:
data = sock.recv(4096)  # b"Hello, World!"

# TCP doesn't preserve message boundaries!
```

**The recv() flags:**

```python
# Normal receive
data = sock.recv(4096)

# Peek at data without removing from buffer
data = sock.recv(4096, socket.MSG_PEEK)

# Wait for all bytes (may still return less on connection close)
data = sock.recv(4096, socket.MSG_WAITALL)
```

### Writing Data: send() and sendall()

```python
# send() - sends what it can, returns number of bytes sent
bytes_sent = sock.send(b"Hello, World!")
# bytes_sent might be less than len(data)!

# sendall() - keeps trying until all data sent (or error)
sock.sendall(b"Hello, World!")
# Returns None on success, raises exception on error
```

**Always use `sendall()` for complete messages** unless you have a specific reason not to.

**Why send() might send less:**
- Send buffer is full
- Network congestion
- Non-blocking mode

### Closing Connections: close() and shutdown()

```python
# Close the socket entirely
sock.close()

# Graceful shutdown - half-close
sock.shutdown(socket.SHUT_WR)   # Stop sending (send FIN)
sock.shutdown(socket.SHUT_RD)   # Stop receiving
sock.shutdown(socket.SHUT_RDWR) # Stop both (like close, but doesn't release fd)
```

**shutdown() vs close():**

| Operation | Effect |
|-----------|--------|
| `shutdown(SHUT_WR)` | Sends FIN, can still receive |
| `shutdown(SHUT_RD)` | Discard incoming data |
| `close()` | Release file descriptor, send FIN if needed |

**Pattern for graceful closure:**

```python
# Server done sending response
sock.shutdown(socket.SHUT_WR)  # Send FIN

# Continue reading until client closes
while True:
    data = sock.recv(4096)
    if not data:
        break  # Client closed

sock.close()  # Now fully close
```

---

## 2.3 Socket Options: setsockopt()

Socket options control behavior at various levels:

```python
# Set option
sock.setsockopt(level, optname, value)

# Get option
value = sock.getsockopt(level, optname)
```

### SOL_SOCKET Level Options

**SO_REUSEADDR — Reuse address immediately:**

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', 8080))
```

Without this, after closing a server, you get "Address already in use" for ~60 seconds (TIME_WAIT). With it, you can rebind immediately.

**SO_REUSEPORT — Multiple sockets on same port (Linux 3.9+):**

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
```

Allows multiple processes to bind to the same port. Kernel load-balances connections between them. Used by high-performance servers.

**SO_RCVBUF / SO_SNDBUF — Buffer sizes:**

```python
# Set receive buffer to 256KB
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)

# Set send buffer to 256KB
sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)
```

Larger buffers = more data can be in flight = higher throughput (especially on high-latency connections).

**SO_KEEPALIVE — Detect dead connections:**

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
```

Kernel will send probes on idle connections to detect if peer is dead.

### IPPROTO_TCP Level Options

**TCP_NODELAY — Disable Nagle's algorithm:**

```python
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
```

Nagle's algorithm batches small writes to reduce overhead. Disabling it reduces latency but increases packet count. Use for interactive applications (SSH, games, real-time).

**TCP_QUICKACK — Disable delayed ACKs:**

```python
# Linux only
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
```

---

## 2.4 Blocking vs Non-Blocking Sockets

### Blocking Mode (Default)

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# sock is blocking by default

data = sock.recv(4096)  # Blocks until data available
sock.send(data)         # Blocks if send buffer full
sock.accept()           # Blocks until connection arrives
sock.connect(addr)      # Blocks until handshake complete
```

### Non-Blocking Mode

```python
sock.setblocking(False)
# or
sock.settimeout(0)

# Now operations return immediately or raise exception
try:
    data = sock.recv(4096)
except BlockingIOError:
    # No data available right now
    pass
```

**Non-blocking behavior:**

| Operation | Blocking | Non-Blocking |
|-----------|----------|--------------|
| `recv()` on empty buffer | Waits for data | Raises `BlockingIOError` |
| `send()` on full buffer | Waits for space | Raises `BlockingIOError` or returns partial |
| `accept()` with no pending | Waits | Raises `BlockingIOError` |
| `connect()` | Waits for handshake | Returns immediately, use `select` to wait |

### Timeout Mode

```python
sock.settimeout(5.0)  # 5 second timeout

try:
    data = sock.recv(4096)
except socket.timeout:
    print("No data received in 5 seconds")
```

### Using fcntl (Low-Level)

```python
import fcntl
import os

# Get current flags
flags = fcntl.fcntl(sock.fileno(), fcntl.F_GETFL)

# Set non-blocking
fcntl.fcntl(sock.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)

# Set blocking
fcntl.fcntl(sock.fileno(), fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
```

---

## 2.5 Address Families

### AF_INET (IPv4)

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('192.168.1.100', 8080))  # (host, port)
```

### AF_INET6 (IPv6)

```python
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.bind(('::1', 8080))  # IPv6 localhost

# Dual-stack socket (accepts both IPv4 and IPv6)
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
sock.bind(('::', 8080))
```

### AF_UNIX (Unix Domain Sockets)

For local inter-process communication:

```python
import os

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

# Remove socket file if exists
socket_path = '/tmp/my_socket.sock'
if os.path.exists(socket_path):
    os.unlink(socket_path)

sock.bind(socket_path)
sock.listen(5)

# Client connects to same path
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.connect('/tmp/my_socket.sock')
```

Benefits:
- Faster than TCP (no network stack)
- File permissions for access control
- Supports passing file descriptors between processes

---

## 2.6 Socket Types

### SOCK_STREAM (TCP)

- Connection-oriented
- Reliable, ordered byte stream
- Use for HTTP, SSH, databases

### SOCK_DGRAM (UDP)

```python
# UDP Server
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(('0.0.0.0', 8080))

while True:
    data, addr = server.recvfrom(4096)
    print(f"Received from {addr}: {data}")
    server.sendto(b"Response", addr)

# UDP Client
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.sendto(b"Hello", ('127.0.0.1', 8080))
data, addr = client.recvfrom(4096)
```

### SOCK_RAW (Raw Sockets)

For building custom protocols or packet sniffing:

```python
# Requires root/admin privileges
sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
```

---

## 2.7 Building an Echo Server

Let's build a complete TCP echo server:

```python
#!/usr/bin/env python3
"""
A simple TCP echo server.
Receives data from clients and sends it back.
"""

import socket


def create_server_socket(host: str, port: int) -> socket.socket:
    """Create and configure a server socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Allow reuse of address (avoid "Address already in use")
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    sock.bind((host, port))
    sock.listen(128)

    print(f"Server listening on {host}:{port}")
    return sock


def handle_client(client_sock: socket.socket, client_addr: tuple) -> None:
    """Handle a single client connection."""
    print(f"Connection from {client_addr}")

    try:
        while True:
            # Receive data
            data = client_sock.recv(4096)

            if not data:
                # Client closed connection
                print(f"Client {client_addr} disconnected")
                break

            print(f"Received from {client_addr}: {data!r}")

            # Echo it back
            client_sock.sendall(data)

    except ConnectionResetError:
        print(f"Client {client_addr} reset connection")
    except Exception as e:
        print(f"Error handling {client_addr}: {e}")
    finally:
        client_sock.close()


def main():
    server_sock = create_server_socket('0.0.0.0', 8080)

    try:
        while True:
            # Wait for a connection
            client_sock, client_addr = server_sock.accept()

            # Handle this client (blocking - one at a time)
            handle_client(client_sock, client_addr)

    except KeyboardInterrupt:
        print("\nShutting down server")
    finally:
        server_sock.close()


if __name__ == '__main__':
    main()
```

**Limitations of this server:**
- Handles only one client at a time (blocking)
- We'll fix this in Module 9-13 (concurrency)

---

## 2.8 Building an Echo Client

```python
#!/usr/bin/env python3
"""
A simple TCP echo client.
Sends user input to server and prints response.
"""

import socket


def main():
    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Connect to server
        sock.connect(('127.0.0.1', 8080))
        print("Connected to server")

        while True:
            # Get user input
            message = input("Enter message (or 'quit'): ")

            if message.lower() == 'quit':
                break

            # Send to server
            sock.sendall(message.encode('utf-8'))

            # Receive response
            data = sock.recv(4096)

            if not data:
                print("Server closed connection")
                break

            print(f"Server replied: {data.decode('utf-8')}")

    except ConnectionRefusedError:
        print("Could not connect to server")
    except KeyboardInterrupt:
        print("\nDisconnecting")
    finally:
        sock.close()


if __name__ == '__main__':
    main()
```

---

## 2.9 Understanding Backlog and Connection Queues

### The Two-Queue Model (Linux)

Linux actually maintains two queues:

```
                                           ┌──────────────────────┐
  SYN from ────▶  SYN Queue (incomplete)   │ SYN_RCVD connections │
  client                                   │ tcp_max_syn_backlog  │
                                           └──────────┬───────────┘
                                                      │
                                                      │ Handshake completes
                                                      ▼
                                           ┌──────────────────────┐
                                           │  Accept Queue        │
                      accept() ◀────────── │  (complete)          │
                                           │  listen() backlog    │
                                           └──────────────────────┘
```

**SYN Queue:**
- Holds connections that have received SYN but haven't completed handshake
- Size controlled by `tcp_max_syn_backlog` sysctl
- Subject to SYN flood attacks

**Accept Queue:**
- Holds connections that completed handshake, waiting for `accept()`
- Size controlled by `listen()` backlog parameter
- Capped by `somaxconn` sysctl

### What Happens When Queues Fill

**Accept queue full:**
- Linux ignores new SYNs (client retries)
- Or sends RST (depending on `tcp_abort_on_overflow`)

**SYN queue full:**
- SYN cookies may be used (if enabled)
- Or SYNs are dropped

### Observing Queue State

```bash
# Linux: see queue lengths
ss -ltn

# Output includes:
# Recv-Q: current accept queue length
# Send-Q: accept queue max size (backlog)
```

---

## 2.10 Lab: Packet Sniffing Your Own Server

### Exercise Setup

We'll observe our echo server at the packet level.

### Step 1: Start tcpdump

```bash
# In terminal 1
sudo tcpdump -i lo -nn -X port 8080
```

Options:
- `-i lo` — Listen on loopback interface
- `-nn` — Don't resolve hostnames or ports
- `-X` — Show packet contents in hex and ASCII

### Step 2: Start the Server

```bash
# In terminal 2
python echo_server.py
```

### Step 3: Connect with Client

```bash
# In terminal 3
python echo_client.py
```

Send a message: "Hello"

### Step 4: Analyze the Capture

You should see:

1. **Three-way handshake:**
```
IP 127.0.0.1.54321 > 127.0.0.1.8080: Flags [S], seq 1234567890
IP 127.0.0.1.8080 > 127.0.0.1.54321: Flags [S.], seq 9876543210, ack 1234567891
IP 127.0.0.1.54321 > 127.0.0.1.8080: Flags [.], ack 9876543211
```

2. **Data transfer:**
```
IP 127.0.0.1.54321 > 127.0.0.1.8080: Flags [P.], seq 1:6, ack 1
    0x0000:  ...Hello...
IP 127.0.0.1.8080 > 127.0.0.1.54321: Flags [P.], seq 1:6, ack 6
    0x0000:  ...Hello...
```

3. **Connection close:**
```
IP 127.0.0.1.54321 > 127.0.0.1.8080: Flags [F.], seq 6, ack 6
IP 127.0.0.1.8080 > 127.0.0.1.54321: Flags [F.], seq 6, ack 7
IP 127.0.0.1.54321 > 127.0.0.1.8080: Flags [.], ack 7
```

---

## Exercises

### Exercise 2.1: Socket Information

Write a script that:
1. Creates a socket and binds to port 0 (let OS choose)
2. Prints the assigned port number
3. Prints the file descriptor number
4. Prints the socket's receive and send buffer sizes

### Exercise 2.2: Multiple Connections

Modify the echo server to handle multiple connections sequentially:
1. After a client disconnects, accept the next one
2. Keep a count of total connections handled
3. Print statistics when the server shuts down

### Exercise 2.3: Echo Server with Timeout

Add a 30-second idle timeout:
1. If no data received for 30 seconds, close the connection
2. Print a message indicating timeout
3. Continue accepting new connections

### Exercise 2.4: UDP Echo Server

Rewrite the echo server using UDP:
1. Use `SOCK_DGRAM`
2. Use `recvfrom()` and `sendto()`
3. No accept() needed (connectionless)
4. Test with `nc -u 127.0.0.1 8080`

### Exercise 2.5: Unix Socket Echo Server

Create an echo server using Unix domain sockets:
1. Use `AF_UNIX` and a socket file path
2. Handle cleanup (remove socket file on shutdown)
3. Test with `nc -U /tmp/echo.sock`

### Exercise 2.6: Buffer Sizes and Throughput

Experiment with buffer sizes:
1. Create a server and client that transfer 100MB of data
2. Measure transfer time with default buffer sizes
3. Increase `SO_RCVBUF` and `SO_SNDBUF` to 1MB
4. Measure again and compare

---

## Deep Dive Questions

1. **Why does `send()` return the number of bytes sent instead of just success/failure?**

2. **What happens if you call `recv()` with a buffer size of 1 byte repeatedly? Is this efficient?**

3. **Why might `connect()` succeed even if the server application hasn't called `accept()` yet?**

4. **What's the difference between `socket.close()` and letting the socket object be garbage collected?**

5. **Why does `SO_REUSEADDR` not cause conflicts when two servers try to use the same port?**

6. **How does `SO_REUSEPORT` distribute connections between multiple processes?**

---

## Common Pitfalls

### 1. Assuming recv() Gets All Data

```python
# WRONG
data = sock.recv(4096)  # Assumes complete message

# RIGHT
def recv_all(sock, length):
    """Receive exactly `length` bytes."""
    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    return data
```

### 2. Forgetting to Handle Partial Sends

```python
# WRONG (though rare in practice)
sock.send(large_data)  # Might not send all

# RIGHT
sock.sendall(large_data)  # Guarantees all sent or exception
```

### 3. Not Setting SO_REUSEADDR

```python
# Server crashes, restart fails with "Address already in use"

# Fix: set SO_REUSEADDR before bind()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((host, port))
```

### 4. Blocking Forever

```python
# Server waits forever for a dead client

# Fix: use timeout
sock.settimeout(30)
try:
    data = sock.recv(4096)
except socket.timeout:
    # Handle timeout
```

### 5. Not Closing Sockets

```python
# Resource leak

# Fix: use context manager or try/finally
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.connect(('localhost', 8080))
    # sock automatically closed when exiting with block
```

---

## Resources

### Python Documentation
- [socket — Low-level networking interface](https://docs.python.org/3/library/socket.html)

### System Documentation
- `man 2 socket` — socket() system call
- `man 7 socket` — socket concepts
- `man 7 tcp` — TCP protocol specifics
- `man 7 ip` — IP protocol specifics

### Books
- "Unix Network Programming, Volume 1" by W. Richard Stevens — The bible of socket programming
- "The Linux Programming Interface" by Michael Kerrisk — Chapter on sockets

### Online
- [Beej's Guide to Network Programming](https://beej.us/guide/bgnet/) — Classic tutorial
- [Real Python: Socket Programming](https://realpython.com/python-sockets/) — Python-specific

---

## Summary

You now have the foundation for all network programming in Python:

1. **Sockets are file descriptors** — Integers referencing kernel structures
2. **Kernel buffers** — Send and receive buffers managed by the kernel
3. **The socket API** — socket(), bind(), listen(), accept(), connect(), recv(), send(), close()
4. **Socket options** — SO_REUSEADDR, SO_REUSEPORT, TCP_NODELAY control behavior
5. **Blocking vs non-blocking** — Default blocks; non-blocking raises exceptions
6. **Address families** — AF_INET (IPv4), AF_INET6 (IPv6), AF_UNIX (local)
7. **Socket types** — SOCK_STREAM (TCP), SOCK_DGRAM (UDP)

The echo server you built has a critical limitation: it handles only one client at a time. In Modules 9-14, we'll explore threading, multiprocessing, and async I/O to handle thousands of concurrent connections.

But first, we need to understand what our server will actually speak: HTTP.

---

## Next Module

**[Module 3: The HTTP Protocol — Complete Specification →](./MODULE_03_HTTP_PROTOCOL.md)**

We'll dive deep into HTTP: request/response structure, headers, methods, status codes, and everything your server needs to speak the web's language.
