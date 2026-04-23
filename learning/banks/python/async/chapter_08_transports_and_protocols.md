# Chapter 8: Transports and Protocols - Low-Level Network I/O

## 8.1 The Transport/Protocol Abstraction

Transports and Protocols form the foundation of asyncio's networking layer. While Streams provide a high-level interface, understanding transports and protocols gives you fine-grained control over network communication and is essential for building high-performance network applications.

### Understanding the Architecture

```python
import asyncio
import time
from typing import Optional

class BasicProtocol(asyncio.Protocol):
    """Basic protocol to understand the architecture"""
    
    def __init__(self):
        self.transport = None
        self.data_received_count = 0
        self.bytes_received = 0
        self.connection_time = None
    
    def connection_made(self, transport):
        """Called when connection is established"""
        self.transport = transport
        self.connection_time = time.time()
        
        # Get connection information
        peername = transport.get_extra_info('peername')
        sockname = transport.get_extra_info('sockname')
        
        print(f"   Protocol: Connection made")
        print(f"   Protocol: Local address: {sockname}")
        print(f"   Protocol: Remote address: {peername}")
        print(f"   Protocol: Transport: {type(transport).__name__}")
    
    def data_received(self, data):
        """Called when data is received"""
        self.data_received_count += 1
        self.bytes_received += len(data)
        
        print(f"   Protocol: Received {len(data)} bytes (total: {self.bytes_received})")
        print(f"   Protocol: Data: {data[:50]!r}...")  # Show first 50 chars
        
        # Echo the data back
        if self.transport:
            echo_data = f"ECHO: {data.decode('utf-8', errors='ignore')}"
            self.transport.write(echo_data.encode('utf-8'))
    
    def connection_lost(self, exc):
        """Called when connection is lost"""
        if exc:
            print(f"   Protocol: Connection lost due to error: {exc}")
        else:
            print(f"   Protocol: Connection closed normally")
        
        if self.connection_time:
            duration = time.time() - self.connection_time
            print(f"   Protocol: Connection duration: {duration:.2f}s")
        
        print(f"   Protocol: Final stats - Messages: {self.data_received_count}, "
              f"Bytes: {self.bytes_received}")

async def demonstrate_transport_protocol_basics():
    """Demonstrate basic transport/protocol concepts"""
    
    print("=== Transport/Protocol Basics ===")
    
    # Create server using protocol
    loop = asyncio.get_event_loop()
    
    # Create server
    server = await loop.create_server(BasicProtocol, 'localhost', 8900)
    print("1. Started protocol-based server on localhost:8900")
    
    async with server:
        # Start serving in background
        server_task = asyncio.create_task(server.serve_forever())
        await asyncio.sleep(0.1)  # Let server start
        
        # Connect and test
        print("\n2. Testing with multiple clients:")
        
        async def test_client(client_id, messages):
            """Test client using streams to connect to protocol server"""
            try:
                reader, writer = await asyncio.open_connection('localhost', 8900)
                print(f"   Client {client_id}: Connected")
                
                for i, message in enumerate(messages):
                    # Send message
                    writer.write(f"{message}\n".encode('utf-8'))
                    await writer.drain()
                    
                    # Read echo
                    response = await reader.readline()
                    print(f"   Client {client_id}: Sent '{message}', "
                          f"got '{response.decode().strip()}'")
                    
                    await asyncio.sleep(0.1)
                
                writer.close()
                await writer.wait_closed()
                print(f"   Client {client_id}: Disconnected")
            
            except Exception as e:
                print(f"   Client {client_id}: Error: {e}")
        
        # Test with multiple clients
        client_tasks = [
            test_client("A", ["Hello", "World"]),
            test_client("B", ["Foo", "Bar", "Baz"]),
        ]
        
        await asyncio.gather(*client_tasks)
        
        # Stop server
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)

asyncio.run(demonstrate_transport_protocol_basics())
```

### Advanced Protocol Features

```python
import asyncio
import struct
import json
from enum import Enum

class MessageType(Enum):
    PING = 1
    PONG = 2
    DATA = 3
    ERROR = 4

class AdvancedProtocol(asyncio.Protocol):
    """Advanced protocol with framing and message types"""
    
    def __init__(self):
        self.transport = None
        self.buffer = b''
        self.stats = {
            'messages_received': 0,
            'messages_sent': 0,
            'bytes_received': 0,
            'bytes_sent': 0,
            'errors': 0
        }
    
    def connection_made(self, transport):
        """Connection established"""
        self.transport = transport
        peername = transport.get_extra_info('peername')
        print(f"   Advanced Protocol: Connected to {peername}")
        
        # Send initial ping
        self.send_message(MessageType.PING, {"timestamp": time.time()})
    
    def data_received(self, data):
        """Handle incoming data with framing"""
        self.buffer += data
        self.stats['bytes_received'] += len(data)
        
        # Process complete messages
        while len(self.buffer) >= 4:  # Need at least 4 bytes for length
            # Read message length
            msg_length = struct.unpack('>I', self.buffer[:4])[0]
            
            # Check if we have complete message
            if len(self.buffer) < 4 + msg_length:
                break  # Wait for more data
            
            # Extract message
            msg_data = self.buffer[4:4 + msg_length]
            self.buffer = self.buffer[4 + msg_length:]
            
            # Process message
            self.process_message(msg_data)
    
    def process_message(self, msg_data):
        """Process a complete message"""
        try:
            # Parse message
            msg_type_byte = msg_data[0]
            msg_payload = msg_data[1:]
            
            msg_type = MessageType(msg_type_byte)
            payload = json.loads(msg_payload.decode('utf-8'))
            
            self.stats['messages_received'] += 1
            
            print(f"   Advanced Protocol: Received {msg_type.name}: {payload}")
            
            # Handle different message types
            if msg_type == MessageType.PING:
                # Respond with pong
                pong_payload = {
                    "original_timestamp": payload.get("timestamp"),
                    "pong_timestamp": time.time()
                }
                self.send_message(MessageType.PONG, pong_payload)
            
            elif msg_type == MessageType.DATA:
                # Echo data back
                echo_payload = {
                    "echoed_data": payload.get("data"),
                    "echo_timestamp": time.time()
                }
                self.send_message(MessageType.DATA, echo_payload)
            
            elif msg_type == MessageType.PONG:
                # Calculate round-trip time
                original_ts = payload.get("original_timestamp")
                if original_ts:
                    rtt = time.time() - original_ts
                    print(f"   Advanced Protocol: Round-trip time: {rtt:.3f}s")
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"   Advanced Protocol: Error processing message: {e}")
            
            # Send error response
            error_payload = {"error": str(e)}
            self.send_message(MessageType.ERROR, error_payload)
    
    def send_message(self, msg_type: MessageType, payload: dict):
        """Send a framed message"""
        try:
            # Serialize payload
            payload_bytes = json.dumps(payload).encode('utf-8')
            
            # Create message (type + payload)
            message = bytes([msg_type.value]) + payload_bytes
            
            # Create frame (length + message)
            frame = struct.pack('>I', len(message)) + message
            
            # Send frame
            self.transport.write(frame)
            self.stats['messages_sent'] += 1
            self.stats['bytes_sent'] += len(frame)
            
            print(f"   Advanced Protocol: Sent {msg_type.name}: {payload}")
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"   Advanced Protocol: Error sending message: {e}")
    
    def connection_lost(self, exc):
        """Connection lost"""
        if exc:
            print(f"   Advanced Protocol: Connection lost: {exc}")
        else:
            print(f"   Advanced Protocol: Connection closed")
        
        print(f"   Advanced Protocol: Final stats: {self.stats}")

class AdvancedClient(asyncio.Protocol):
    """Client protocol that works with AdvancedProtocol"""
    
    def __init__(self):
        self.transport = None
        self.buffer = b''
        self.connected = asyncio.Event()
        self.responses = asyncio.Queue()
    
    def connection_made(self, transport):
        """Connection established"""
        self.transport = transport
        print(f"   Advanced Client: Connected")
        self.connected.set()
    
    def data_received(self, data):
        """Handle incoming data"""
        self.buffer += data
        
        # Process complete messages
        while len(self.buffer) >= 4:
            msg_length = struct.unpack('>I', self.buffer[:4])[0]
            
            if len(self.buffer) < 4 + msg_length:
                break
            
            msg_data = self.buffer[4:4 + msg_length]
            self.buffer = self.buffer[4 + msg_length:]
            
            # Parse message
            msg_type_byte = msg_data[0]
            msg_payload = msg_data[1:]
            
            msg_type = MessageType(msg_type_byte)
            payload = json.loads(msg_payload.decode('utf-8'))
            
            # Queue response for retrieval
            asyncio.create_task(self.responses.put((msg_type, payload)))
    
    def send_message(self, msg_type: MessageType, payload: dict):
        """Send message to server"""
        payload_bytes = json.dumps(payload).encode('utf-8')
        message = bytes([msg_type.value]) + payload_bytes
        frame = struct.pack('>I', len(message)) + message
        self.transport.write(frame)
    
    async def get_response(self, timeout=5.0):
        """Get next response"""
        return await asyncio.wait_for(self.responses.get(), timeout=timeout)
    
    def connection_lost(self, exc):
        """Connection lost"""
        print(f"   Advanced Client: Disconnected")

async def demonstrate_advanced_protocols():
    """Demonstrate advanced protocol features"""
    
    print("=== Advanced Protocol Features ===")
    
    # Start server
    loop = asyncio.get_event_loop()
    server = await loop.create_server(AdvancedProtocol, 'localhost', 8901)
    
    async with server:
        server_task = asyncio.create_task(server.serve_forever())
        await asyncio.sleep(0.1)
        
        print("1. Testing advanced protocol with custom client:")
        
        # Create client connection
        transport, client_protocol = await loop.create_connection(
            AdvancedClient, 'localhost', 8901
        )
        
        try:
            # Wait for connection
            await client_protocol.connected.wait()
            
            # Test ping-pong
            print("\n   Testing ping-pong:")
            ping_payload = {"timestamp": time.time()}
            client_protocol.send_message(MessageType.PING, ping_payload)
            
            # Get pong response
            msg_type, response = await client_protocol.get_response()
            print(f"   Client: Received {msg_type.name}: {response}")
            
            # Test data exchange
            print("\n   Testing data exchange:")
            data_payload = {"data": "Hello Advanced Protocol!", "client_id": "test_client"}
            client_protocol.send_message(MessageType.DATA, data_payload)
            
            # Get echo response
            msg_type, response = await client_protocol.get_response()
            print(f"   Client: Received {msg_type.name}: {response}")
            
            # Send multiple messages rapidly
            print("\n   Testing rapid messages:")
            for i in range(3):
                rapid_payload = {"data": f"Rapid message {i}", "sequence": i}
                client_protocol.send_message(MessageType.DATA, rapid_payload)
            
            # Collect responses
            for i in range(3):
                msg_type, response = await client_protocol.get_response(timeout=2.0)
                print(f"   Client: Rapid response {i}: {response}")
        
        finally:
            transport.close()
        
        # Stop server
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)

asyncio.run(demonstrate_advanced_protocols())
```

## 8.2 Protocol Interface Methods

Understanding all protocol interface methods is crucial for building robust network applications. Each method serves a specific purpose in the protocol lifecycle.

### Complete Protocol Interface

```python
import asyncio
import socket
import ssl

class ComprehensiveProtocol(asyncio.Protocol):
    """Protocol demonstrating all interface methods"""
    
    def __init__(self, name="Protocol"):
        self.name = name
        self.transport = None
        self.start_time = None
        self.pause_count = 0
        self.resume_count = 0
    
    # Core Protocol Methods
    
    def connection_made(self, transport):
        """Called when connection is established"""
        self.transport = transport
        self.start_time = time.time()
        
        # Get detailed connection info
        peername = transport.get_extra_info('peername')
        sockname = transport.get_extra_info('sockname')
        socket_obj = transport.get_extra_info('socket')
        
        print(f"   {self.name}: Connection established")
        print(f"   {self.name}: Local: {sockname}, Remote: {peername}")
        
        if socket_obj:
            print(f"   {self.name}: Socket family: {socket_obj.family.name}")
            print(f"   {self.name}: Socket type: {socket_obj.type.name}")
        
        # Check for SSL
        ssl_obj = transport.get_extra_info('sslcontext')
        if ssl_obj:
            print(f"   {self.name}: SSL connection detected")
    
    def data_received(self, data):
        """Called when data is received"""
        print(f"   {self.name}: Received {len(data)} bytes: {data[:30]!r}...")
        
        # Echo with timestamp
        response = f"[{time.time():.3f}] Echo: {data.decode('utf-8', errors='ignore')}"
        if self.transport:
            self.transport.write(response.encode('utf-8'))
    
    def eof_received(self):
        """Called when EOF is received (half-close)"""
        print(f"   {self.name}: EOF received (remote closed writing)")
        
        # Return True to keep transport open for writing
        # Return False (or None) to close transport
        return False
    
    def connection_lost(self, exc):
        """Called when connection is lost or closed"""
        duration = time.time() - self.start_time if self.start_time else 0
        
        if exc:
            print(f"   {self.name}: Connection lost due to: {exc}")
        else:
            print(f"   {self.name}: Connection closed cleanly")
        
        print(f"   {self.name}: Connection duration: {duration:.2f}s")
        print(f"   {self.name}: Pause/Resume cycles: {self.pause_count}/{self.resume_count}")
    
    # Flow Control Methods
    
    def pause_writing(self):
        """Called when write buffer becomes too large"""
        self.pause_count += 1
        print(f"   {self.name}: Writing paused (buffer full)")
    
    def resume_writing(self):
        """Called when write buffer size drops below threshold"""
        self.resume_count += 1
        print(f"   {self.name}: Writing resumed (buffer drained)")

class BufferedProtocol(asyncio.BufferedProtocol):
    """Protocol using buffered interface for better performance"""
    
    def __init__(self, name="BufferedProtocol"):
        self.name = name
        self.transport = None
        self.buffer = bytearray(4096)  # Reusable buffer
        self.bytes_received = 0
    
    def connection_made(self, transport):
        """Connection established"""
        self.transport = transport
        peername = transport.get_extra_info('peername')
        print(f"   {self.name}: Connected to {peername}")
        print(f"   {self.name}: Using buffered protocol for efficiency")
    
    def get_buffer(self, sizehint):
        """Return buffer for writing received data"""
        print(f"   {self.name}: get_buffer() called with sizehint={sizehint}")
        
        # Resize buffer if needed
        if sizehint > len(self.buffer):
            self.buffer = bytearray(sizehint)
        
        return self.buffer
    
    def buffer_updated(self, nbytes):
        """Called when buffer has been updated with received data"""
        self.bytes_received += nbytes
        print(f"   {self.name}: buffer_updated() with {nbytes} bytes "
              f"(total: {self.bytes_received})")
        
        # Process the data in buffer
        data = self.buffer[:nbytes]
        print(f"   {self.name}: Processing: {data[:50]!r}...")
        
        # Echo the data
        if self.transport:
            response = f"Buffered echo: {data.decode('utf-8', errors='ignore')}"
            self.transport.write(response.encode('utf-8'))
    
    def eof_received(self):
        """EOF received"""
        print(f"   {self.name}: EOF received")
        return False
    
    def connection_lost(self, exc):
        """Connection lost"""
        if exc:
            print(f"   {self.name}: Connection lost: {exc}")
        else:
            print(f"   {self.name}: Connection closed")
        
        print(f"   {self.name}: Total bytes processed: {self.bytes_received}")

async def demonstrate_protocol_interface():
    """Demonstrate complete protocol interface"""
    
    print("=== Protocol Interface Methods ===")
    
    loop = asyncio.get_event_loop()
    
    # Test comprehensive protocol
    print("1. Testing comprehensive protocol:")
    
    server1 = await loop.create_server(
        lambda: ComprehensiveProtocol("Server"), 'localhost', 8902
    )
    
    async with server1:
        server_task1 = asyncio.create_task(server1.serve_forever())
        await asyncio.sleep(0.1)
        
        # Test normal operation
        reader, writer = await asyncio.open_connection('localhost', 8902)
        
        # Send some data
        writer.write(b"Hello comprehensive protocol!\n")
        await writer.drain()
        
        response = await reader.readline()
        print(f"   Client: Got response: {response.decode().strip()}")
        
        # Test EOF
        writer.write_eof()
        await asyncio.sleep(0.1)
        
        writer.close()
        await writer.wait_closed()
        
        server_task1.cancel()
        await asyncio.gather(server_task1, return_exceptions=True)
    
    # Test buffered protocol
    print("\n2. Testing buffered protocol:")
    
    server2 = await loop.create_server(
        lambda: BufferedProtocol("BufferedServer"), 'localhost', 8903
    )
    
    async with server2:
        server_task2 = asyncio.create_task(server2.serve_forever())
        await asyncio.sleep(0.1)
        
        reader, writer = await asyncio.open_connection('localhost', 8903)
        
        # Send data in chunks
        for i in range(3):
            message = f"Buffered message {i}\n"
            writer.write(message.encode('utf-8'))
            await writer.drain()
            
            response = await reader.readline()
            print(f"   Client: Buffered response: {response.decode().strip()}")
        
        writer.close()
        await writer.wait_closed()
        
        server_task2.cancel()
        await asyncio.gather(server_task2, return_exceptions=True)

asyncio.run(demonstrate_protocol_interface())
```

### Protocol Error Handling and Robustness

```python
import asyncio
import random
import traceback

class RobustProtocol(asyncio.Protocol):
    """Protocol with comprehensive error handling"""
    
    def __init__(self):
        self.transport = None
        self.error_count = 0
        self.message_count = 0
        self.last_activity = time.time()
        self.timeout_handle = None
    
    def connection_made(self, transport):
        """Connection established with timeout setup"""
        self.transport = transport
        self.last_activity = time.time()
        
        peername = transport.get_extra_info('peername')
        print(f"   Robust Protocol: Connected to {peername}")
        
        # Set up activity timeout
        self.reset_timeout()
        
        # Send welcome message
        welcome = "Welcome to RobustProtocol server\n"
        transport.write(welcome.encode('utf-8'))
    
    def data_received(self, data):
        """Data received with error handling"""
        self.last_activity = time.time()
        self.reset_timeout()
        
        try:
            self.message_count += 1
            message = data.decode('utf-8').strip()
            
            print(f"   Robust Protocol: Message {self.message_count}: {message}")
            
            # Simulate processing that might fail
            self.process_message(message)
            
        except UnicodeDecodeError as e:
            self.handle_error(f"Unicode decode error: {e}", data)
        except Exception as e:
            self.handle_error(f"Processing error: {e}", data)
    
    def process_message(self, message):
        """Process message with potential for errors"""
        if message.lower() == "error":
            # Simulate an error
            raise ValueError("Simulated processing error")
        
        elif message.lower() == "slow":
            # Simulate slow processing
            import time
            time.sleep(0.5)  # This would block in real code - don't do this!
            response = "Slow operation completed\n"
        
        elif message.lower() == "disconnect":
            # Client requests disconnection
            response = "Goodbye!\n"
            self.transport.write(response.encode('utf-8'))
            self.transport.close()
            return
        
        elif message.lower().startswith("echo "):
            # Echo command
            echo_text = message[5:]
            response = f"Echo: {echo_text}\n"
        
        else:
            # Default response
            response = f"Processed: {message}\n"
        
        # Send response
        if self.transport and not self.transport.is_closing():
            self.transport.write(response.encode('utf-8'))
    
    def handle_error(self, error_msg, data=None):
        """Handle errors gracefully"""
        self.error_count += 1
        print(f"   Robust Protocol: Error {self.error_count}: {error_msg}")
        
        if data:
            print(f"   Robust Protocol: Problematic data: {data[:50]!r}...")
        
        # Send error response to client
        error_response = f"Error: {error_msg}\n"
        
        try:
            if self.transport and not self.transport.is_closing():
                self.transport.write(error_response.encode('utf-8'))
        except Exception as e:
            print(f"   Robust Protocol: Failed to send error response: {e}")
    
    def reset_timeout(self):
        """Reset the inactivity timeout"""
        if self.timeout_handle:
            self.timeout_handle.cancel()
        
        # Set 30-second timeout
        loop = asyncio.get_event_loop()
        self.timeout_handle = loop.call_later(30.0, self.timeout_occurred)
    
    def timeout_occurred(self):
        """Handle inactivity timeout"""
        print(f"   Robust Protocol: Inactivity timeout, closing connection")
        
        if self.transport and not self.transport.is_closing():
            timeout_msg = "Connection timed out due to inactivity\n"
            self.transport.write(timeout_msg.encode('utf-8'))
            self.transport.close()
    
    def connection_lost(self, exc):
        """Connection lost cleanup"""
        # Cancel timeout
        if self.timeout_handle:
            self.timeout_handle.cancel()
        
        # Calculate session stats
        session_duration = time.time() - self.last_activity
        
        if exc:
            print(f"   Robust Protocol: Connection lost: {exc}")
        else:
            print(f"   Robust Protocol: Connection closed normally")
        
        print(f"   Robust Protocol: Session stats:")
        print(f"     Messages processed: {self.message_count}")
        print(f"     Errors encountered: {self.error_count}")
        print(f"     Session duration: {session_duration:.2f}s")

class ErrorTestClient:
    """Client for testing error handling"""
    
    def __init__(self):
        self.transport = None
        self.protocol = None
    
    async def connect(self, host, port):
        """Connect to server"""
        loop = asyncio.get_event_loop()
        
        class ClientProtocol(asyncio.Protocol):
            def __init__(self):
                self.data_queue = asyncio.Queue()
                self.connected = asyncio.Event()
            
            def connection_made(self, transport):
                self.connected.set()
            
            def data_received(self, data):
                asyncio.create_task(self.data_queue.put(data))
            
            async def get_response(self, timeout=5.0):
                return await asyncio.wait_for(self.data_queue.get(), timeout=timeout)
        
        self.transport, self.protocol = await loop.create_connection(
            ClientProtocol, host, port
        )
        
        await self.protocol.connected.wait()
    
    def send(self, message):
        """Send message to server"""
        if self.transport:
            self.transport.write(f"{message}\n".encode('utf-8'))
    
    async def get_response(self, timeout=5.0):
        """Get response from server"""
        data = await self.protocol.get_response(timeout)
        return data.decode('utf-8').strip()
    
    def close(self):
        """Close connection"""
        if self.transport:
            self.transport.close()

async def demonstrate_error_handling():
    """Demonstrate protocol error handling"""
    
    print("=== Protocol Error Handling ===")
    
    loop = asyncio.get_event_loop()
    
    # Start robust server
    server = await loop.create_server(RobustProtocol, 'localhost', 8904)
    
    async with server:
        server_task = asyncio.create_task(server.serve_forever())
        await asyncio.sleep(0.1)
        
        print("1. Testing normal operation:")
        
        client = ErrorTestClient()
        await client.connect('localhost', 8904)
        
        # Get welcome message
        welcome = await client.get_response()
        print(f"   Client: {welcome}")
        
        # Test normal echo
        client.send("echo Hello World")
        response = await client.get_response()
        print(f"   Client: {response}")
        
        print("\n2. Testing error handling:")
        
        # Test error condition
        client.send("error")
        error_response = await client.get_response()
        print(f"   Client: {error_response}")
        
        # Test invalid UTF-8 (send raw bytes)
        if client.transport:
            client.transport.write(b'\xff\xfe\xfd invalid utf-8\n')
        
        invalid_response = await client.get_response()
        print(f"   Client: {invalid_response}")
        
        print("\n3. Testing graceful disconnect:")
        
        # Test disconnect
        client.send("disconnect")
        goodbye = await client.get_response()
        print(f"   Client: {goodbye}")
        
        client.close()
        
        # Stop server
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)

asyncio.run(demonstrate_error_handling())
```

## 8.3 TCP Protocols

TCP protocols are the most common type in network programming. Understanding how to build robust TCP protocols is essential for most network applications.

### TCP Protocol Patterns

```python
import asyncio
import struct
import json
import hashlib
from typing import Dict, Any, Optional
from enum import Enum

class TCPMessageType(Enum):
    HEARTBEAT = 1
    REQUEST = 2
    RESPONSE = 3
    NOTIFICATION = 4
    ERROR = 5

class TCPProtocol(asyncio.Protocol):
    """Production-ready TCP protocol with framing and reliability"""
    
    def __init__(self, server_instance=None):
        self.server = server_instance
        self.transport = None
        self.buffer = bytearray()
        self.client_id = None
        self.authenticated = False
        self.last_heartbeat = time.time()
        self.stats = {
            'bytes_received': 0,
            'bytes_sent': 0,
            'messages_received': 0,
            'messages_sent': 0,
            'errors': 0
        }
    
    def connection_made(self, transport):
        """Handle new connection"""
        self.transport = transport
        peername = transport.get_extra_info('peername')
        self.client_id = f"client_{peername[0]}_{peername[1]}_{int(time.time())}"
        
        print(f"   TCP Server: New connection {self.client_id}")
        
        if self.server:
            self.server.register_client(self.client_id, self)
        
        # Send authentication challenge
        self.send_message(TCPMessageType.REQUEST, {
            "type": "auth_challenge",
            "challenge": "Please authenticate"
        })
    
    def data_received(self, data):
        """Process incoming data with proper framing"""
        self.buffer.extend(data)
        self.stats['bytes_received'] += len(data)
        
        # Process complete messages
        while len(self.buffer) >= 8:  # Header: 4 bytes length + 4 bytes checksum
            # Read message length
            msg_length = struct.unpack('>I', self.buffer[:4])[0]
            
            # Validate message length
            if msg_length > 1024 * 1024:  # 1MB max
                print(f"   TCP Server: Invalid message length {msg_length}")
                self.transport.close()
                return
            
            # Check if complete message available
            total_length = 8 + msg_length  # header + payload
            if len(self.buffer) < total_length:
                break
            
            # Extract message
            checksum = struct.unpack('>I', self.buffer[4:8])[0]
            payload = self.buffer[8:total_length]
            
            # Verify checksum
            calculated_checksum = self.calculate_checksum(payload)
            if checksum != calculated_checksum:
                print(f"   TCP Server: Checksum mismatch")
                self.stats['errors'] += 1
                self.send_error("Checksum verification failed")
                self.buffer = self.buffer[total_length:]
                continue
            
            # Process valid message
            self.process_message(payload)
            self.buffer = self.buffer[total_length:]
    
    def calculate_checksum(self, data):
        """Calculate simple checksum"""
        return hash(data) & 0xFFFFFFFF
    
    def process_message(self, payload):
        """Process a validated message"""
        try:
            # Parse message
            msg_type_byte = payload[0]
            msg_data = payload[1:]
            
            msg_type = TCPMessageType(msg_type_byte)
            message_content = json.loads(msg_data.decode('utf-8'))
            
            self.stats['messages_received'] += 1
            self.last_heartbeat = time.time()
            
            print(f"   TCP Server: {self.client_id} sent {msg_type.name}: "
                  f"{str(message_content)[:100]}")
            
            # Handle message based on type
            if msg_type == TCPMessageType.HEARTBEAT:
                self.handle_heartbeat(message_content)
            
            elif msg_type == TCPMessageType.REQUEST:
                self.handle_request(message_content)
            
            elif msg_type == TCPMessageType.RESPONSE:
                self.handle_response(message_content)
            
            elif msg_type == TCPMessageType.NOTIFICATION:
                self.handle_notification(message_content)
            
            else:
                self.send_error(f"Unknown message type: {msg_type}")
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"   TCP Server: Error processing message: {e}")
            self.send_error(f"Message processing error: {e}")
    
    def handle_heartbeat(self, content):
        """Handle heartbeat message"""
        # Respond to heartbeat
        self.send_message(TCPMessageType.HEARTBEAT, {
            "timestamp": time.time(),
            "status": "alive"
        })
    
    def handle_request(self, content):
        """Handle client requests"""
        request_type = content.get("type")
        
        if request_type == "auth":
            # Simple authentication
            password = content.get("password")
            if password == "secret123":
                self.authenticated = True
                self.send_message(TCPMessageType.RESPONSE, {
                    "type": "auth_result",
                    "success": True,
                    "client_id": self.client_id
                })
            else:
                self.send_message(TCPMessageType.RESPONSE, {
                    "type": "auth_result", 
                    "success": False,
                    "error": "Invalid password"
                })
        
        elif request_type == "data":
            if not self.authenticated:
                self.send_error("Not authenticated")
                return
            
            # Process data request
            data_request = content.get("request")
            response_data = f"Processed: {data_request}"
            
            self.send_message(TCPMessageType.RESPONSE, {
                "type": "data_response",
                "data": response_data,
                "timestamp": time.time()
            })
        
        elif request_type == "stats":
            # Send connection statistics
            self.send_message(TCPMessageType.RESPONSE, {
                "type": "stats_response",
                "stats": self.stats.copy(),
                "uptime": time.time() - self.last_heartbeat
            })
        
        else:
            self.send_error(f"Unknown request type: {request_type}")
    
    def handle_response(self, content):
        """Handle responses from client"""
        print(f"   TCP Server: Client response: {content}")
    
    def handle_notification(self, content):
        """Handle notifications from client"""
        print(f"   TCP Server: Client notification: {content}")
        
        # Broadcast to other clients if needed
        if self.server and content.get("broadcast"):
            self.server.broadcast_message(content, exclude=self.client_id)
    
    def send_message(self, msg_type: TCPMessageType, content: Dict[str, Any]):
        """Send a message with proper framing"""
        try:
            # Serialize content
            content_bytes = json.dumps(content).encode('utf-8')
            
            # Create message (type + content)
            message = bytes([msg_type.value]) + content_bytes
            
            # Calculate checksum
            checksum = self.calculate_checksum(message)
            
            # Create frame (length + checksum + message)
            frame = struct.pack('>II', len(message), checksum) + message
            
            # Send frame
            self.transport.write(frame)
            self.stats['bytes_sent'] += len(frame)
            self.stats['messages_sent'] += 1
            
        except Exception as e:
            print(f"   TCP Server: Error sending message: {e}")
            self.stats['errors'] += 1
    
    def send_error(self, error_message):
        """Send error message to client"""
        self.send_message(TCPMessageType.ERROR, {
            "error": error_message,
            "timestamp": time.time()
        })
    
    def connection_lost(self, exc):
        """Handle connection loss"""
        if exc:
            print(f"   TCP Server: {self.client_id} disconnected with error: {exc}")
        else:
            print(f"   TCP Server: {self.client_id} disconnected normally")
        
        if self.server:
            self.server.unregister_client(self.client_id)
        
        print(f"   TCP Server: {self.client_id} final stats: {self.stats}")

class TCPServer:
    """TCP server managing multiple protocol instances"""
    
    def __init__(self):
        self.clients: Dict[str, TCPProtocol] = {}
        self.server = None
        
    def create_protocol(self):
        """Factory method for creating protocol instances"""
        return TCPProtocol(server_instance=self)
    
    def register_client(self, client_id, protocol):
        """Register a new client"""
        self.clients[client_id] = protocol
        print(f"   TCP Server: Registered {client_id} (total: {len(self.clients)})")
    
    def unregister_client(self, client_id):
        """Unregister a client"""
        if client_id in self.clients:
            del self.clients[client_id]
            print(f"   TCP Server: Unregistered {client_id} (total: {len(self.clients)})")
    
    def broadcast_message(self, content, exclude=None):
        """Broadcast message to all connected clients"""
        message_content = {
            "type": "broadcast",
            "content": content,
            "timestamp": time.time()
        }
        
        for client_id, protocol in self.clients.items():
            if client_id != exclude:
                try:
                    protocol.send_message(TCPMessageType.NOTIFICATION, message_content)
                except Exception as e:
                    print(f"   TCP Server: Error broadcasting to {client_id}: {e}")
    
    async def start(self, host='localhost', port=8905):
        """Start the TCP server"""
        loop = asyncio.get_event_loop()
        self.server = await loop.create_server(self.create_protocol, host, port)
        print(f"   TCP Server: Started on {host}:{port}")
        return self.server
    
    def get_stats(self):
        """Get server statistics"""
        total_stats = {
            'connected_clients': len(self.clients),
            'total_bytes_received': 0,
            'total_bytes_sent': 0,
            'total_messages_received': 0,
            'total_messages_sent': 0,
            'total_errors': 0
        }
        
        for protocol in self.clients.values():
            stats = protocol.stats
            total_stats['total_bytes_received'] += stats['bytes_received']
            total_stats['total_bytes_sent'] += stats['bytes_sent']
            total_stats['total_messages_received'] += stats['messages_received']
            total_stats['total_messages_sent'] += stats['messages_sent']
            total_stats['total_errors'] += stats['errors']
        
        return total_stats

async def demonstrate_tcp_protocols():
    """Demonstrate TCP protocol implementation"""
    
    print("=== TCP Protocols ===")
    
    # Start TCP server
    tcp_server = TCPServer()
    server = await tcp_server.start('localhost', 8905)
    
    async with server:
        server_task = asyncio.create_task(server.serve_forever())
        await asyncio.sleep(0.1)
        
        print("1. Testing TCP protocol with authentication and data exchange:")
        
        # Connect client
        reader, writer = await asyncio.open_connection('localhost', 8905)
        
        async def read_message():
            """Read a complete framed message"""
            # Read header
            header = await reader.readexactly(8)
            msg_length, checksum = struct.unpack('>II', header)
            
            # Read payload
            payload = await reader.readexactly(msg_length)
            
            # Verify checksum
            calculated_checksum = hash(payload) & 0xFFFFFFFF
            if checksum != calculated_checksum:
                raise ValueError("Checksum mismatch")
            
            # Parse message
            msg_type = TCPMessageType(payload[0])
            content = json.loads(payload[1:].decode('utf-8'))
            
            return msg_type, content
        
        def send_message(msg_type, content):
            """Send a framed message"""
            content_bytes = json.dumps(content).encode('utf-8')
            message = bytes([msg_type.value]) + content_bytes
            checksum = hash(message) & 0xFFFFFFFF
            frame = struct.pack('>II', len(message), checksum) + message
            writer.write(frame)
        
        try:
            # Read auth challenge
            msg_type, content = await read_message()
            print(f"   Client: Received {msg_type.name}: {content}")
            
            # Send authentication
            send_message(TCPMessageType.REQUEST, {
                "type": "auth",
                "password": "secret123"
            })
            await writer.drain()
            
            # Read auth response
            msg_type, content = await read_message()
            print(f"   Client: Auth response: {content}")
            
            # Send data request
            send_message(TCPMessageType.REQUEST, {
                "type": "data",
                "request": "Hello TCP Server!"
            })
            await writer.drain()
            
            # Read data response
            msg_type, content = await read_message()
            print(f"   Client: Data response: {content}")
            
            # Send heartbeat
            send_message(TCPMessageType.HEARTBEAT, {
                "timestamp": time.time()
            })
            await writer.drain()
            
            # Read heartbeat response
            msg_type, content = await read_message()
            print(f"   Client: Heartbeat response: {content}")
            
            # Request statistics
            send_message(TCPMessageType.REQUEST, {
                "type": "stats"
            })
            await writer.drain()
            
            # Read stats response
            msg_type, content = await read_message()
            print(f"   Client: Stats response: {content}")
        
        finally:
            writer.close()
            await writer.wait_closed()
        
        # Show server stats
        print(f"\n2. Server statistics: {tcp_server.get_stats()}")
        
        # Stop server
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)

asyncio.run(demonstrate_tcp_protocols())
```

This completes the first part of Chapter 8, covering the fundamentals of transports and protocols, the complete protocol interface, and TCP protocol patterns. The examples show how to build production-ready protocols with proper framing, error handling, and reliability features.

Would you like me to continue with the remaining sections (8.4 UDP Protocols, 8.5 Custom Transports, and 8.6 When to Use Transports vs Streams)?