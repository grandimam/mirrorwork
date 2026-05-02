# Module 1: The Internet Protocol Stack

## Overview

Before you write a single line of web server code, you must understand what happens when data travels across a network. This module strips away the abstractions and takes you to the metal—where electrical signals become bytes, bytes become packets, and packets become the HTTP requests your server will eventually handle.

This is not optional knowledge. Every bug you will ever debug in a web server—hanging connections, mysterious timeouts, packets that never arrive—traces back to concepts in this module.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Explain why the OSI model is taught but TCP/IP is used
2. Trace a packet's journey from application to wire and back
3. Understand IP addressing, subnets, and how routing decisions are made
4. Explain every phase of TCP's lifecycle: connection, data transfer, and termination
5. Analyze TCP's reliability mechanisms: sequence numbers, acknowledgments, flow control, congestion control
6. Understand when and why UDP exists
7. Trace DNS resolution from hostname to IP address
8. Use network debugging tools to observe real traffic

---

## 1.1 OSI Model vs TCP/IP Model — What Actually Matters

### The OSI Model (Academic)

The Open Systems Interconnection (OSI) model is a conceptual framework with 7 layers:

```
┌─────────────────────────────────────┐
│  Layer 7: Application  (HTTP, FTP)  │
├─────────────────────────────────────┤
│  Layer 6: Presentation (SSL, TLS)   │
├─────────────────────────────────────┤
│  Layer 5: Session      (NetBIOS)    │
├─────────────────────────────────────┤
│  Layer 4: Transport    (TCP, UDP)   │
├─────────────────────────────────────┤
│  Layer 3: Network      (IP, ICMP)   │
├─────────────────────────────────────┤
│  Layer 2: Data Link    (Ethernet)   │
├─────────────────────────────────────┤
│  Layer 1: Physical     (Cables)     │
└─────────────────────────────────────┘
```

The OSI model was designed by committee before the internet existed. It's useful for conversation ("that's a Layer 7 problem") but doesn't reflect reality.

### The TCP/IP Model (Reality)

The TCP/IP model is what actually runs the internet:

```
┌─────────────────────────────────────┐
│  Application Layer                  │
│  (HTTP, DNS, FTP, SMTP, SSH)        │
├─────────────────────────────────────┤
│  Transport Layer                    │
│  (TCP, UDP)                         │
├─────────────────────────────────────┤
│  Internet Layer                     │
│  (IP, ICMP, ARP)                    │
├─────────────────────────────────────┤
│  Network Access Layer               │
│  (Ethernet, Wi-Fi, Physical)        │
└─────────────────────────────────────┘
```

### Why This Matters for Web Servers

When you build a web server, you operate at the **Application Layer** (HTTP). But your code directly interacts with the **Transport Layer** (TCP) through sockets. Understanding the layers below helps you:

- Debug connection issues (Why is my server not receiving connections?)
- Optimize performance (Why is there a 40ms delay on every request?)
- Understand security (Where does TLS fit in?)

### Key Insight: Encapsulation

Each layer wraps the data from the layer above:

```
Application Data: "GET / HTTP/1.1\r\n..."
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ TCP Header │ "GET / HTTP/1.1\r\n..."                │  ← TCP Segment
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ IP Header │ TCP Header │ "GET / HTTP/1.1\r\n..."            │  ← IP Packet
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Ethernet Header │ IP Header │ TCP Header │ "GET / HTTP/1.1..." │ FCS │  ← Ethernet Frame
└─────────────────────────────────────────────────────────────────────────┘
```

When your server receives data, this process reverses. The kernel handles everything up to TCP and hands you just the application data.

---

## 1.2 IP Addressing, Subnets, and Routing Basics

### IPv4 Addresses

An IPv4 address is a 32-bit number, written as four octets:

```
192.168.1.100

In binary:
11000000.10101000.00000001.01100100
```

### Special Addresses

| Address | Meaning |
|---------|---------|
| `0.0.0.0` | "All interfaces" — when binding a server, listen on all network interfaces |
| `127.0.0.1` | Loopback — the machine talking to itself |
| `127.0.0.0/8` | Entire loopback range (127.0.0.1 to 127.255.255.254) |
| `10.0.0.0/8` | Private network (Class A) |
| `172.16.0.0/12` | Private network (Class B) |
| `192.168.0.0/16` | Private network (Class C) |
| `255.255.255.255` | Broadcast |

### Subnet Masks and CIDR Notation

A subnet mask determines which part of an IP address is the network and which is the host:

```
IP Address:     192.168.1.100
Subnet Mask:    255.255.255.0
                ─────────────
Network Part:   192.168.1.xxx
Host Part:      xxx.xxx.xxx.100
```

CIDR notation is shorthand:
- `192.168.1.0/24` means the first 24 bits are the network (same as `255.255.255.0`)
- `10.0.0.0/8` means the first 8 bits are the network (same as `255.0.0.0`)

### Routing Decisions

When your server sends a response, how does it know where to send it?

```
1. Is the destination on the same subnet?
   → Send directly via Layer 2 (ARP to get MAC address)

2. Is the destination on a different subnet?
   → Send to the default gateway (router)
   → Router forwards to next hop
   → Repeat until destination reached
```

View your routing table:
```bash
# macOS/Linux
netstat -rn
# or
ip route show  # Linux only
```

### Why This Matters for Web Servers

1. **Binding to addresses**: `0.0.0.0` vs `127.0.0.1` vs specific IP
2. **Firewall rules**: Understanding CIDR notation
3. **Debugging**: "Why can't external clients reach my server?"

---

## 1.3 TCP Deep Dive

TCP (Transmission Control Protocol) is the foundation of HTTP. Understanding TCP is understanding how your web server actually works.

### TCP Properties

- **Connection-oriented**: Must establish connection before sending data
- **Reliable**: Guarantees delivery (or tells you it failed)
- **Ordered**: Data arrives in the order it was sent
- **Bidirectional**: Both sides can send and receive
- **Flow-controlled**: Prevents overwhelming the receiver
- **Congestion-controlled**: Prevents overwhelming the network

### The Three-Way Handshake

Before any HTTP data is exchanged, TCP must establish a connection:

```
    Client                                 Server
       │                                      │
       │──────────── SYN (seq=x) ────────────▶│
       │                                      │
       │◀───────── SYN-ACK (seq=y, ack=x+1) ──│
       │                                      │
       │──────────── ACK (ack=y+1) ───────────▶│
       │                                      │
       │          Connection Established       │
```

**Step by step:**

1. **SYN**: Client sends synchronize request with initial sequence number (ISN)
2. **SYN-ACK**: Server acknowledges and sends its own ISN
3. **ACK**: Client acknowledges server's ISN

**Why three steps?** Both sides must:
- Declare their initial sequence number
- Confirm they received the other's sequence number

### Sequence Numbers and Acknowledgments

Every byte of data has a sequence number. Acknowledgments confirm receipt:

```
Client sends: seq=1000, 500 bytes of data
Server responds: ack=1500 (means "I received up to byte 1499, send 1500 next")
```

This enables:
- **Reliability**: If no ACK received, retransmit
- **Ordering**: Receiver can reassemble out-of-order packets
- **Duplicate detection**: Already seen this sequence number? Discard.

### TCP Segment Structure

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
├─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┤
│          Source Port          │       Destination Port        │
├───────────────────────────────┴───────────────────────────────┤
│                        Sequence Number                        │
├───────────────────────────────────────────────────────────────┤
│                    Acknowledgment Number                      │
├───────┬───────┬─┬─┬─┬─┬─┬─┬───────────────────────────────────┤
│  Data │       │U│A│P│R│S│F│                                   │
│ Offset│ Rsrvd │R│C│S│S│Y│I│            Window                 │
│       │       │G│K│H│T│N│N│                                   │
├───────┴───────┴─┴─┴─┴─┴─┴─┴───────────────────────────────────┤
│           Checksum            │         Urgent Pointer        │
├───────────────────────────────┴───────────────────────────────┤
│                    Options (if any)                           │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│                             Data                              │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

**Key flags:**
- **SYN**: Synchronize (connection establishment)
- **ACK**: Acknowledgment field is valid
- **FIN**: Finish (connection termination)
- **RST**: Reset (abort connection)
- **PSH**: Push (deliver data immediately)

### Flow Control: The Sliding Window

The receiver advertises how much buffer space it has:

```
Server sends: ack=1500, window=65535

This means:
- "I've received bytes up to 1499"
- "You can send bytes 1500 through 67034 without waiting for more ACKs"
```

The window "slides" forward as data is acknowledged:

```
┌───────────────────────────────────────────────────────────────────┐
│ Already │                                                         │
│  ACKed  │     Window (can send)        │    Cannot send yet       │
│         │                              │                          │
└─────────┴──────────────────────────────┴──────────────────────────┘
          ▲                              ▲
     Left edge                      Right edge
     (last ACK)                   (last ACK + window)
```

### Congestion Control

TCP must also avoid overwhelming the network (not just the receiver).

**Slow Start:**
1. Start with a small congestion window (cwnd), typically 10 segments
2. For each ACK received, increase cwnd by 1 segment
3. This causes exponential growth until threshold reached

**Congestion Avoidance:**
1. After threshold, grow cwnd linearly (1 segment per RTT)
2. On packet loss, halve the threshold and restart

**AIMD (Additive Increase, Multiplicative Decrease):**
- Increase: Add constant amount each RTT
- Decrease: Multiply by constant (0.5) on loss

```
cwnd
  │
  │            ╱╲          ╱╲
  │          ╱    ╲      ╱    ╲
  │        ╱        ╲  ╱        ╲
  │      ╱            ╲
  │    ╱
  │  ╱
  │╱
  └──────────────────────────────────▶ time
          loss      loss
```

### Connection Termination

Either side can initiate termination:

```
    Client                                 Server
       │                                      │
       │──────────── FIN ────────────────────▶│
       │                                      │
       │◀───────────── ACK ───────────────────│
       │                                      │
       │◀───────────── FIN ───────────────────│
       │                                      │
       │──────────── ACK ────────────────────▶│
       │                                      │
```

**The TIME_WAIT state:**

After sending the final ACK, the client enters TIME_WAIT for 2×MSL (Maximum Segment Lifetime, typically 60 seconds):

- Ensures the final ACK reaches the server (can retransmit if lost)
- Ensures old packets from this connection don't interfere with new connections

**Why this matters for web servers:**

High-traffic servers can exhaust local ports due to TIME_WAIT. Solutions:
- `SO_REUSEADDR` socket option
- `SO_REUSEPORT` socket option
- TCP keepalive to reuse connections

### TCP State Machine

```
                              ┌─────────────┐
                              │   CLOSED    │
                              └──────┬──────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 │ (Server)                   (Client)   │
                 ▼                                       ▼
          ┌─────────────┐                         ┌─────────────┐
          │   LISTEN    │                         │  SYN_SENT   │
          └──────┬──────┘                         └──────┬──────┘
                 │ recv SYN, send SYN+ACK                │ recv SYN+ACK, send ACK
                 ▼                                       │
          ┌─────────────┐                                │
          │  SYN_RCVD   │────────────────────────────────┤
          └──────┬──────┘                                │
                 │ recv ACK                              │
                 ▼                                       ▼
          ┌───────────────────────────────────────────────┐
          │                  ESTABLISHED                  │
          └───────────────────────────────────────────────┘
                 │                                 │
                 │ send FIN                        │ recv FIN, send ACK
                 ▼                                 ▼
          ┌─────────────┐                   ┌─────────────┐
          │  FIN_WAIT_1 │                   │ CLOSE_WAIT  │
          └──────┬──────┘                   └──────┬──────┘
                 │ recv ACK                        │ send FIN
                 ▼                                 ▼
          ┌─────────────┐                   ┌─────────────┐
          │  FIN_WAIT_2 │                   │  LAST_ACK   │
          └──────┬──────┘                   └──────┬──────┘
                 │ recv FIN, send ACK              │ recv ACK
                 ▼                                 ▼
          ┌─────────────┐                   ┌─────────────┐
          │  TIME_WAIT  │                   │   CLOSED    │
          └──────┬──────┘                   └─────────────┘
                 │ 2MSL timeout
                 ▼
          ┌─────────────┐
          │   CLOSED    │
          └─────────────┘
```

---

## 1.4 UDP — When and Why

UDP (User Datagram Protocol) is TCP's simpler sibling:

- **Connectionless**: No handshake, just send
- **Unreliable**: No guarantee of delivery
- **Unordered**: Packets may arrive out of order
- **No flow/congestion control**: Sender sends at will

### UDP Datagram Structure

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
├───────────────────────────────┬───────────────────────────────┤
│          Source Port          │       Destination Port        │
├───────────────────────────────┼───────────────────────────────┤
│            Length             │           Checksum            │
├───────────────────────────────┴───────────────────────────────┤
│                             Data                              │
└───────────────────────────────────────────────────────────────┘
```

Just 8 bytes of header vs TCP's minimum 20 bytes.

### When UDP is Used

- **DNS**: Quick queries, retry at application level
- **Video streaming**: Dropping frames is better than waiting
- **Gaming**: Low latency matters more than reliability
- **QUIC/HTTP/3**: UDP with reliability built on top

### Why This Matters for Web Servers

- HTTP/1.1 and HTTP/2 use TCP
- HTTP/3 uses QUIC (over UDP)
- DNS resolution (which your server does) uses UDP

---

## 1.5 DNS Resolution — From Hostname to IP

When a client requests `http://example.com/`, the browser must first resolve `example.com` to an IP address.

### The Resolution Process

```
1. Browser checks its DNS cache
2. OS checks its DNS cache
3. OS queries configured DNS resolver (e.g., 8.8.8.8)
4. Resolver performs recursive lookup:

   ┌─────────────────┐
   │  Your Resolver  │
   └────────┬────────┘
            │
            │ "Where is example.com?"
            ▼
   ┌─────────────────┐
   │  Root Server    │  "Ask .com servers"
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │  .com TLD       │  "Ask ns.example.com"
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Authoritative   │  "93.184.216.34"
   │ for example.com │
   └─────────────────┘
```

### DNS Record Types

| Type | Purpose | Example |
|------|---------|---------|
| A | IPv4 address | `example.com. IN A 93.184.216.34` |
| AAAA | IPv6 address | `example.com. IN AAAA 2606:2800:220:1:...` |
| CNAME | Alias to another name | `www.example.com. IN CNAME example.com.` |
| MX | Mail server | `example.com. IN MX 10 mail.example.com.` |
| TXT | Text data | Used for SPF, DKIM, verification |
| NS | Name server | `example.com. IN NS ns1.example.com.` |

### Why This Matters for Web Servers

1. **Your server is found via DNS**: Misconfigured DNS = unreachable server
2. **DNS caching**: TTL determines how long clients cache your IP
3. **DNS-based load balancing**: Multiple A records for round-robin
4. **Performance**: DNS lookup adds latency to first request

---

## 1.6 Network Debugging Tools

### tcpdump — Capture Packets

```bash
# Capture all traffic on port 80
sudo tcpdump -i any port 80

# Capture with more detail
sudo tcpdump -i any -nn -X port 80

# Save to file for Wireshark
sudo tcpdump -i any -w capture.pcap port 80

# Capture TCP handshake
sudo tcpdump -i any 'tcp[tcpflags] & (tcp-syn|tcp-fin|tcp-rst) != 0'
```

### Wireshark — Visual Packet Analysis

Open capture files from tcpdump or capture live. Key features:
- Follow TCP streams to see full request/response
- Filter by protocol, port, IP
- Analyze timing and retransmissions

### netstat / ss — Socket Statistics

```bash
# Show all listening sockets
netstat -tlnp   # Linux
netstat -an | grep LISTEN   # macOS

# Modern alternative (Linux)
ss -tlnp

# Show all TCP connections with state
ss -tan

# Show socket memory usage
ss -tm
```

### lsof — List Open Files (including sockets)

```bash
# What process is using port 8080?
lsof -i :8080

# What files/sockets does this process have open?
lsof -p <pid>
```

### curl — HTTP Debugging

```bash
# Verbose output showing connection details
curl -v http://localhost:8080/

# Show timing breakdown
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8080/

# curl-format.txt:
#     time_namelookup:  %{time_namelookup}s\n
#        time_connect:  %{time_connect}s\n
#     time_appconnect:  %{time_appconnect}s\n
#    time_pretransfer:  %{time_pretransfer}s\n
#       time_redirect:  %{time_redirect}s\n
#  time_starttransfer:  %{time_starttransfer}s\n
#                     ----------\n
#          time_total:  %{time_total}s\n
```

### nc (netcat) — Raw TCP Testing

```bash
# Connect to a server
nc localhost 8080

# Listen on a port (simple server)
nc -l 8080

# Send HTTP request manually
echo -e "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n" | nc localhost 8080
```

---

## Exercises

### Exercise 1.1: Packet Tracing

1. Start a simple HTTP server (Python: `python -m http.server 8080`)
2. In another terminal, start tcpdump: `sudo tcpdump -i lo0 port 8080`
3. In a third terminal: `curl http://localhost:8080/`
4. Identify in the tcpdump output:
   - The three-way handshake (SYN, SYN-ACK, ACK)
   - The HTTP request
   - The HTTP response
   - The connection termination (FIN, ACK)

### Exercise 1.2: Connection States

1. Write a simple TCP client that connects but doesn't close the connection
2. Use `netstat` or `ss` to observe the ESTABLISHED state
3. Modify the client to close properly and observe TIME_WAIT
4. Start a server, kill it abruptly, and observe socket states

### Exercise 1.3: DNS Resolution Tracing

```bash
# Use dig to trace full resolution
dig +trace example.com

# Observe DNS caching
dig example.com  # Note Query time
dig example.com  # Should be faster (cached)
```

Answer:
1. How many servers were queried?
2. What was the TTL on the final answer?
3. What are the authoritative nameservers for the domain?

### Exercise 1.4: TCP Retransmission

1. Use a tool like `tc` (Linux) to introduce packet loss:
   ```bash
   sudo tc qdisc add dev lo root netem loss 10%
   ```
2. Run tcpdump while making HTTP requests
3. Observe retransmissions in the capture
4. Remove the artificial loss:
   ```bash
   sudo tc qdisc del dev lo root
   ```

### Exercise 1.5: Manual HTTP Request

Using only `nc`, perform a complete HTTP/1.1 request:

```bash
nc example.com 80
```

Type:
```
GET / HTTP/1.1
Host: example.com
Connection: close

```

(Note the blank line at the end)

Observe the response headers and body.

---

## Deep Dive Questions

1. **Why does TCP use a three-way handshake instead of two?**

2. **What happens if a SYN packet is lost? How does the client know to retry?**

3. **Why does TIME_WAIT last for 2×MSL? What would happen with a shorter duration?**

4. **If TCP guarantees ordered delivery, why might packets arrive at the kernel out of order?**

5. **Why does HTTP/3 use UDP instead of TCP? What problem does this solve?**

6. **How does TCP's congestion control differ from flow control?**

---

## Resources

### RFCs (Authoritative Sources)

- [RFC 791 - Internet Protocol (IP)](https://tools.ietf.org/html/rfc791)
- [RFC 793 - Transmission Control Protocol (TCP)](https://tools.ietf.org/html/rfc793)
- [RFC 768 - User Datagram Protocol (UDP)](https://tools.ietf.org/html/rfc768)
- [RFC 1035 - Domain Names (DNS)](https://tools.ietf.org/html/rfc1035)
- [RFC 5681 - TCP Congestion Control](https://tools.ietf.org/html/rfc5681)

### Books

- "TCP/IP Illustrated, Volume 1" by W. Richard Stevens — The definitive reference
- "Computer Networking: A Top-Down Approach" by Kurose & Ross — Academic but thorough
- "High Performance Browser Networking" by Ilya Grigorik — Free online, web-focused

### Interactive Tools

- [Wireshark](https://www.wireshark.org/) — Packet analysis GUI
- [Beej's Guide to Network Programming](https://beej.us/guide/bgnet/) — Practical socket programming

### Videos

- "TCP/IP Explained" — Ben Eater's networking fundamentals series
- CS144 Stanford — Full networking course lectures available online

---

## Summary

You now understand the protocol stack that underlies every web request:

1. **Application Layer**: HTTP lives here, and so will your server
2. **Transport Layer**: TCP provides reliable, ordered byte streams
3. **Internet Layer**: IP handles addressing and routing
4. **Network Access**: Ethernet/Wi-Fi move bits physically

Key TCP concepts you must internalize:
- Three-way handshake establishes connections
- Sequence numbers and acknowledgments ensure reliability
- Flow control prevents overwhelming receivers
- Congestion control prevents overwhelming the network
- Four-way termination closes connections
- TIME_WAIT exists for a reason

In the next module, we'll take these concepts and implement them in Python using the socket API. You'll create your first TCP server and client, experiencing firsthand how these protocols manifest in code.

---

## Next Module

**[Module 2: Socket Programming Fundamentals →](./MODULE_02_SOCKET_PROGRAMMING.md)**

We'll translate this theory into practice, writing raw socket code in Python.
