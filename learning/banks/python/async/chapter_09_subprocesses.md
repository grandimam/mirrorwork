# Chapter 9: Subprocesses

## 9.1 Creating Subprocesses

Working with subprocesses in asyncio allows you to execute external programs without blocking the event loop. This is essential for integrating with system tools, running scripts, or performing CPU-intensive operations in separate processes.

### Basic Subprocess Creation

```python
import asyncio
import sys
import os
import tempfile

async def demonstrate_basic_subprocess():
    """Demonstrate basic subprocess creation and execution"""
    
    print("=== Basic Subprocess Creation ===")
    
    # Method 1: Simple command execution
    print("1. Simple command execution:")
    
    try:
        # Execute a simple command
        process = await asyncio.create_subprocess_exec(
            'echo', 'Hello from subprocess!',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for completion and get output
        stdout, stderr = await process.communicate()
        
        print(f"   Return code: {process.returncode}")
        print(f"   Stdout: {stdout.decode().strip()}")
        print(f"   Stderr: {stderr.decode().strip()}")
    
    except Exception as e:
        print(f"   Error: {e}")
    
    # Method 2: Shell command execution
    print("\n2. Shell command execution:")
    
    try:
        # Execute command through shell
        process = await asyncio.create_subprocess_shell(
            'echo "Hello from shell!" | wc -c',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        print(f"   Return code: {process.returncode}")
        print(f"   Character count: {stdout.decode().strip()}")
    
    except Exception as e:
        print(f"   Error: {e}")
    
    # Method 3: Python subprocess
    print("\n3. Python subprocess:")
    
    try:
        # Execute Python code in subprocess
        python_code = """
import sys
import time
print(f"Python version: {sys.version_info[:2]}")
print("Processing data...")
time.sleep(0.1)  # Simulate work
print("Done!")
"""
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-c', python_code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        print(f"   Return code: {process.returncode}")
        print(f"   Output:\n{stdout.decode()}")
        
        if stderr:
            print(f"   Errors: {stderr.decode()}")
    
    except Exception as e:
        print(f"   Error: {e}")

asyncio.run(demonstrate_basic_subprocess())
```

### Subprocess with Input/Output Streams

```python
import asyncio
import json
import tempfile
import os

async def demonstrate_subprocess_streams():
    """Demonstrate subprocess communication using streams"""
    
    print("=== Subprocess Streams ===")
    
    # Create a Python script that processes JSON data
    script_content = '''
import sys
import json
import time

def process_data():
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            # Parse JSON input
            data = json.loads(line)
            
            # Process the data
            result = {
                "original": data,
                "processed": data.get("value", 0) * 2,
                "timestamp": time.time()
            }
            
            # Output JSON result
            print(json.dumps(result))
            sys.stdout.flush()  # Ensure immediate output
    
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    process_data()
'''
    
    # Write script to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script_content)
        script_path = f.name
    
    try:
        print("1. Creating subprocess with bidirectional communication:")
        
        # Start the subprocess
        process = await asyncio.create_subprocess_exec(
            sys.executable, script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        print(f"   Process started with PID: {process.pid}")
        
        # Function to send data to subprocess
        async def send_data():
            """Send JSON data to subprocess"""
            test_data = [
                {"id": 1, "value": 10},
                {"id": 2, "value": 25},
                {"id": 3, "value": 42},
                {"id": 4, "value": 100}
            ]
            
            for item in test_data:
                json_line = json.dumps(item) + '\n'
                print(f"   Sending: {item}")
                
                process.stdin.write(json_line.encode('utf-8'))
                await process.stdin.drain()
                
                # Small delay between sends
                await asyncio.sleep(0.1)
            
            # Close stdin to signal end of input
            process.stdin.close()
            await process.stdin.wait_closed()
            print("   Input stream closed")
        
        # Function to read output from subprocess
        async def read_output():
            """Read JSON responses from subprocess"""
            responses = []
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                try:
                    response = json.loads(line.decode('utf-8').strip())
                    responses.append(response)
                    print(f"   Received: {response}")
                except json.JSONDecodeError as e:
                    print(f"   JSON decode error: {e}")
            
            return responses
        
        # Run sender and receiver concurrently
        sender_task = asyncio.create_task(send_data())
        receiver_task = asyncio.create_task(read_output())
        
        # Wait for both to complete
        await sender_task
        responses = await receiver_task
        
        # Wait for process to finish
        return_code = await process.wait()
        
        print(f"\n2. Process completed:")
        print(f"   Return code: {return_code}")
        print(f"   Responses received: {len(responses)}")
        
        # Check for errors
        stderr_data = await process.stderr.read()
        if stderr_data:
            print(f"   Stderr: {stderr_data.decode()}")
    
    finally:
        # Clean up temporary file
        os.unlink(script_path)

asyncio.run(demonstrate_subprocess_streams())
```

### Advanced Subprocess Management

```python
import asyncio
import signal
import time
import sys
import tempfile
import os

class SubprocessManager:
    """Manager for handling multiple subprocesses"""
    
    def __init__(self):
        self.processes = {}
        self.process_counter = 0
    
    async def start_process(self, command, name=None, **kwargs):
        """Start a new subprocess"""
        self.process_counter += 1
        process_id = name or f"process_{self.process_counter}"
        
        # Default subprocess options
        default_kwargs = {
            'stdout': asyncio.subprocess.PIPE,
            'stderr': asyncio.subprocess.PIPE
        }
        default_kwargs.update(kwargs)
        
        try:
            if isinstance(command, str):
                process = await asyncio.create_subprocess_shell(command, **default_kwargs)
            else:
                process = await asyncio.create_subprocess_exec(*command, **default_kwargs)
            
            self.processes[process_id] = {
                'process': process,
                'command': command,
                'start_time': time.time(),
                'status': 'running'
            }
            
            print(f"   Manager: Started process '{process_id}' (PID: {process.pid})")
            return process_id
        
        except Exception as e:
            print(f"   Manager: Failed to start process '{process_id}': {e}")
            return None
    
    async def wait_for_process(self, process_id, timeout=None):
        """Wait for a specific process to complete"""
        if process_id not in self.processes:
            raise ValueError(f"Process '{process_id}' not found")
        
        process_info = self.processes[process_id]
        process = process_info['process']
        
        try:
            if timeout:
                return_code = await asyncio.wait_for(process.wait(), timeout=timeout)
            else:
                return_code = await process.wait()
            
            duration = time.time() - process_info['start_time']
            process_info['status'] = 'completed'
            process_info['return_code'] = return_code
            process_info['duration'] = duration
            
            print(f"   Manager: Process '{process_id}' completed "
                  f"(code: {return_code}, duration: {duration:.2f}s)")
            
            return return_code
        
        except asyncio.TimeoutError:
            print(f"   Manager: Process '{process_id}' timed out")
            process_info['status'] = 'timeout'
            raise
    
    async def terminate_process(self, process_id, force=False):
        """Terminate a specific process"""
        if process_id not in self.processes:
            raise ValueError(f"Process '{process_id}' not found")
        
        process_info = self.processes[process_id]
        process = process_info['process']
        
        if process.returncode is not None:
            print(f"   Manager: Process '{process_id}' already terminated")
            return
        
        try:
            if force:
                print(f"   Manager: Killing process '{process_id}' (PID: {process.pid})")
                process.kill()
            else:
                print(f"   Manager: Terminating process '{process_id}' (PID: {process.pid})")
                process.terminate()
            
            # Wait for termination
            await asyncio.wait_for(process.wait(), timeout=5.0)
            process_info['status'] = 'terminated'
            
        except asyncio.TimeoutError:
            print(f"   Manager: Force killing process '{process_id}'")
            process.kill()
            await process.wait()
            process_info['status'] = 'killed'
    
    async def terminate_all(self, timeout=5.0):
        """Terminate all running processes"""
        running_processes = [
            pid for pid, info in self.processes.items()
            if info['status'] == 'running' and info['process'].returncode is None
        ]
        
        if not running_processes:
            print("   Manager: No running processes to terminate")
            return
        
        print(f"   Manager: Terminating {len(running_processes)} processes")
        
        # Send terminate signal to all
        for process_id in running_processes:
            process = self.processes[process_id]['process']
            process.terminate()
        
        # Wait for graceful termination
        terminate_tasks = [
            self.wait_for_process(pid, timeout=timeout)
            for pid in running_processes
        ]
        
        results = await asyncio.gather(*terminate_tasks, return_exceptions=True)
        
        # Force kill any remaining processes
        for i, process_id in enumerate(running_processes):
            if isinstance(results[i], asyncio.TimeoutError):
                await self.terminate_process(process_id, force=True)
    
    def get_status(self):
        """Get status of all processes"""
        status = {
            'total_processes': len(self.processes),
            'running': 0,
            'completed': 0,
            'terminated': 0,
            'failed': 0
        }
        
        for info in self.processes.values():
            if info['status'] == 'running':
                status['running'] += 1
            elif info['status'] == 'completed':
                if info.get('return_code', 0) == 0:
                    status['completed'] += 1
                else:
                    status['failed'] += 1
            else:
                status['terminated'] += 1
        
        return status
    
    def get_process_info(self, process_id):
        """Get detailed info about a specific process"""
        return self.processes.get(process_id, {}).copy()

async def demonstrate_subprocess_management():
    """Demonstrate advanced subprocess management"""
    
    print("=== Advanced Subprocess Management ===")
    
    manager = SubprocessManager()
    
    # Create test scripts
    scripts = {
        'fast': '''
import time
print("Fast script starting...")
time.sleep(1)
print("Fast script completed!")
''',
        'slow': '''
import time
print("Slow script starting...")
for i in range(10):
    print(f"Slow script progress: {i+1}/10")
    time.sleep(0.5)
print("Slow script completed!")
''',
        'failing': '''
import time
print("Failing script starting...")
time.sleep(0.5)
print("About to fail...")
raise Exception("Simulated failure")
'''
    }
    
    # Write scripts to temporary files
    script_paths = {}
    for name, content in scripts.items():
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            script_paths[name] = f.name
    
    try:
        print("1. Starting multiple processes:")
        
        # Start different types of processes
        fast_id = await manager.start_process(
            [sys.executable, script_paths['fast']], 
            name='fast_process'
        )
        
        slow_id = await manager.start_process(
            [sys.executable, script_paths['slow']], 
            name='slow_process'
        )
        
        failing_id = await manager.start_process(
            [sys.executable, script_paths['failing']], 
            name='failing_process'
        )
        
        echo_id = await manager.start_process(
            'echo "Hello from shell process"',
            name='echo_process'
        )
        
        print(f"   Started processes: {[fast_id, slow_id, failing_id, echo_id]}")
        
        # Wait for fast process
        print("\n2. Waiting for fast process:")
        await manager.wait_for_process(fast_id)
        
        # Wait for echo process
        print("\n3. Waiting for echo process:")
        await manager.wait_for_process(echo_id)
        
        # Wait for failing process (should fail)
        print("\n4. Waiting for failing process:")
        try:
            await manager.wait_for_process(failing_id)
        except Exception as e:
            print(f"   Expected failure: {e}")
        
        # Show status
        print(f"\n5. Current status: {manager.get_status()}")
        
        # Try to wait for slow process with timeout
        print("\n6. Waiting for slow process with timeout:")
        try:
            await manager.wait_for_process(slow_id, timeout=2.0)
        except asyncio.TimeoutError:
            print("   Slow process timed out as expected")
        
        # Terminate remaining processes
        print("\n7. Terminating remaining processes:")
        await manager.terminate_all()
        
        # Final status
        print(f"\n8. Final status: {manager.get_status()}")
        
        # Show detailed info
        print("\n9. Process details:")
        for process_id in [fast_id, slow_id, failing_id, echo_id]:
            if process_id:
                info = manager.get_process_info(process_id)
                print(f"   {process_id}: {info}")
    
    finally:
        # Clean up temporary files
        for path in script_paths.values():
            if os.path.exists(path):
                os.unlink(path)

asyncio.run(demonstrate_subprocess_management())
```

## 9.2 Communicating with Subprocesses

Effective communication with subprocesses is crucial for building robust async applications that interact with external tools and scripts.

### Real-time Communication

```python
import asyncio
import json
import sys
import tempfile
import os

async def demonstrate_realtime_communication():
    """Demonstrate real-time bidirectional communication with subprocesses"""
    
    print("=== Real-time Subprocess Communication ===")
    
    # Create an interactive Python script
    interactive_script = '''
import sys
import json
import time

def main():
    print(json.dumps({"type": "ready", "message": "Interactive script ready"}))
    sys.stdout.flush()
    
    try:
        for line in sys.stdin:
            command = json.loads(line.strip())
            
            if command["type"] == "echo":
                response = {
                    "type": "echo_response",
                    "original": command["data"],
                    "echoed": f"Echo: {command['data']}"
                }
            
            elif command["type"] == "calculate":
                a = command["a"]
                b = command["b"]
                op = command["operation"]
                
                if op == "add":
                    result = a + b
                elif op == "multiply":
                    result = a * b
                elif op == "divide":
                    result = a / b if b != 0 else "division by zero"
                else:
                    result = "unknown operation"
                
                response = {
                    "type": "calculation_result",
                    "operation": f"{a} {op} {b}",
                    "result": result
                }
            
            elif command["type"] == "status":
                response = {
                    "type": "status_response",
                    "uptime": time.time(),
                    "memory_usage": "unknown"
                }
            
            elif command["type"] == "quit":
                response = {"type": "goodbye", "message": "Shutting down"}
                print(json.dumps(response))
                sys.stdout.flush()
                break
            
            else:
                response = {
                    "type": "error",
                    "message": f"Unknown command type: {command['type']}"
                }
            
            print(json.dumps(response))
            sys.stdout.flush()
    
    except Exception as e:
        error_response = {"type": "error", "message": str(e)}
        print(json.dumps(error_response))
        sys.stdout.flush()

if __name__ == "__main__":
    main()
'''
    
    # Write script to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(interactive_script)
        script_path = f.name
    
    try:
        print("1. Starting interactive subprocess:")
        
        # Start the interactive subprocess
        process = await asyncio.create_subprocess_exec(
            sys.executable, script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        print(f"   Process started (PID: {process.pid})")
        
        class SubprocessCommunicator:
            """Helper class for subprocess communication"""
            
            def __init__(self, process):
                self.process = process
                self.response_queue = asyncio.Queue()
                self.reader_task = None
                self.running = True
            
            async def start_reader(self):
                """Start background task to read subprocess output"""
                self.reader_task = asyncio.create_task(self._read_output())
            
            async def _read_output(self):
                """Background task to read subprocess output"""
                while self.running:
                    try:
                        line = await self.process.stdout.readline()
                        if not line:
                            break
                        
                        response = json.loads(line.decode().strip())
                        await self.response_queue.put(response)
                    
                    except json.JSONDecodeError as e:
                        error = {"type": "parse_error", "error": str(e)}
                        await self.response_queue.put(error)
                    except Exception as e:
                        error = {"type": "read_error", "error": str(e)}
                        await self.response_queue.put(error)
                        break
            
            async def send_command(self, command):
                """Send command to subprocess"""
                command_line = json.dumps(command) + '\n'
                self.process.stdin.write(command_line.encode())
                await self.process.stdin.drain()
            
            async def get_response(self, timeout=5.0):
                """Get response from subprocess"""
                return await asyncio.wait_for(
                    self.response_queue.get(), 
                    timeout=timeout
                )
            
            async def stop(self):
                """Stop the communicator"""
                self.running = False
                if self.reader_task:
                    self.reader_task.cancel()
                    await asyncio.gather(self.reader_task, return_exceptions=True)
        
        # Create communicator
        comm = SubprocessCommunicator(process)
        await comm.start_reader()
        
        try:
            # Wait for ready message
            ready_msg = await comm.get_response(timeout=5.0)
            print(f"   {ready_msg}")
            
            print("\n2. Testing interactive commands:")
            
            # Test echo command
            await comm.send_command({
                "type": "echo",
                "data": "Hello interactive subprocess!"
            })
            
            echo_response = await comm.get_response()
            print(f"   Echo: {echo_response}")
            
            # Test calculation commands
            calculations = [
                {"type": "calculate", "a": 10, "b": 5, "operation": "add"},
                {"type": "calculate", "a": 15, "b": 3, "operation": "multiply"},
                {"type": "calculate", "a": 20, "b": 4, "operation": "divide"}
            ]
            
            for calc in calculations:
                await comm.send_command(calc)
                calc_response = await comm.get_response()
                print(f"   Calculation: {calc_response}")
            
            # Test status command
            await comm.send_command({"type": "status"})
            status_response = await comm.get_response()
            print(f"   Status: {status_response}")
            
            # Test rapid commands
            print("\n3. Testing rapid command execution:")
            
            rapid_commands = [
                {"type": "echo", "data": f"Rapid message {i}"} 
                for i in range(5)
            ]
            
            # Send all commands quickly
            for cmd in rapid_commands:
                await comm.send_command(cmd)
            
            # Collect responses
            for i in range(len(rapid_commands)):
                response = await comm.get_response()
                print(f"   Rapid response {i}: {response}")
            
            # Shutdown subprocess
            print("\n4. Shutting down subprocess:")
            await comm.send_command({"type": "quit"})
            
            goodbye_msg = await comm.get_response()
            print(f"   {goodbye_msg}")
        
        finally:
            await comm.stop()
        
        # Wait for process to finish
        return_code = await process.wait()
        print(f"   Process finished with code: {return_code}")
    
    finally:
        # Clean up
        if os.path.exists(script_path):
            os.unlink(script_path)

asyncio.run(demonstrate_realtime_communication())
```

### Streaming Data Processing

```python
import asyncio
import csv
import io
import tempfile
import os
import sys

async def demonstrate_streaming_processing():
    """Demonstrate streaming data processing with subprocesses"""
    
    print("=== Streaming Data Processing ===")
    
    # Create a data processing script
    processor_script = '''
import sys
import csv
import json

def process_csv_stream():
    """Process CSV data from stdin and output JSON to stdout"""
    csv_reader = csv.DictReader(sys.stdin)
    
    for row_num, row in enumerate(csv_reader, 1):
        try:
            # Process each row
            processed_row = {
                "row_number": row_num,
                "original": dict(row),
                "processed": {
                    "name_upper": row.get("name", "").upper(),
                    "age_category": "adult" if int(row.get("age", 0)) >= 18 else "minor",
                    "email_domain": row.get("email", "").split("@")[-1] if "@" in row.get("email", "") else ""
                }
            }
            
            # Output as JSON
            print(json.dumps(processed_row))
            sys.stdout.flush()
            
        except Exception as e:
            error_row = {
                "row_number": row_num,
                "error": str(e),
                "original": dict(row)
            }
            print(json.dumps(error_row))
            sys.stdout.flush()

if __name__ == "__main__":
    process_csv_stream()
'''
    
    # Write processor script
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(processor_script)
        processor_path = f.name
    
    try:
        print("1. Starting streaming data processor:")
        
        # Start data processor
        process = await asyncio.create_subprocess_exec(
            sys.executable, processor_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        print(f"   Processor started (PID: {process.pid})")
        
        # Sample CSV data to process
        csv_data = [
            ["name", "age", "email"],
            ["John Doe", "25", "john@example.com"],
            ["Jane Smith", "17", "jane@test.org"],
            ["Bob Johnson", "35", "bob@company.net"],
            ["Alice Brown", "16", "alice@school.edu"],
            ["Charlie Wilson", "42", "charlie@business.com"],
            ["Invalid Row", "not_a_number", "invalid_email"],  # This will cause an error
            ["Mary Davis", "28", "mary@example.org"]
        ]
        
        async def stream_csv_data():
            """Stream CSV data to the processor"""
            print("   Streaming CSV data to processor:")
            
            # Send CSV header and data
            for row in csv_data:
                csv_line = ','.join(f'"{field}"' if ',' in field else field for field in row) + '\n'
                print(f"     Sending: {row}")
                
                process.stdin.write(csv_line.encode())
                await process.stdin.drain()
                
                # Small delay to simulate real-time data
                await asyncio.sleep(0.1)
            
            # Close input stream
            process.stdin.close()
            await process.stdin.wait_closed()
            print("   Finished streaming data")
        
        async def collect_results():
            """Collect processed results from the subprocess"""
            print("   Collecting processed results:")
            results = []
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                try:
                    result = json.loads(line.decode())
                    results.append(result)
                    
                    if "error" in result:
                        print(f"     Error in row {result['row_number']}: {result['error']}")
                    else:
                        processed = result["processed"]
                        print(f"     Processed row {result['row_number']}: "
                              f"{processed['name_upper']} ({processed['age_category']})")
                
                except json.JSONDecodeError as e:
                    print(f"     JSON decode error: {e}")
            
            return results
        
        # Run streaming and collection concurrently
        stream_task = asyncio.create_task(stream_csv_data())
        collect_task = asyncio.create_task(collect_results())
        
        # Wait for streaming to complete, then collect results
        await stream_task
        results = await collect_task
        
        # Wait for process to finish
        return_code = await process.wait()
        
        print(f"\n2. Processing completed:")
        print(f"   Return code: {return_code}")
        print(f"   Total rows processed: {len(results)}")
        
        # Count successes and errors
        successes = sum(1 for r in results if "error" not in r)
        errors = len(results) - successes
        print(f"   Successful: {successes}, Errors: {errors}")
        
        # Check for stderr output
        stderr_data = await process.stderr.read()
        if stderr_data:
            print(f"   Stderr: {stderr_data.decode()}")
    
    finally:
        # Clean up
        if os.path.exists(processor_path):
            os.unlink(processor_path)

asyncio.run(demonstrate_streaming_processing())
```

## 9.3 Process Streams

Process streams provide a more flexible way to work with subprocess I/O, giving you direct access to StreamReader and StreamWriter objects.

### Advanced Stream Operations

```python
import asyncio
import sys
import tempfile
import os
import time

async def demonstrate_process_streams():
    """Demonstrate advanced process stream operations"""
    
    print("=== Advanced Process Streams ===")
    
    # Create a line-based server script
    server_script = '''
import sys
import time
import threading

class LineServer:
    def __init__(self):
        self.running = True
        self.stats = {"commands": 0, "uptime": time.time()}
    
    def handle_line(self, line):
        """Process a single line of input"""
        line = line.strip()
        self.stats["commands"] += 1
        
        if line.startswith("echo "):
            return f"ECHO: {line[5:]}"
        
        elif line == "stats":
            uptime = time.time() - self.stats["uptime"]
            return f"STATS: commands={self.stats['commands']}, uptime={uptime:.1f}s"
        
        elif line == "slow":
            time.sleep(2)  # Simulate slow operation
            return "SLOW: Operation completed"
        
        elif line.startswith("repeat "):
            try:
                parts = line.split(" ", 2)
                count = int(parts[1])
                message = parts[2] if len(parts) > 2 else "default"
                return f"REPEAT: {message} " * count
            except (ValueError, IndexError):
                return "ERROR: Invalid repeat command"
        
        elif line == "quit":
            self.running = False
            return "GOODBYE: Server shutting down"
        
        else:
            return f"ERROR: Unknown command '{line}'"
    
    def run(self):
        """Main server loop"""
        print("LINE_SERVER_READY", flush=True)
        
        try:
            while self.running:
                line = sys.stdin.readline()
                if not line:  # EOF
                    break
                
                response = self.handle_line(line)
                print(response, flush=True)
        
        except KeyboardInterrupt:
            pass
        
        print("LINE_SERVER_SHUTDOWN", flush=True)

if __name__ == "__main__":
    server = LineServer()
    server.run()
'''
    
    # Write server script
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(server_script)
        server_path = f.name
    
    try:
        print("1. Starting line-based server process:")
        
        # Start the server process
        process = await asyncio.create_subprocess_exec(
            sys.executable, server_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Get direct access to streams
        stdin_stream = process.stdin
        stdout_stream = process.stdout
        stderr_stream = process.stderr
        
        print(f"   Server started (PID: {process.pid})")
        print(f"   Stream types: stdin={type(stdin_stream)}, stdout={type(stdout_stream)}")
        
        # Wait for server ready signal
        ready_line = await stdout_stream.readline()
        print(f"   Server ready: {ready_line.decode().strip()}")
        
        async def send_command(command, wait_for_response=True):
            """Send command and optionally wait for response"""
            print(f"   Sending: '{command}'")
            
            stdin_stream.write(f"{command}\n".encode())
            await stdin_stream.drain()
            
            if wait_for_response:
                response_line = await stdout_stream.readline()
                response = response_line.decode().strip()
                print(f"   Response: '{response}'")
                return response
            
            return None
        
        print("\n2. Testing basic commands:")
        
        # Test echo command
        await send_command("echo Hello World!")
        
        # Test stats command
        await send_command("stats")
        
        # Test repeat command
        await send_command("repeat 3 Hi!")
        
        print("\n3. Testing concurrent operations:")
        
        # Send slow command (don't wait for response immediately)
        slow_task = asyncio.create_task(send_command("slow"))
        
        # Send other commands while slow command is processing
        await send_command("echo While slow command is running...")
        await send_command("stats")
        
        # Now wait for slow command to complete
        slow_response = await slow_task
        print(f"   Slow command completed: '{slow_response}'")
        
        print("\n4. Testing stream buffering and partial reads:")
        
        # Send repeat command that generates large output
        large_command = "repeat 100 This_is_a_long_message_to_test_buffering. "
        stdin_stream.write(f"{large_command}\n".encode())
        await stdin_stream.drain()
        
        # Read response in chunks to demonstrate stream handling
        print("   Reading large response in chunks:")
        response_line = await stdout_stream.readline()
        response = response_line.decode().strip()
        
        print(f"   Large response length: {len(response)} characters")
        print(f"   First 100 chars: '{response[:100]}...'")
        
        print("\n5. Testing multiple rapid commands:")
        
        # Send multiple commands rapidly
        commands = [
            "echo Command 1",
            "echo Command 2", 
            "echo Command 3",
            "stats",
            "echo Final command"
        ]
        
        # Send all commands
        for cmd in commands:
            stdin_stream.write(f"{cmd}\n".encode())
        
        await stdin_stream.drain()
        
        # Read all responses
        for i, cmd in enumerate(commands):
            response_line = await stdout_stream.readline()
            response = response_line.decode().strip()
            print(f"   Rapid {i+1}: '{cmd}' -> '{response}'")
        
        print("\n6. Shutting down server:")
        
        # Send quit command
        await send_command("quit")
        
        # Wait for shutdown message
        shutdown_line = await stdout_stream.readline()
        print(f"   Shutdown: {shutdown_line.decode().strip()}")
        
        # Wait for process to finish
        return_code = await process.wait()
        print(f"   Process finished with return code: {return_code}")
        
        # Check for any stderr output
        stderr_data = await stderr_stream.read()
        if stderr_data:
            print(f"   Stderr: {stderr_data.decode()}")
    
    finally:
        # Clean up
        if os.path.exists(server_path):
            os.unlink(server_path)

asyncio.run(demonstrate_process_streams())
```

This completes Chapter 9 covering Subprocesses in asyncio. The chapter demonstrates:

1. **Creating Subprocesses** - Various methods for launching external processes
2. **Communicating with Subprocesses** - Real-time bidirectional communication patterns
3. **Process Streams** - Advanced stream operations for complex I/O scenarios

Each section provides practical examples showing how to integrate external processes into async applications effectively. The examples progress from basic subprocess execution to complex streaming data processing patterns.

Would you like me to continue with Chapter 10 (Exception Handling and Debugging) or focus on any specific area?