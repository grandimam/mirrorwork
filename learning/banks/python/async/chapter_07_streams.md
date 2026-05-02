# Chapter 7: Streams - High-Level Network I/O

## 7.1 StreamReader and StreamWriter

Streams provide a high-level interface for working with network connections in asyncio. They offer a more convenient API than low-level transports and protocols while still maintaining excellent performance.

### Understanding Streams

```python
import asyncio
import socket

async def demonstrate_basic_streams():
    """Demonstrate basic StreamReader and StreamWriter usage"""
    
    print("=== Basic Streams Demonstration ===")
    
    # Create a simple echo server using streams
    async def echo_server_handler(reader, writer):
        """Handle client connections for echo server"""
        
        # Get client address
        client_addr = writer.get_extra_info('peername')
        print(f"   Server: Client connected from {client_addr}")
        
        try:
            while True:
                # Read data from client
                data = await reader.read(1024)  # Read up to 1024 bytes
                
                if not data:
                    print(f"   Server: Client {client_addr} disconnected")
                    break
                
                message = data.decode('utf-8').strip()
                print(f"   Server: Received '{message}' from {client_addr}")
                
                # Echo the message back
                echo_message = f"Echo: {message}\n"
                writer.write(echo_message.encode('utf-8'))
                await writer.drain()  # Ensure data is sent
                
                print(f"   Server: Echoed back to {client_addr}")
        
        except Exception as e:
            print(f"   Server: Error handling client {client_addr}: {e}")
        
        finally:
            # Close the connection
            print(f"   Server: Closing connection to {client_addr}")
            writer.close()
            await writer.wait_closed()
    
    async def echo_client(message):
        """Simple echo client"""
        try:
            # Connect to server
            reader, writer = await asyncio.open_connection('localhost', 8888)
            print(f"   Client: Connected to server")
            
            # Send message
            writer.write(f"{message}\n".encode('utf-8'))
            await writer.drain()
            print(f"   Client: Sent '{message}'")
            
            # Read response
            response = await reader.readline()
            response_text = response.decode('utf-8').strip()
            print(f"   Client: Received '{response_text}'")
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            print(f"   Client: Connection closed")
            
            return response_text
        
        except Exception as e:
            print(f"   Client: Error: {e}")
            return None
    
    # Start the echo server
    server = await asyncio.start_server(
        echo_server_handler,
        'localhost',
        8888
    )
    
    print("1. Starting echo server on localhost:8888")
    
    async with server:
        # Start serving in background
        server_task = asyncio.create_task(server.serve_forever())
        
        # Give server time to start
        await asyncio.sleep(0.1)
        
        # Test with multiple clients
        client_tasks = [
            echo_client("Hello World"),
            echo_client("How are you?"),
            echo_client("Goodbye")
        ]
        
        print("\n2. Testing with multiple clients:")
        results = await asyncio.gather(*client_tasks)
        
        print(f"\n3. Results: {results}")
        
        # Stop the server
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)

asyncio.run(demonstrate_basic_streams())
```

### StreamReader Methods and Patterns

```python
import asyncio
import io

async def demonstrate_stream_reader_methods():
    """Demonstrate different StreamReader methods"""
    
    print("=== StreamReader Methods ===")
    
    # Create mock data for demonstration
    sample_data = (
        b"Line 1\n"
        b"Line 2\r\n"
        b"Line 3 without newline"
        b"BINARY_DATA\x00\x01\x02\x03"
        b"Final line\n"
    )
    
    async def data_server_handler(reader, writer):
        """Server that sends predefined data"""
        client_addr = writer.get_extra_info('peername')
        print(f"   Data Server: Client {client_addr} connected")
        
        # Send all sample data
        writer.write(sample_data)
        await writer.drain()
        
        print(f"   Data Server: Sent {len(sample_data)} bytes to {client_addr}")
        
        # Close connection after sending
        await asyncio.sleep(0.1)  # Give client time to read
        writer.close()
        await writer.wait_closed()
    
    async def test_read_methods():
        """Test different read methods"""
        
        # Connect to data server
        reader, writer = await asyncio.open_connection('localhost', 8889)
        print("   Client: Connected to data server")
        
        try:
            # Method 1: read() - read up to n bytes
            print("\n   1. Using read(10):")
            chunk1 = await reader.read(10)
            print(f"      Read: {chunk1}")
            
            # Method 2: readline() - read until newline
            print("\n   2. Using readline():")
            line1 = await reader.readline()
            print(f"      Read line: {line1}")
            
            # Method 3: readexactly() - read exactly n bytes
            print("\n   3. Using readexactly(8):")
            exact_chunk = await reader.readexactly(8)
            print(f"      Read exactly: {exact_chunk}")
            
            # Method 4: readuntil() - read until delimiter
            print("\n   4. Using readuntil(b'BINARY'):")
            until_chunk = await reader.readuntil(b'BINARY')
            print(f"      Read until: {until_chunk}")
            
            # Method 5: Read remaining data
            print("\n   5. Reading remaining data:")
            remaining = await reader.read()  # Read all remaining
            print(f"      Remaining: {remaining}")
        
        finally:
            writer.close()
            await writer.wait_closed()
    
    # Start data server
    server = await asyncio.start_server(
        data_server_handler,
        'localhost',
        8889
    )
    
    async with server:
        # Start serving
        server_task = asyncio.create_task(server.serve_forever())
        
        # Wait for server to start
        await asyncio.sleep(0.1)
        
        # Test read methods
        await test_read_methods()
        
        # Stop server
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)

asyncio.run(demonstrate_stream_reader_methods())
```

### StreamWriter Methods and Flow Control

```python
import asyncio
import time

async def demonstrate_stream_writer_methods():
    """Demonstrate StreamWriter methods and flow control"""
    
    print("=== StreamWriter Methods and Flow Control ===")
    
    async def flow_control_server(reader, writer):
        """Server that demonstrates flow control"""
        client_addr = writer.get_extra_info('peername')
        print(f"   Server: Client {client_addr} connected")
        
        # Get transport info
        transport = writer.transport
        print(f"   Server: Transport type: {type(transport).__name__}")
        print(f"   Server: Socket info: {writer.get_extra_info('socket')}")
        
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                
                message = data.decode('utf-8', errors='ignore')
                print(f"   Server: Received: {message[:50]}...")
                
                # Echo with flow control demonstration
                response = f"Received {len(data)} bytes\n"
                writer.write(response.encode('utf-8'))
                
                # Demonstrate drain() for flow control
                await writer.drain()
                
                # Check if transport can accept more data
                if transport.is_closing():
                    print("   Server: Transport is closing")
                    break
        
        except Exception as e:
            print(f"   Server: Error: {e}")
        
        finally:
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
                print(f"   Server: Connection to {client_addr} closed")
    
    async def flow_control_client():
        """Client that demonstrates various writer methods"""
        
        reader, writer = await asyncio.open_connection('localhost', 8890)
        print("   Client: Connected")
        
        try:
            # Method 1: write() - buffer data
            print("\n   1. Testing write() and drain():")
            writer.write(b"Hello, ")
            writer.write(b"World!\n")
            
            # drain() ensures data is actually sent
            await writer.drain()
            print("   Client: Data drained to network")
            
            # Read response
            response = await reader.readline()
            print(f"   Client: Response: {response.decode().strip()}")
            
            # Method 2: writelines() - write multiple lines
            print("\n   2. Testing writelines():")
            lines = [b"Line 1\n", b"Line 2\n", b"Line 3\n"]
            writer.writelines(lines)
            await writer.drain()
            
            response = await reader.readline()
            print(f"   Client: Response: {response.decode().strip()}")
            
            # Method 3: Large data transfer with flow control
            print("\n   3. Testing large data transfer:")
            large_data = b"X" * 10000  # 10KB of data
            
            start_time = time.time()
            writer.write(large_data)
            await writer.drain()  # This might block if receiver is slow
            end_time = time.time()
            
            print(f"   Client: Sent {len(large_data)} bytes in {end_time - start_time:.3f}s")
            
            response = await reader.readline()
            print(f"   Client: Response: {response.decode().strip()}")
            
            # Method 4: Check connection state
            print("\n   4. Connection state:")
            print(f"   Client: Writer is closing: {writer.is_closing()}")
            print(f"   Client: Can write EOF: {writer.can_write_eof()}")
            
            if writer.can_write_eof():
                writer.write_eof()
                print("   Client: Wrote EOF")
        
        finally:
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
                print("   Client: Connection closed")
    
    # Start flow control server
    server = await asyncio.start_server(
        flow_control_server,
        'localhost',
        8890
    )
    
    async with server:
        server_task = asyncio.create_task(server.serve_forever())
        
        await asyncio.sleep(0.1)  # Let server start
        
        # Test flow control
        await flow_control_client()
        
        # Stop server
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)

asyncio.run(demonstrate_stream_writer_methods())
```

## 7.2 Opening Connections

Understanding different ways to establish connections is crucial for building robust network applications.

### Basic Connection Patterns

```python
import asyncio
import ssl
import socket

async def demonstrate_connection_patterns():
    """Demonstrate different ways to open connections"""
    
    print("=== Connection Patterns ===")
    
    # Create a simple HTTP-like server for testing
    async def http_like_server(reader, writer):
        """Simple HTTP-like server for testing"""
        client_addr = writer.get_extra_info('peername')
        print(f"   HTTP Server: Connection from {client_addr}")
        
        try:
            # Read request line
            request_line = await reader.readline()
            request = request_line.decode('utf-8').strip()
            print(f"   HTTP Server: Request: {request}")
            
            # Read headers until empty line
            headers = {}
            while True:
                header_line = await reader.readline()
                if header_line == b'\r\n' or header_line == b'\n':
                    break
                
                header = header_line.decode('utf-8').strip()
                if ':' in header:
                    key, value = header.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            print(f"   HTTP Server: Headers: {headers}")
            
            # Send response
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 13\r\n"
                "\r\n"
                "Hello, World!"
            )
            
            writer.write(response.encode('utf-8'))
            await writer.drain()
            
        except Exception as e:
            print(f"   HTTP Server: Error: {e}")
        
        finally:
            writer.close()
            await writer.wait_closed()
    
    # Start HTTP-like server
    server = await asyncio.start_server(http_like_server, 'localhost', 8891)
    
    async with server:
        server_task = asyncio.create_task(server.serve_forever())
        await asyncio.sleep(0.1)  # Let server start
        
        # Pattern 1: Basic connection
        print("1. Basic connection:")
        try:
            reader, writer = await asyncio.open_connection('localhost', 8891)
            
            # Send HTTP request
            request = (
                "GET / HTTP/1.1\r\n"
                "Host: localhost\r\n"
                "User-Agent: AsyncioClient/1.0\r\n"
                "\r\n"
            )
            
            writer.write(request.encode('utf-8'))
            await writer.drain()
            
            # Read response
            response_line = await reader.readline()
            print(f"   Response: {response_line.decode().strip()}")
            
            writer.close()
            await writer.wait_closed()
        
        except Exception as e:
            print(f"   Basic connection error: {e}")
        
        # Pattern 2: Connection with timeout
        print("\n2. Connection with timeout:")
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection('localhost', 8891),
                timeout=5.0
            )
            
            print("   Connected with timeout")
            
            # Quick request
            writer.write(b"GET /quick HTTP/1.1\r\n\r\n")
            await writer.drain()
            
            # Read with timeout
            response = await asyncio.wait_for(
                reader.readline(),
                timeout=2.0
            )
            print(f"   Quick response: {response.decode().strip()}")
            
            writer.close()
            await writer.wait_closed()
        
        except asyncio.TimeoutError:
            print("   Connection timeout")
        except Exception as e:
            print(f"   Timeout connection error: {e}")
        
        # Pattern 3: Connection to external service (if available)
        print("\n3. External connection test:")
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection('httpbin.org', 80),
                timeout=5.0
            )
            
            # Send HTTP request to httpbin
            request = (
                "GET /get HTTP/1.1\r\n"
                "Host: httpbin.org\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            
            writer.write(request.encode('utf-8'))
            await writer.drain()
            
            # Read status line
            status_line = await reader.readline()
            print(f"   External response: {status_line.decode().strip()}")
            
            writer.close()
            await writer.wait_closed()
        
        except Exception as e:
            print(f"   External connection error: {e}")
        
        # Stop server
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)

asyncio.run(demonstrate_connection_patterns())
```

### Connection with Custom Socket Options

```python
import asyncio
import socket

async def demonstrate_custom_socket_connections():
    """Demonstrate connections with custom socket options"""
    
    print("=== Custom Socket Connections ===")
    
    async def socket_info_server(reader, writer):
        """Server that reports socket information"""
        sock = writer.get_extra_info('socket')
        peername = writer.get_extra_info('peername')
        sockname = writer.get_extra_info('sockname')
        
        print(f"   Server: Connection from {peername} to {sockname}")
        print(f"   Server: Socket type: {sock.type}")
        print(f"   Server: Socket family: {sock.family}")
        
        # Send socket info back to client
        info = (
            f"Socket Family: {sock.family.name}\n"
            f"Socket Type: {sock.type.name}\n"
            f"Local Address: {sockname}\n"
            f"Remote Address: {peername}\n"
        )
        
        writer.write(info.encode('utf-8'))
        await writer.drain()
        
        # Keep connection open briefly
        await asyncio.sleep(1)
        
        writer.close()
        await writer.wait_closed()
    
    # Start socket info server
    server = await asyncio.start_server(socket_info_server, 'localhost', 8892)
    
    async with server:
        server_task = asyncio.create_task(server.serve_forever())
        await asyncio.sleep(0.1)
        
        # Method 1: Connection with custom socket
        print("1. Connection with custom socket options:")
        
        # Create custom socket
        custom_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Set socket options
        custom_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        custom_sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        
        # Set TCP options if available
        if hasattr(socket, 'TCP_NODELAY'):
            custom_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        try:
            # Connect using custom socket
            await asyncio.get_event_loop().sock_connect(
                custom_sock, ('localhost', 8892)
            )
            
            # Create streams from connected socket
            reader, writer = await asyncio.open_connection(sock=custom_sock)
            
            print("   Connected with custom socket")
            
            # Read socket info from server
            info = await reader.read(1024)
            print(f"   Socket info:\n{info.decode()}")
            
            writer.close()
            await writer.wait_closed()
        
        except Exception as e:
            print(f"   Custom socket connection error: {e}")
            custom_sock.close()
        
        # Method 2: Connection with family specification
        print("\n2. IPv6 connection (if available):")
        try:
            # Try IPv6 connection
            reader, writer = await asyncio.open_connection(
                '::1',  # IPv6 loopback
                8892,
                family=socket.AF_INET6
            )
            
            print("   Connected via IPv6")
            
            info = await reader.read(1024)
            print(f"   IPv6 Socket info:\n{info.decode()}")
            
            writer.close()
            await writer.wait_closed()
        
        except Exception as e:
            print(f"   IPv6 connection error: {e}")
        
        # Method 3: Unix socket connection (if supported)
        print("\n3. Unix socket connection:")
        import tempfile
        import os
        
        # Create temporary unix socket server
        sock_path = None
        unix_server = None
        
        try:
            # Create temporary socket file
            with tempfile.NamedTemporaryFile(delete=False) as f:
                sock_path = f.name
            os.unlink(sock_path)  # Remove the file, keep the name
            
            # Start Unix socket server
            unix_server = await asyncio.start_unix_server(
                socket_info_server, sock_path
            )
            
            print(f"   Unix server started at {sock_path}")
            
            # Connect to Unix socket
            reader, writer = await asyncio.open_unix_connection(sock_path)
            
            print("   Connected via Unix socket")
            
            info = await reader.read(1024)
            print(f"   Unix Socket info:\n{info.decode()}")
            
            writer.close()
            await writer.wait_closed()
        
        except Exception as e:
            print(f"   Unix socket connection error: {e}")
        
        finally:
            if unix_server:
                unix_server.close()
                await unix_server.wait_closed()
            if sock_path and os.path.exists(sock_path):
                os.unlink(sock_path)
        
        # Stop main server
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)

asyncio.run(demonstrate_custom_socket_connections())
```

### Connection Pooling and Reuse

```python
import asyncio
import time
import weakref
from collections import defaultdict

class ConnectionPool:
    """Simple connection pool for demonstration"""
    
    def __init__(self, host, port, max_connections=5):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.available_connections = asyncio.Queue(maxsize=max_connections)
        self.active_connections = set()
        self.stats = defaultdict(int)
        self._closed = False
    
    async def get_connection(self):
        """Get a connection from the pool"""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        try:
            # Try to get existing connection
            reader, writer = self.available_connections.get_nowait()
            
            # Check if connection is still alive
            if not writer.is_closing():
                self.active_connections.add(writer)
                self.stats['reused'] += 1
                print(f"   Pool: Reused existing connection")
                return reader, writer
            else:
                print(f"   Pool: Found dead connection, creating new one")
        
        except asyncio.QueueEmpty:
            pass
        
        # Create new connection
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
            self.active_connections.add(writer)
            self.stats['created'] += 1
            print(f"   Pool: Created new connection")
            return reader, writer
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"   Pool: Error creating connection: {e}")
            raise
    
    async def return_connection(self, reader, writer):
        """Return a connection to the pool"""
        if writer in self.active_connections:
            self.active_connections.remove(writer)
        
        if self._closed or writer.is_closing():
            # Pool is closed or connection is dead
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
            return
        
        try:
            # Return to pool if there's space
            self.available_connections.put_nowait((reader, writer))
            print(f"   Pool: Returned connection to pool")
        except asyncio.QueueFull:
            # Pool is full, close the connection
            writer.close()
            await writer.wait_closed()
            print(f"   Pool: Pool full, closed connection")
    
    async def close(self):
        """Close all connections in the pool"""
        self._closed = True
        
        # Close active connections
        for writer in list(self.active_connections):
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
        
        # Close available connections
        while not self.available_connections.empty():
            try:
                reader, writer = self.available_connections.get_nowait()
                if not writer.is_closing():
                    writer.close()
                    await writer.wait_closed()
            except asyncio.QueueEmpty:
                break
        
        print(f"   Pool: Closed all connections")
    
    def get_stats(self):
        """Get connection pool statistics"""
        return {
            'created': self.stats['created'],
            'reused': self.stats['reused'],
            'errors': self.stats['errors'],
            'active': len(self.active_connections),
            'available': self.available_connections.qsize()
        }

async def demonstrate_connection_pooling():
    """Demonstrate connection pooling"""
    
    print("=== Connection Pooling ===")
    
    # Simple echo server for testing
    async def pooling_test_server(reader, writer):
        """Echo server for pool testing"""
        client_addr = writer.get_extra_info('peername')
        
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                
                # Echo with connection info
                response = f"Echo from {client_addr}: {data.decode()}"
                writer.write(response.encode())
                await writer.drain()
        
        except Exception as e:
            print(f"   Server: Error with {client_addr}: {e}")
        
        finally:
            writer.close()
            await writer.wait_closed()
    
    # Start test server
    server = await asyncio.start_server(pooling_test_server, 'localhost', 8893)
    
    async with server:
        server_task = asyncio.create_task(server.serve_forever())
        await asyncio.sleep(0.1)
        
        # Create connection pool
        pool = ConnectionPool('localhost', 8893, max_connections=3)
        
        async def pool_client(client_id, request_count):
            """Client that uses connection pool"""
            print(f"   Client {client_id}: Starting {request_count} requests")
            
            for i in range(request_count):
                try:
                    # Get connection from pool
                    reader, writer = await pool.get_connection()
                    
                    # Send request
                    message = f"Request {i} from client {client_id}\n"
                    writer.write(message.encode())
                    await writer.drain()
                    
                    # Read response
                    response = await reader.readline()
                    print(f"   Client {client_id}: {response.decode().strip()}")
                    
                    # Simulate some work
                    await asyncio.sleep(0.1)
                    
                    # Return connection to pool
                    await pool.return_connection(reader, writer)
                
                except Exception as e:
                    print(f"   Client {client_id}: Error: {e}")
            
            print(f"   Client {client_id}: Finished")
        
        print("1. Testing connection pool with multiple clients:")
        
        # Run multiple clients concurrently
        client_tasks = [
            pool_client(f"C{i}", 3)
            for i in range(4)
        ]
        
        await asyncio.gather(*client_tasks)
        
        # Show pool statistics
        print(f"\n2. Pool statistics: {pool.get_stats()}")
        
        # Close pool
        await pool.close()
        
        # Stop server
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)

asyncio.run(demonstrate_connection_pooling())
```

## 7.3 Starting Servers

Creating servers is essential for building network applications. Understanding different server patterns helps in choosing the right approach for your use case.

### Basic Server Patterns

```python
import asyncio
import json
import time
from typing import Dict, Any

async def demonstrate_server_patterns():
    """Demonstrate different server patterns"""
    
    print("=== Server Patterns ===")
    
    # Pattern 1: Simple Echo Server
    async def echo_handler(reader, writer):
        """Simple echo server handler"""
        addr = writer.get_extra_info('peername')
        print(f"   Echo Server: Client {addr} connected")
        
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                
                message = data.decode('utf-8').strip()
                response = f"ECHO: {message}\n"
                
                writer.write(response.encode('utf-8'))
                await writer.drain()
        
        except Exception as e:
            print(f"   Echo Server: Error with {addr}: {e}")
        
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"   Echo Server: Client {addr} disconnected")
    
    # Pattern 2: JSON API Server
    async def json_api_handler(reader, writer):
        """JSON API server handler"""
        addr = writer.get_extra_info('peername')
        print(f"   API Server: Client {addr} connected")
        
        try:
            while True:
                # Read request line
                request_line = await reader.readline()
                if not request_line:
                    break
                
                try:
                    # Parse JSON request
                    request_data = json.loads(request_line.decode('utf-8'))
                    command = request_data.get('command')
                    params = request_data.get('params', {})
                    
                    print(f"   API Server: Command '{command}' from {addr}")
                    
                    # Process command
                    if command == 'ping':
                        response = {'status': 'success', 'result': 'pong'}
                    elif command == 'time':
                        response = {'status': 'success', 'result': time.time()}
                    elif command == 'echo':
                        response = {'status': 'success', 'result': params.get('message', '')}
                    else:
                        response = {'status': 'error', 'message': f'Unknown command: {command}'}
                    
                    # Send JSON response
                    response_line = json.dumps(response) + '\n'
                    writer.write(response_line.encode('utf-8'))
                    await writer.drain()
                
                except json.JSONDecodeError:
                    error_response = {'status': 'error', 'message': 'Invalid JSON'} 
                    response_line = json.dumps(error_response) + '\n'
                    writer.write(response_line.encode('utf-8'))
                    await writer.drain()
                
                except Exception as e:
                    error_response = {'status': 'error', 'message': str(e)}
                    response_line = json.dumps(error_response) + '\n'
                    writer.write(response_line.encode('utf-8'))
                    await writer.drain()
        
        except Exception as e:
            print(f"   API Server: Error with {addr}: {e}")
        
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"   API Server: Client {addr} disconnected")
    
    # Pattern 3: Chat Server
    class ChatServer:
        def __init__(self):
            self.clients: Dict[str, Any] = {}
            self.message_history = []
        
        async def handle_client(self, reader, writer):
            """Handle chat client"""
            addr = writer.get_extra_info('peername')
            client_id = f"Client_{addr[0]}_{addr[1]}"
            
            print(f"   Chat Server: {client_id} joined")
            
            # Register client
            self.clients[client_id] = {
                'reader': reader,
                'writer': writer,
                'addr': addr
            }
            
            # Send welcome message
            welcome_msg = f"Welcome {client_id}! Connected clients: {len(self.clients)}\n"
            writer.write(welcome_msg.encode('utf-8'))
            await writer.drain()
            
            # Broadcast join notification
            join_msg = f"{client_id} joined the chat\n"
            await self.broadcast_message(join_msg, exclude=client_id)
            
            try:
                while True:
                    data = await reader.read(1024)
                    if not data:
                        break
                    
                    message = data.decode('utf-8').strip()
                    if message:
                        # Store message
                        chat_message = f"{client_id}: {message}"
                        self.message_history.append(chat_message)
                        
                        # Broadcast to all clients
                        broadcast_msg = f"{chat_message}\n"
                        await self.broadcast_message(broadcast_msg)
            
            except Exception as e:
                print(f"   Chat Server: Error with {client_id}: {e}")
            
            finally:
                # Remove client
                if client_id in self.clients:
                    del self.clients[client_id]
                
                writer.close()
                await writer.wait_closed()
                
                # Broadcast leave notification
                leave_msg = f"{client_id} left the chat\n"
                await self.broadcast_message(leave_msg)
                
                print(f"   Chat Server: {client_id} left")
        
        async def broadcast_message(self, message, exclude=None):
            """Broadcast message to all connected clients"""
            if not self.clients:
                return
            
            tasks = []
            for client_id, client_info in self.clients.items():
                if client_id != exclude:
                    task = self._send_to_client(client_info['writer'], message)
                    tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        
        async def _send_to_client(self, writer, message):
            """Send message to a specific client"""
            try:
                if not writer.is_closing():
                    writer.write(message.encode('utf-8'))
                    await writer.drain()
            except Exception as e:
                print(f"   Chat Server: Error sending message: {e}")
    
    # Test the servers
    print("1. Starting Echo Server on port 8894:")
    echo_server = await asyncio.start_server(echo_handler, 'localhost', 8894)
    
    print("2. Starting JSON API Server on port 8895:")
    api_server = await asyncio.start_server(json_api_handler, 'localhost', 8895)
    
    print("3. Starting Chat Server on port 8896:")
    chat_server_instance = ChatServer()
    chat_server = await asyncio.start_server(
        chat_server_instance.handle_client, 'localhost', 8896
    )
    
    async with echo_server, api_server, chat_server:
        # Start serving
        echo_task = asyncio.create_task(echo_server.serve_forever())
        api_task = asyncio.create_task(api_server.serve_forever())
        chat_task = asyncio.create_task(chat_server.serve_forever())
        
        await asyncio.sleep(0.1)  # Let servers start
        
        # Test Echo Server
        print("\n4. Testing Echo Server:")
        try:
            reader, writer = await asyncio.open_connection('localhost', 8894)
            writer.write(b"Hello Echo Server!\n")
            await writer.drain()
            
            response = await reader.readline()
            print(f"   Echo response: {response.decode().strip()}")
            
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"   Echo test error: {e}")
        
        # Test JSON API Server
        print("\n5. Testing JSON API Server:")
        try:
            reader, writer = await asyncio.open_connection('localhost', 8895)
            
            # Test ping command
            ping_request = json.dumps({'command': 'ping'}) + '\n'
            writer.write(ping_request.encode('utf-8'))
            await writer.drain()
            
            response = await reader.readline()
            ping_response = json.loads(response.decode())
            print(f"   API ping response: {ping_response}")
            
            # Test echo command
            echo_request = json.dumps({
                'command': 'echo',
                'params': {'message': 'Hello API!'}
            }) + '\n'
            writer.write(echo_request.encode('utf-8'))
            await writer.drain()
            
            response = await reader.readline()
            echo_response = json.loads(response.decode())
            print(f"   API echo response: {echo_response}")
            
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"   API test error: {e}")
        
        # Test Chat Server (brief test)
        print("\n6. Testing Chat Server:")
        try:
            reader, writer = await asyncio.open_connection('localhost', 8896)
            
            # Read welcome message
            welcome = await reader.readline()
            print(f"   Chat welcome: {welcome.decode().strip()}")
            
            # Send a message
            writer.write(b"Hello everyone!\n")
            await writer.drain()
            
            await asyncio.sleep(0.1)  # Let message process
            
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"   Chat test error: {e}")
        
        print("\n7. Servers are running. Stopping...")
        
        # Stop all servers
        echo_task.cancel()
        api_task.cancel()
        chat_task.cancel()
        
        await asyncio.gather(echo_task, api_task, chat_task, return_exceptions=True)

asyncio.run(demonstrate_server_patterns())
```

This completes Chapter 7 covering the fundamentals of Streams in asyncio. The chapter demonstrates:

1. **StreamReader and StreamWriter basics** - Understanding the high-level interface
2. **Opening Connections** - Various patterns for establishing connections
3. **Starting Servers** - Different server patterns for various use cases

Each section includes practical, runnable examples that show real-world usage patterns. The examples progress from basic concepts to more advanced patterns like connection pooling and multi-client servers.

Would you like me to continue with Chapter 8 (Transports and Protocols) or would you prefer to focus on any specific area from Chapter 7?