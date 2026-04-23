# Appendix C: Debugging Cheatsheet

## Overview

This appendix provides quick debugging techniques for common web server issues.

---

## C.1 Network Debugging

### tcpdump

```bash
# Capture HTTP traffic on port 8080
sudo tcpdump -i lo0 port 8080 -A

# Capture and save to file
sudo tcpdump -i eth0 port 80 -w capture.pcap

# Filter by host
sudo tcpdump host 192.168.1.100

# Show packet contents in hex and ASCII
sudo tcpdump -X port 8080
```

### netstat / ss

```bash
# Show all listening ports
netstat -tlnp
ss -tlnp

# Show connections by state
ss -tan state established
ss -tan state time-wait

# Count connections per IP
ss -tan | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -rn

# Show socket statistics
ss -s
```

### curl

```bash
# Verbose output with timing
curl -v http://localhost:8080/

# Show only headers
curl -I http://localhost:8080/

# Time breakdown
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8080/

# POST with JSON
curl -X POST -H "Content-Type: application/json" \
     -d '{"key":"value"}' http://localhost:8080/api

# Follow redirects
curl -L http://localhost:8080/redirect

# With cookies
curl -b "session=abc123" http://localhost:8080/
```

**curl-format.txt:**
```
     time_namelookup:  %{time_namelookup}s\n
        time_connect:  %{time_connect}s\n
     time_appconnect:  %{time_appconnect}s\n
    time_pretransfer:  %{time_pretransfer}s\n
       time_redirect:  %{time_redirect}s\n
  time_starttransfer:  %{time_starttransfer}s\n
                     ----------\n
          time_total:  %{time_total}s\n
```

### nc (netcat)

```bash
# Send raw HTTP request
echo -e "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n" | nc localhost 8080

# Listen on port (simple server)
nc -l 8080

# Check if port is open
nc -zv localhost 8080
```

---

## C.2 Python Debugging

### pdb

```python
# Insert breakpoint
import pdb; pdb.set_trace()

# Python 3.7+ breakpoint
breakpoint()

# Common commands
# n - next line
# s - step into
# c - continue
# l - list source
# p expr - print expression
# pp expr - pretty print
# w - where (stack trace)
# q - quit
```

### Async Debugging

```python
import asyncio

# Enable debug mode
asyncio.run(main(), debug=True)

# Or via environment
# PYTHONASYNCIODEBUG=1 python server.py

# Log slow callbacks
import logging
logging.getLogger('asyncio').setLevel(logging.DEBUG)
```

### Logging

```python
import logging

# Basic setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)

# Per-module logger
logger = logging.getLogger(__name__)
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.exception("Error with traceback")

# Log to file
handler = logging.FileHandler('server.log')
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s %(name)s: %(message)s'
))
logger.addHandler(handler)
```

### Memory Debugging

```python
# tracemalloc - memory allocation tracking
import tracemalloc

tracemalloc.start()

# ... run code ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("Top 10 memory allocations:")
for stat in top_stats[:10]:
    print(stat)


# objgraph - object graph visualization
import objgraph

# Show most common types
objgraph.show_most_common_types(limit=10)

# Find objects
objgraph.by_type('Request')

# Show backreferences (find memory leaks)
objgraph.show_backrefs(obj, filename='refs.png')
```

---

## C.3 Common Issues

### Connection Refused

```
Error: Connection refused (111)

Causes:
1. Server not running
2. Wrong port
3. Firewall blocking

Debug:
- Check if server is running: ps aux | grep python
- Check port: ss -tlnp | grep 8080
- Check firewall: iptables -L
```

### Address Already in Use

```
Error: Address already in use (98)

Causes:
1. Previous server still running
2. Socket in TIME_WAIT state

Solutions:
1. Kill existing process: kill $(lsof -t -i:8080)
2. Set SO_REUSEADDR:
   sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
3. Wait for TIME_WAIT (usually 60s)
```

### Too Many Open Files

```
Error: Too many open files (24)

Causes:
1. File descriptor limit reached
2. Connection leak

Debug:
- Check limits: ulimit -n
- Count open files: ls -l /proc/$(pgrep python)/fd | wc -l
- Find leaks: lsof -p $(pgrep python)

Solutions:
1. Increase limit: ulimit -n 65535
2. Fix connection leaks
3. Add to /etc/security/limits.conf:
   * soft nofile 65535
   * hard nofile 65535
```

### Broken Pipe

```
Error: Broken pipe (32)

Causes:
1. Client closed connection
2. Writing to closed socket

Solutions:
1. Handle exception:
   try:
       writer.write(data)
       await writer.drain()
   except (ConnectionResetError, BrokenPipeError):
       pass

2. Check connection before writing
```

### Slow Responses

```
Symptoms:
- High latency
- Timeouts

Debug:
1. Profile code:
   python -m cProfile -s cumtime server.py

2. Check database queries:
   - N+1 queries
   - Missing indexes
   - Long transactions

3. Check external calls:
   - Add timeouts
   - Use connection pooling

4. Check resource usage:
   - CPU: top, htop
   - Memory: free -m
   - Disk I/O: iostat
   - Network: iftop
```

### Memory Leak

```
Symptoms:
- Increasing memory usage over time
- OOM killer

Debug:
1. Use tracemalloc (see above)
2. Check for:
   - Unclosed connections
   - Growing caches
   - Circular references
   - Global state accumulation

3. Monitor:
   import resource
   print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
```

---

## C.4 Performance Profiling

### cProfile

```bash
# Run with profiler
python -m cProfile -s cumtime server.py

# Save to file
python -m cProfile -o profile.stats server.py

# Analyze
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative')
p.print_stats(20)
"
```

### py-spy

```bash
# Install
pip install py-spy

# Top-like view
py-spy top --pid $(pgrep -f server.py)

# Generate flame graph
py-spy record -o flame.svg --pid $(pgrep -f server.py)

# Profile command
py-spy record -o flame.svg -- python server.py
```

### memory_profiler

```python
# Install
# pip install memory_profiler

from memory_profiler import profile

@profile
def my_function():
    # Function to profile
    pass

# Run: python -m memory_profiler script.py
```

---

## C.5 HTTP Debugging

### Request Issues

```python
# Log all requests
class LoggingMiddleware:
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            print(f"Request: {scope['method']} {scope['path']}")
            print(f"Headers: {dict(scope['headers'])}")

            # Log body
            body = b''
            async def receive_wrapper():
                nonlocal body
                message = await receive()
                body += message.get('body', b'')
                return message

            # ... continue processing
```

### Response Issues

```python
# Log all responses
class ResponseLoggingMiddleware:
    async def __call__(self, scope, receive, send):
        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                print(f"Response: {message['status']}")
                print(f"Headers: {message.get('headers', [])}")
            elif message['type'] == 'http.response.body':
                print(f"Body: {message.get('body', b'')[:100]}")
            await send(message)

        await self.app(scope, receive, send_wrapper)
```

### WebSocket Debugging

```python
# Log WebSocket messages
class WebSocketDebugger:
    async def __call__(self, scope, receive, send):
        async def receive_wrapper():
            message = await receive()
            print(f"WS Receive: {message}")
            return message

        async def send_wrapper(message):
            print(f"WS Send: {message}")
            await send(message)

        await self.app(scope, receive_wrapper, send_wrapper)
```

---

## C.6 Quick Commands

### Process Management

```bash
# Find server process
pgrep -f "python.*server"
ps aux | grep server

# Kill by port
kill $(lsof -t -i:8080)

# Monitor resources
htop -p $(pgrep -f server)
watch -n 1 'ss -tan | grep 8080 | wc -l'
```

### Log Analysis

```bash
# Tail logs with filtering
tail -f server.log | grep ERROR

# Count errors per minute
grep ERROR server.log | cut -d' ' -f1-2 | uniq -c

# Find slow requests (>1s)
grep -E 'took [0-9]{4,}ms' server.log

# Unique IPs
awk '{print $1}' access.log | sort | uniq -c | sort -rn
```

### Network

```bash
# Test connectivity
ping server.example.com
traceroute server.example.com

# DNS lookup
dig server.example.com
nslookup server.example.com

# Check TLS certificate
openssl s_client -connect server.example.com:443

# HTTP timing
curl -w "Total: %{time_total}s\n" -o /dev/null -s http://localhost:8080/
```

---

## Summary

Essential debugging tools:

1. **Network**: tcpdump, curl, nc, ss
2. **Python**: pdb, logging, cProfile
3. **Memory**: tracemalloc, objgraph
4. **Performance**: py-spy, memory_profiler
5. **System**: htop, strace, lsof

Always start with logs, then add instrumentation as needed.
