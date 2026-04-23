# Chapter 13: Context Variables and Task Context

## 13.1 Understanding Context Variables

Context variables provide a way to maintain context-specific data that automatically propagates through async call chains without explicit parameter passing. They're essential for building libraries where you need to maintain request-specific or operation-specific state.

### Basic Context Variable Usage

```python
import asyncio
import contextvars
import time
import uuid
from typing import Optional

# Create context variables
request_id: contextvars.ContextVar[str] = contextvars.ContextVar('request_id')
user_context: contextvars.ContextVar[dict] = contextvars.ContextVar('user_context', default={})
operation_start_time: contextvars.ContextVar[float] = contextvars.ContextVar('operation_start_time')

async def demonstrate_basic_context_vars():
    """Demonstrate basic context variable usage"""
    
    print("=== Basic Context Variables ===")
    
    async def log_with_context(message: str, level: str = "INFO"):
        """Log message with automatic context inclusion"""
        try:
            req_id = request_id.get()
            user = user_context.get()
            username = user.get('username', 'anonymous')
            
            timestamp = time.strftime('%H:%M:%S')
            print(f"[{timestamp}] {level} [{req_id}] [{username}] {message}")
        except LookupError:
            # Context variables not set
            timestamp = time.strftime('%H:%M:%S')
            print(f"[{timestamp}] {level} [no-context] {message}")
    
    async def business_operation(operation_name: str):
        """Business operation that uses context automatically"""
        await log_with_context(f"Starting {operation_name}")
        
        # Simulate some work
        await asyncio.sleep(0.1)
        
        # The context variables are automatically available
        start_time = operation_start_time.get()
        duration = time.time() - start_time
        
        await log_with_context(f"Completed {operation_name} in {duration:.3f}s")
        return f"{operation_name} result"
    
    async def process_request(req_data: dict):
        """Process a request with automatic context propagation"""
        # Set context for this request
        req_id_value = str(uuid.uuid4())[:8]
        request_id.set(req_id_value)
        user_context.set(req_data.get('user', {}))
        operation_start_time.set(time.time())
        
        await log_with_context("Request processing started")
        
        # All nested operations automatically inherit the context
        result1 = await business_operation("Authentication")
        result2 = await business_operation("Data Processing")
        result3 = await business_operation("Response Generation")
        
        await log_with_context("Request processing completed")
        return [result1, result2, result3]
    
    print("1. Processing multiple requests concurrently:")
    
    # Create multiple concurrent requests
    requests = [
        {"user": {"username": "alice", "role": "admin"}},
        {"user": {"username": "bob", "role": "user"}},
        {"user": {"username": "charlie", "role": "guest"}},
    ]
    
    # Process requests concurrently - each maintains its own context
    tasks = [process_request(req) for req in requests]
    results = await asyncio.gather(*tasks)
    
    print(f"\nCompleted {len(results)} requests with isolated contexts")
    
    print("\n2. Context variable access patterns:")
    
    async def demonstrate_context_access():
        """Show different ways to access context variables"""
        
        # Try to get context variable with default
        req_id_with_default = request_id.get("no-request-id")
        print(f"   Request ID (with default): {req_id_with_default}")
        
        # Try to get context variable without default (will raise LookupError)
        try:
            user = user_context.get()
            print(f"   User context: {user}")
        except LookupError:
            print("   User context: Not set")
        
        # Set context and access it
        operation_start_time.set(time.time())
        start = operation_start_time.get()
        print(f"   Operation start time: {start}")
    
    # Demonstrate outside of request context
    await demonstrate_context_access()

asyncio.run(demonstrate_basic_context_vars())
```

### Context Variable Inheritance and Propagation

```python
import asyncio
import contextvars
import json
from typing import Any, Dict

# Context variables for tracing
trace_id: contextvars.ContextVar[str] = contextvars.ContextVar('trace_id')
span_stack: contextvars.ContextVar[list] = contextvars.ContextVar('span_stack', default=[])
metadata: contextvars.ContextVar[dict] = contextvars.ContextVar('metadata', default={})

class ContextTracer:
    """Helper class for distributed tracing using context variables"""
    
    @staticmethod
    def start_trace(trace_id_value: str):
        """Start a new trace"""
        trace_id.set(trace_id_value)
        span_stack.set([])
        metadata.set({})
    
    @staticmethod
    def start_span(span_name: str, **span_metadata):
        """Start a new span within current trace"""
        current_spans = span_stack.get().copy()
        
        span = {
            'name': span_name,
            'start_time': asyncio.get_event_loop().time(),
            'metadata': span_metadata
        }
        
        current_spans.append(span)
        span_stack.set(current_spans)
        
        return len(current_spans) - 1  # Return span index
    
    @staticmethod
    def end_span(span_index: int, **result_metadata):
        """End a span and record duration"""
        current_spans = span_stack.get().copy()
        
        if span_index < len(current_spans):
            span = current_spans[span_index]
            span['end_time'] = asyncio.get_event_loop().time()
            span['duration'] = span['end_time'] - span['start_time']
            span['result'] = result_metadata
            
            span_stack.set(current_spans)
    
    @staticmethod
    def get_current_trace():
        """Get current trace information"""
        try:
            return {
                'trace_id': trace_id.get(),
                'spans': span_stack.get(),
                'metadata': metadata.get()
            }
        except LookupError:
            return None
    
    @staticmethod
    def add_metadata(key: str, value: Any):
        """Add metadata to current trace"""
        current_meta = metadata.get().copy()
        current_meta[key] = value
        metadata.set(current_meta)

async def demonstrate_context_propagation():
    """Demonstrate how context propagates through async calls"""
    
    print("=== Context Variable Propagation ===")
    
    async def database_query(query: str, params: dict = None):
        """Simulate database query with tracing"""
        span_idx = ContextTracer.start_span("database_query", query=query, params=params)
        
        try:
            # Simulate query execution
            await asyncio.sleep(0.1)
            
            # Add query result metadata
            result_count = len(params) if params else 1
            ContextTracer.add_metadata(f"query_result_count", result_count)
            
            ContextTracer.end_span(span_idx, success=True, result_count=result_count)
            return f"Query result for: {query}"
        
        except Exception as e:
            ContextTracer.end_span(span_idx, success=False, error=str(e))
            raise
    
    async def cache_lookup(key: str):
        """Simulate cache lookup with tracing"""
        span_idx = ContextTracer.start_span("cache_lookup", cache_key=key)
        
        try:
            # Simulate cache miss/hit
            import random
            is_hit = random.choice([True, False])
            
            if is_hit:
                await asyncio.sleep(0.01)  # Fast cache hit
                result = f"Cached value for {key}"
            else:
                await asyncio.sleep(0.05)  # Slower cache miss
                result = None
            
            ContextTracer.end_span(span_idx, cache_hit=is_hit, key=key)
            return result
        
        except Exception as e:
            ContextTracer.end_span(span_idx, success=False, error=str(e))
            raise
    
    async def external_api_call(endpoint: str):
        """Simulate external API call with tracing"""
        span_idx = ContextTracer.start_span("external_api", endpoint=endpoint)
        
        try:
            # Simulate API call
            await asyncio.sleep(0.15)
            
            ContextTracer.end_span(span_idx, success=True, status_code=200)
            return f"API response from {endpoint}"
        
        except Exception as e:
            ContextTracer.end_span(span_idx, success=False, error=str(e))
            raise
    
    async def complex_business_operation(user_id: str):
        """Complex operation that makes multiple sub-calls"""
        span_idx = ContextTracer.start_span("business_operation", user_id=user_id)
        
        try:
            # First, try cache
            cached_result = await cache_lookup(f"user_data_{user_id}")
            
            if cached_result:
                print(f"   Using cached data for user {user_id}")
                user_data = cached_result
            else:
                print(f"   Cache miss, querying database for user {user_id}")
                user_data = await database_query("SELECT * FROM users WHERE id = ?", {"id": user_id})
            
            # Make external API call for additional data
            external_data = await external_api_call(f"/api/user/{user_id}/profile")
            
            # Combine results
            result = {
                "user_data": user_data,
                "external_data": external_data,
                "processed_at": asyncio.get_event_loop().time()
            }
            
            ContextTracer.end_span(span_idx, success=True, user_id=user_id)
            return result
        
        except Exception as e:
            ContextTracer.end_span(span_idx, success=False, error=str(e))
            raise
    
    async def request_handler(request_id: str, user_id: str):
        """Top-level request handler"""
        # Start trace for this request
        ContextTracer.start_trace(request_id)
        
        request_span = ContextTracer.start_span("request_handler", 
                                               request_id=request_id, 
                                               user_id=user_id)
        
        try:
            print(f"\n--- Processing Request {request_id} ---")
            
            # Process the business logic
            result = await complex_business_operation(user_id)
            
            # Add final metadata
            ContextTracer.add_metadata("request_status", "completed")
            ContextTracer.add_metadata("result_size", len(str(result)))
            
            ContextTracer.end_span(request_span, success=True)
            
            return result
        
        except Exception as e:
            ContextTracer.add_metadata("request_status", "failed")
            ContextTracer.end_span(request_span, success=False, error=str(e))
            raise
    
    print("1. Processing requests with automatic context propagation:")
    
    # Process multiple requests concurrently
    requests = [
        ("req_001", "user_alice"),
        ("req_002", "user_bob"), 
        ("req_003", "user_charlie")
    ]
    
    # Each request gets its own context that propagates automatically
    tasks = [request_handler(req_id, user_id) for req_id, user_id in requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print(f"\nCompleted {len(results)} requests")
    
    print("\n2. Examining trace data:")
    
    # Start a new trace to examine
    ContextTracer.start_trace("trace_examination")
    await complex_business_operation("demo_user")
    
    trace_data = ContextTracer.get_current_trace()
    if trace_data:
        print(f"   Trace ID: {trace_data['trace_id']}")
        print(f"   Total spans: {len(trace_data['spans'])}")
        print(f"   Metadata: {trace_data['metadata']}")
        
        print("   Span details:")
        for i, span in enumerate(trace_data['spans']):
            duration = span.get('duration', 0)
            print(f"     {i+1}. {span['name']}: {duration:.3f}s")

asyncio.run(demonstrate_context_propagation())
```

### Context Variable Patterns and Best Practices

```python
import asyncio
import contextvars
import functools
import time
from typing import Optional, Callable, Any

# Common application context variables
request_context: contextvars.ContextVar[dict] = contextvars.ContextVar('request_context')
security_context: contextvars.ContextVar[dict] = contextvars.ContextVar('security_context') 
performance_context: contextvars.ContextVar[dict] = contextvars.ContextVar('performance_context')

class ContextManager:
    """Utility class for managing application context variables"""
    
    @staticmethod
    def create_request_context(request_id: str, user_id: Optional[str] = None, 
                              client_ip: Optional[str] = None, **extra):
        """Create a new request context"""
        context = {
            'request_id': request_id,
            'user_id': user_id,
            'client_ip': client_ip,
            'start_time': time.time(),
            **extra
        }
        request_context.set(context)
        return context
    
    @staticmethod
    def get_request_id() -> Optional[str]:
        """Get current request ID"""
        try:
            return request_context.get().get('request_id')
        except LookupError:
            return None
    
    @staticmethod
    def get_user_id() -> Optional[str]:
        """Get current user ID"""
        try:
            return request_context.get().get('user_id')
        except LookupError:
            return None
    
    @staticmethod
    def set_security_context(user_roles: list, permissions: list, 
                           authenticated: bool = True, **extra):
        """Set security context for current request"""
        context = {
            'authenticated': authenticated,
            'user_roles': user_roles,
            'permissions': permissions,
            **extra
        }
        security_context.set(context)
        return context
    
    @staticmethod
    def has_permission(permission: str) -> bool:
        """Check if current context has specific permission"""
        try:
            sec_ctx = security_context.get()
            return permission in sec_ctx.get('permissions', [])
        except LookupError:
            return False
    
    @staticmethod
    def track_performance(operation_name: str):
        """Start performance tracking for an operation"""
        try:
            perf_ctx = performance_context.get().copy()
        except LookupError:
            perf_ctx = {}
        
        if 'operations' not in perf_ctx:
            perf_ctx['operations'] = {}
        
        perf_ctx['operations'][operation_name] = {
            'start_time': time.time(),
            'active': True
        }
        
        performance_context.set(perf_ctx)
    
    @staticmethod
    def finish_performance_tracking(operation_name: str):
        """Finish performance tracking for an operation"""
        try:
            perf_ctx = performance_context.get().copy()
            if operation_name in perf_ctx.get('operations', {}):
                op = perf_ctx['operations'][operation_name]
                op['end_time'] = time.time()
                op['duration'] = op['end_time'] - op['start_time']
                op['active'] = False
                performance_context.set(perf_ctx)
                return op['duration']
        except LookupError:
            pass
        return None

def with_context_logging(func):
    """Decorator that adds context-aware logging to functions"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        func_name = f"{func.__module__}.{func.__name__}"
        request_id = ContextManager.get_request_id()
        user_id = ContextManager.get_user_id()
        
        log_prefix = f"[{request_id or 'no-req'}][{user_id or 'anon'}]"
        
        print(f"{log_prefix} Starting {func_name}")
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            print(f"{log_prefix} Completed {func_name} in {duration:.3f}s")
            return result
        
        except Exception as e:
            duration = time.time() - start_time
            print(f"{log_prefix} Failed {func_name} after {duration:.3f}s: {e}")
            raise
    
    return wrapper

def require_permission(permission: str):
    """Decorator that requires specific permission in security context"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not ContextManager.has_permission(permission):
                user_id = ContextManager.get_user_id()
                raise PermissionError(f"User {user_id} lacks permission: {permission}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def track_performance(operation_name: str):
    """Decorator that tracks performance for an operation"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            ContextManager.track_performance(operation_name)
            try:
                result = await func(*args, **kwargs)
                duration = ContextManager.finish_performance_tracking(operation_name)
                return result
            except Exception as e:
                ContextManager.finish_performance_tracking(operation_name)
                raise
        return wrapper
    return decorator

async def demonstrate_context_patterns():
    """Demonstrate context variable patterns and best practices"""
    
    print("=== Context Variable Patterns ===")
    
    @with_context_logging
    @track_performance("user_authentication")
    async def authenticate_user(username: str, password: str):
        """Authenticate user and set security context"""
        await asyncio.sleep(0.1)  # Simulate auth check
        
        # Mock authentication result
        if username in ["admin", "user", "guest"]:
            roles = {"admin": ["admin", "user"], 
                    "user": ["user"], 
                    "guest": ["guest"]}.get(username, ["guest"])
            
            permissions = {
                "admin": ["read", "write", "delete", "admin"],
                "user": ["read", "write"],
                "guest": ["read"]
            }.get(username, ["read"])
            
            ContextManager.set_security_context(
                user_roles=roles,
                permissions=permissions,
                username=username
            )
            
            return {"success": True, "user_id": f"uid_{username}"}
        
        return {"success": False}
    
    @with_context_logging
    @require_permission("read")
    @track_performance("data_retrieval") 
    async def get_user_data(user_id: str):
        """Get user data - requires read permission"""
        await asyncio.sleep(0.05)
        return {"user_id": user_id, "data": "user information"}
    
    @with_context_logging
    @require_permission("write")
    @track_performance("data_modification")
    async def update_user_data(user_id: str, data: dict):
        """Update user data - requires write permission"""
        await asyncio.sleep(0.1)
        return {"user_id": user_id, "updated": True}
    
    @with_context_logging
    @require_permission("delete")
    @track_performance("data_deletion")
    async def delete_user_data(user_id: str):
        """Delete user data - requires delete permission"""
        await asyncio.sleep(0.08)
        return {"user_id": user_id, "deleted": True}
    
    @with_context_logging
    @require_permission("admin")
    async def admin_operation():
        """Admin-only operation"""
        await asyncio.sleep(0.05)
        return {"admin_data": "sensitive information"}
    
    async def process_user_request(request_id: str, user_credentials: dict, 
                                 requested_operations: list):
        """Process a user request with full context management"""
        
        # Set up request context
        ContextManager.create_request_context(
            request_id=request_id,
            client_ip="192.168.1.100",
            user_agent="AsyncApp/1.0"
        )
        
        print(f"\n--- Processing Request {request_id} ---")
        
        try:
            # Authenticate user
            auth_result = await authenticate_user(
                user_credentials['username'],
                user_credentials['password']
            )
            
            if not auth_result['success']:
                return {"error": "Authentication failed"}
            
            # Update request context with user ID
            current_ctx = request_context.get().copy()
            current_ctx['user_id'] = auth_result['user_id'] 
            request_context.set(current_ctx)
            
            results = []
            
            # Process requested operations
            for operation in requested_operations:
                try:
                    if operation['type'] == 'get_data':
                        result = await get_user_data(operation['user_id'])
                        results.append({"operation": "get_data", "result": result})
                    
                    elif operation['type'] == 'update_data':
                        result = await update_user_data(
                            operation['user_id'], 
                            operation['data']
                        )
                        results.append({"operation": "update_data", "result": result})
                    
                    elif operation['type'] == 'delete_data':
                        result = await delete_user_data(operation['user_id'])
                        results.append({"operation": "delete_data", "result": result})
                    
                    elif operation['type'] == 'admin_op':
                        result = await admin_operation()
                        results.append({"operation": "admin_op", "result": result})
                    
                except PermissionError as e:
                    results.append({"operation": operation['type'], "error": str(e)})
                
                except Exception as e:
                    results.append({"operation": operation['type'], "error": f"Unexpected error: {e}"})
            
            # Get performance summary
            try:
                perf_ctx = performance_context.get()
                performance_summary = {
                    op_name: {
                        'duration': op_data.get('duration'),
                        'active': op_data.get('active')
                    }
                    for op_name, op_data in perf_ctx.get('operations', {}).items()
                }
            except LookupError:
                performance_summary = {}
            
            return {
                "request_id": request_id,
                "results": results,
                "performance": performance_summary
            }
        
        except Exception as e:
            return {"error": f"Request processing failed: {e}"}
    
    print("1. Testing different user permission levels:")
    
    # Test requests with different permission levels
    test_scenarios = [
        {
            "request_id": "req_admin_001",
            "credentials": {"username": "admin", "password": "secret"},
            "operations": [
                {"type": "get_data", "user_id": "test_user"},
                {"type": "update_data", "user_id": "test_user", "data": {"name": "Updated"}},
                {"type": "admin_op"}
            ]
        },
        {
            "request_id": "req_user_001", 
            "credentials": {"username": "user", "password": "secret"},
            "operations": [
                {"type": "get_data", "user_id": "test_user"},
                {"type": "update_data", "user_id": "test_user", "data": {"name": "Updated"}},
                {"type": "admin_op"},  # This should fail
                {"type": "delete_data", "user_id": "test_user"}  # This should fail
            ]
        },
        {
            "request_id": "req_guest_001",
            "credentials": {"username": "guest", "password": "secret"},
            "operations": [
                {"type": "get_data", "user_id": "test_user"},
                {"type": "update_data", "user_id": "test_user", "data": {"name": "Updated"}},  # This should fail
            ]
        }
    ]
    
    # Process all scenarios concurrently
    tasks = [
        process_user_request(scenario["request_id"], 
                           scenario["credentials"], 
                           scenario["operations"])
        for scenario in test_scenarios
    ]
    
    results = await asyncio.gather(*tasks)
    
    print(f"\n2. Summary of {len(results)} processed requests:")
    for i, result in enumerate(results):
        scenario = test_scenarios[i]
        print(f"   Request {scenario['request_id']} ({scenario['credentials']['username']}):")
        
        if 'error' in result:
            print(f"     Error: {result['error']}")
        else:
            successful_ops = sum(1 for r in result['results'] if 'error' not in r)
            failed_ops = len(result['results']) - successful_ops
            print(f"     Operations: {successful_ops} successful, {failed_ops} failed")
            
            if result.get('performance'):
                total_time = sum(
                    data['duration'] for data in result['performance'].values() 
                    if data['duration'] is not None
                )
                print(f"     Total operation time: {total_time:.3f}s")

asyncio.run(demonstrate_context_patterns())
```

## 13.2 Task-Local Context

Understanding how context propagates between tasks and how to manage task-specific state is crucial for building robust async applications.

### Task Context Propagation

```python
import asyncio
import contextvars
import uuid
import time
from typing import Dict, Any

# Context variables for task management
task_context: contextvars.ContextVar[dict] = contextvars.ContextVar('task_context')
task_hierarchy: contextvars.ContextVar[list] = contextvars.ContextVar('task_hierarchy', default=[])

class TaskContextManager:
    """Manage task-specific context and hierarchy"""
    
    @staticmethod
    def create_task_context(task_name: str, parent_task_id: str = None, **metadata):
        """Create context for a new task"""
        task_id = str(uuid.uuid4())[:8]
        
        context = {
            'task_id': task_id,
            'task_name': task_name,
            'parent_task_id': parent_task_id,
            'start_time': time.time(),
            'metadata': metadata
        }
        
        task_context.set(context)
        
        # Update task hierarchy
        current_hierarchy = task_hierarchy.get().copy()
        current_hierarchy.append(task_id)
        task_hierarchy.set(current_hierarchy)
        
        return task_id
    
    @staticmethod
    def get_current_task_id():
        """Get current task ID"""
        try:
            return task_context.get().get('task_id')
        except LookupError:
            return None
    
    @staticmethod
    def get_task_hierarchy():
        """Get current task hierarchy"""
        try:
            return task_hierarchy.get().copy()
        except LookupError:
            return []
    
    @staticmethod
    def update_task_metadata(key: str, value: Any):
        """Update metadata for current task"""
        try:
            ctx = task_context.get().copy()
            ctx['metadata'][key] = value
            task_context.set(ctx)
        except LookupError:
            pass
    
    @staticmethod
    def get_task_info():
        """Get complete task information"""
        try:
            ctx = task_context.get()
            hierarchy = task_hierarchy.get()
            return {
                'current_task': ctx,
                'hierarchy': hierarchy,
                'depth': len(hierarchy)
            }
        except LookupError:
            return None

async def demonstrate_task_context_propagation():
    """Demonstrate how context propagates between tasks"""
    
    print("=== Task Context Propagation ===")
    
    async def leaf_operation(operation_name: str, duration: float = 0.1):
        """Leaf operation that doesn't spawn new tasks"""
        task_id = TaskContextManager.create_task_context(
            f"leaf_{operation_name}",
            metadata={'operation_type': 'leaf', 'duration': duration}
        )
        
        task_info = TaskContextManager.get_task_info()
        print(f"   Leaf {operation_name} (ID: {task_id}) - Depth: {task_info['depth']}")
        
        await asyncio.sleep(duration)
        
        TaskContextManager.update_task_metadata('completed_at', time.time())
        return f"Result from {operation_name}"
    
    async def parallel_operation(operation_name: str, num_subtasks: int = 3):
        """Operation that spawns parallel subtasks"""
        task_id = TaskContextManager.create_task_context(
            f"parallel_{operation_name}",
            metadata={'operation_type': 'parallel', 'num_subtasks': num_subtasks}
        )
        
        task_info = TaskContextManager.get_task_info()
        print(f"   Parallel {operation_name} (ID: {task_id}) - Depth: {task_info['depth']}")
        
        # Spawn multiple subtasks in parallel
        subtasks = [
            leaf_operation(f"{operation_name}_sub_{i}", 0.05 + i * 0.02)
            for i in range(num_subtasks)
        ]
        
        results = await asyncio.gather(*subtasks)
        
        TaskContextManager.update_task_metadata('subtask_results', len(results))
        return f"Parallel {operation_name} completed with {len(results)} subtasks"
    
    async def sequential_operation(operation_name: str, num_steps: int = 2):
        """Operation that executes steps sequentially"""
        task_id = TaskContextManager.create_task_context(
            f"sequential_{operation_name}",
            metadata={'operation_type': 'sequential', 'num_steps': num_steps}
        )
        
        task_info = TaskContextManager.get_task_info()
        print(f"   Sequential {operation_name} (ID: {task_id}) - Depth: {task_info['depth']}")
        
        results = []
        
        for i in range(num_steps):
            result = await leaf_operation(f"{operation_name}_step_{i}", 0.08)
            results.append(result)
        
        TaskContextManager.update_task_metadata('step_results', len(results))
        return f"Sequential {operation_name} completed {num_steps} steps"
    
    async def complex_operation(operation_name: str):
        """Complex operation with mixed parallel and sequential tasks"""
        task_id = TaskContextManager.create_task_context(
            f"complex_{operation_name}",
            metadata={'operation_type': 'complex'}
        )
        
        task_info = TaskContextManager.get_task_info()
        print(f"   Complex {operation_name} (ID: {task_id}) - Depth: {task_info['depth']}")
        
        # Phase 1: Parallel operations
        parallel_tasks = [
            parallel_operation(f"{operation_name}_parallel_A", 2),
            parallel_operation(f"{operation_name}_parallel_B", 3)
        ]
        
        phase1_results = await asyncio.gather(*parallel_tasks)
        
        # Phase 2: Sequential operation
        phase2_result = await sequential_operation(f"{operation_name}_sequential", 3)
        
        # Phase 3: Final leaf operation
        phase3_result = await leaf_operation(f"{operation_name}_final")
        
        all_results = phase1_results + [phase2_result, phase3_result]
        
        TaskContextManager.update_task_metadata('total_phases', 3)
        TaskContextManager.update_task_metadata('total_results', len(all_results))
        
        return f"Complex {operation_name} completed with {len(all_results)} total results"
    
    async def root_operation():
        """Root operation that starts the task hierarchy"""
        root_task_id = TaskContextManager.create_task_context(
            "root_operation",
            metadata={'operation_type': 'root'}
        )
        
        print(f"Root operation started (ID: {root_task_id})")
        
        # Start multiple complex operations concurrently
        complex_tasks = [
            complex_operation("WorkflowA"),
            complex_operation("WorkflowB")
        ]
        
        results = await asyncio.gather(*complex_tasks)
        
        TaskContextManager.update_task_metadata('workflows_completed', len(results))
        
        return results
    
    print("1. Executing nested task hierarchy:")
    
    start_time = time.time()
    root_results = await root_operation()
    total_duration = time.time() - start_time
    
    print(f"\nRoot operation completed in {total_duration:.3f}s")
    print(f"Results: {root_results}")
    
    print("\n2. Demonstrating context isolation between concurrent tasks:")
    
    async def isolated_task(task_number: int):
        """Task that maintains its own isolated context"""
        task_id = TaskContextManager.create_task_context(
            f"isolated_task_{task_number}",
            metadata={'task_number': task_number, 'isolation_test': True}
        )
        
        # Each task gets its own context
        task_info = TaskContextManager.get_task_info()
        hierarchy = task_info['hierarchy']
        
        print(f"   Task {task_number} (ID: {task_id}) - Hierarchy: {hierarchy}")
        
        # Do some work with context updates
        for step in range(3):
            TaskContextManager.update_task_metadata(f'step_{step}', f'completed at {time.time()}')
            await asyncio.sleep(0.05)
        
        # Each task should have its own isolated context
        final_info = TaskContextManager.get_task_info()
        return {
            'task_id': task_id,
            'task_number': task_number,
            'final_hierarchy': final_info['hierarchy'],
            'metadata': final_info['current_task']['metadata']
        }
    
    # Run multiple isolated tasks concurrently
    isolated_tasks = [isolated_task(i) for i in range(4)]
    isolated_results = await asyncio.gather(*isolated_tasks)
    
    print("\nIsolated task results:")
    for result in isolated_results:
        print(f"   Task {result['task_number']} (ID: {result['task_id']}):")
        print(f"     Hierarchy: {result['final_hierarchy']}")
        print(f"     Metadata keys: {list(result['metadata'].keys())}")

asyncio.run(demonstrate_task_context_propagation())
```

### Context-Aware Task Pools and Workers

```python
import asyncio
import contextvars
import time
import random
from typing import Callable, Any, List
from dataclasses import dataclass
from enum import Enum

# Context variables for worker management
worker_context: contextvars.ContextVar[dict] = contextvars.ContextVar('worker_context')
work_context: contextvars.ContextVar[dict] = contextvars.ContextVar('work_context')

class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    STOPPING = "stopping"

@dataclass
class WorkItem:
    """Represents a unit of work to be processed"""
    work_id: str
    work_type: str
    payload: Any
    priority: int = 5
    context_data: dict = None
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.context_data is None:
            self.context_data = {}

class ContextAwareWorker:
    """Worker that maintains context during work processing"""
    
    def __init__(self, worker_id: str, worker_type: str = "general"):
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.status = WorkerStatus.IDLE
        self.current_work = None
        self.work_count = 0
        self.total_work_time = 0.0
        self.start_time = time.time()
    
    async def process_work(self, work_item: WorkItem) -> Any:
        """Process a work item with proper context management"""
        
        # Set worker context
        worker_ctx = {
            'worker_id': self.worker_id,
            'worker_type': self.worker_type,
            'work_start_time': time.time(),
            'work_item_id': work_item.work_id
        }
        worker_context.set(worker_ctx)
        
        # Set work context from work item
        work_ctx = {
            'work_id': work_item.work_id,
            'work_type': work_item.work_type,
            'priority': work_item.priority,
            'payload': work_item.payload,
            **work_item.context_data
        }
        work_context.set(work_ctx)
        
        self.status = WorkerStatus.BUSY
        self.current_work = work_item
        
        work_start = time.time()
        
        try:
            print(f"   Worker {self.worker_id} starting work {work_item.work_id}")
            
            # Delegate to work type handler
            if work_item.work_type == "computation":
                result = await self._handle_computation(work_item)
            elif work_item.work_type == "io_operation":
                result = await self._handle_io_operation(work_item)
            elif work_item.work_type == "data_processing":
                result = await self._handle_data_processing(work_item)
            else:
                result = await self._handle_generic_work(work_item)
            
            work_duration = time.time() - work_start
            self.work_count += 1
            self.total_work_time += work_duration
            
            print(f"   Worker {self.worker_id} completed work {work_item.work_id} in {work_duration:.3f}s")
            
            return {
                'work_id': work_item.work_id,
                'result': result,
                'worker_id': self.worker_id,
                'duration': work_duration,
                'success': True
            }
        
        except Exception as e:
            work_duration = time.time() - work_start
            print(f"   Worker {self.worker_id} failed work {work_item.work_id}: {e}")
            
            return {
                'work_id': work_item.work_id,
                'error': str(e),
                'worker_id': self.worker_id,
                'duration': work_duration,
                'success': False
            }
        
        finally:
            self.status = WorkerStatus.IDLE
            self.current_work = None
    
    async def _handle_computation(self, work_item: WorkItem) -> Any:
        """Handle computational work"""
        # Access work context
        work_ctx = work_context.get()
        computation_type = work_ctx['payload'].get('computation_type', 'default')
        
        if computation_type == 'fibonacci':
            n = work_ctx['payload'].get('n', 10)
            await asyncio.sleep(0.01)  # Simulate computation time
            
            # Simple fibonacci calculation
            if n <= 1:
                return n
            else:
                a, b = 0, 1
                for _ in range(2, n + 1):
                    a, b = b, a + b
                return b
        
        elif computation_type == 'prime_check':
            num = work_ctx['payload'].get('number', 17)
            await asyncio.sleep(0.005)  # Simulate computation time
            
            if num < 2:
                return False
            for i in range(2, int(num ** 0.5) + 1):
                if num % i == 0:
                    return False
            return True
        
        else:
            await asyncio.sleep(random.uniform(0.01, 0.1))
            return f"Computed result for {computation_type}"
    
    async def _handle_io_operation(self, work_item: WorkItem) -> Any:
        """Handle I/O operations"""
        work_ctx = work_context.get()
        io_type = work_ctx['payload'].get('io_type', 'read')
        
        if io_type == 'read':
            # Simulate file read
            await asyncio.sleep(random.uniform(0.05, 0.15))
            return f"Read data from {work_ctx['payload'].get('filename', 'file.txt')}"
        
        elif io_type == 'write':
            # Simulate file write
            await asyncio.sleep(random.uniform(0.1, 0.2))
            return f"Wrote data to {work_ctx['payload'].get('filename', 'output.txt')}"
        
        elif io_type == 'network':
            # Simulate network request
            await asyncio.sleep(random.uniform(0.1, 0.3))
            return f"Network response from {work_ctx['payload'].get('url', 'api.example.com')}"
        
        else:
            await asyncio.sleep(random.uniform(0.05, 0.2))
            return f"I/O operation {io_type} completed"
    
    async def _handle_data_processing(self, work_item: WorkItem) -> Any:
        """Handle data processing"""
        work_ctx = work_context.get()
        data = work_ctx['payload'].get('data', [])
        operation = work_ctx['payload'].get('operation', 'transform')
        
        # Simulate processing time based on data size
        processing_time = len(data) * 0.001 + random.uniform(0.01, 0.05)
        await asyncio.sleep(processing_time)
        
        if operation == 'transform':
            return [f"transformed_{item}" for item in data]
        elif operation == 'filter':
            return [item for item in data if len(str(item)) > 2]
        elif operation == 'aggregate':
            return {'count': len(data), 'items': data[:5]}  # Sample
        else:
            return f"Processed {len(data)} items with {operation}"
    
    async def _handle_generic_work(self, work_item: WorkItem) -> Any:
        """Handle generic work"""
        # Simulate work time
        await asyncio.sleep(random.uniform(0.05, 0.15))
        return f"Generic work result for {work_item.work_type}"
    
    def get_stats(self) -> dict:
        """Get worker statistics"""
        uptime = time.time() - self.start_time
        avg_work_time = self.total_work_time / self.work_count if self.work_count > 0 else 0
        
        return {
            'worker_id': self.worker_id,
            'worker_type': self.worker_type,
            'status': self.status.value,
            'work_count': self.work_count,
            'total_work_time': self.total_work_time,
            'average_work_time': avg_work_time,
            'uptime': uptime,
            'current_work': self.current_work.work_id if self.current_work else None
        }

class ContextAwareTaskPool:
    """Task pool that maintains context across workers"""
    
    def __init__(self, pool_size: int = 3):
        self.pool_size = pool_size
        self.workers: List[ContextAwareWorker] = []
        self.work_queue = asyncio.Queue()
        self.results = {}
        self.running = False
        self.worker_tasks = []
    
    async def start(self):
        """Start the worker pool"""
        self.running = True
        
        # Create workers
        for i in range(self.pool_size):
            worker = ContextAwareWorker(
                worker_id=f"worker_{i}",
                worker_type="general"
            )
            self.workers.append(worker)
        
        # Start worker tasks
        for worker in self.workers:
            task = asyncio.create_task(self._worker_loop(worker))
            self.worker_tasks.append(task)
        
        print(f"Started task pool with {len(self.workers)} workers")
    
    async def stop(self):
        """Stop the worker pool"""
        self.running = False
        
        # Signal workers to stop by putting None items
        for _ in self.workers:
            await self.work_queue.put(None)
        
        # Wait for all workers to finish
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        print("Task pool stopped")
    
    async def submit_work(self, work_item: WorkItem) -> str:
        """Submit work to the pool"""
        await self.work_queue.put(work_item)
        return work_item.work_id
    
    async def _worker_loop(self, worker: ContextAwareWorker):
        """Main worker loop"""
        while self.running:
            try:
                # Get work from queue
                work_item = await self.work_queue.get()
                
                # Check for stop signal
                if work_item is None:
                    break
                
                # Process work with context
                result = await worker.process_work(work_item)
                
                # Store result
                self.results[work_item.work_id] = result
                
                # Mark task as done
                self.work_queue.task_done()
            
            except Exception as e:
                print(f"Worker {worker.worker_id} error: {e}")
    
    def get_pool_stats(self) -> dict:
        """Get pool statistics"""
        worker_stats = [worker.get_stats() for worker in self.workers]
        
        total_work = sum(stats['work_count'] for stats in worker_stats)
        total_work_time = sum(stats['total_work_time'] for stats in worker_stats)
        busy_workers = sum(1 for stats in worker_stats if stats['status'] == 'busy')
        
        return {
            'pool_size': len(self.workers),
            'busy_workers': busy_workers,
            'idle_workers': len(self.workers) - busy_workers,
            'total_work_completed': total_work,
            'total_work_time': total_work_time,
            'queue_size': self.work_queue.qsize(),
            'results_count': len(self.results),
            'workers': worker_stats
        }

async def demonstrate_context_aware_task_pool():
    """Demonstrate context-aware task pool operations"""
    
    print("=== Context-Aware Task Pool ===")
    
    # Create and start task pool
    pool = ContextAwareTaskPool(pool_size=4)
    await pool.start()
    
    print("\n1. Submitting various types of work:")
    
    # Create different types of work items
    work_items = [
        # Computational work
        WorkItem(
            work_id="comp_001",
            work_type="computation",
            payload={'computation_type': 'fibonacci', 'n': 15},
            context_data={'department': 'math', 'priority_level': 'high'}
        ),
        WorkItem(
            work_id="comp_002", 
            work_type="computation",
            payload={'computation_type': 'prime_check', 'number': 97},
            context_data={'department': 'math', 'priority_level': 'medium'}
        ),
        
        # I/O work
        WorkItem(
            work_id="io_001",
            work_type="io_operation", 
            payload={'io_type': 'read', 'filename': 'data.csv'},
            context_data={'department': 'data', 'priority_level': 'high'}
        ),
        WorkItem(
            work_id="io_002",
            work_type="io_operation",
            payload={'io_type': 'network', 'url': 'https://api.example.com/data'},
            context_data={'department': 'integration', 'priority_level': 'low'}
        ),
        
        # Data processing work
        WorkItem(
            work_id="data_001",
            work_type="data_processing",
            payload={
                'data': list(range(50)),
                'operation': 'transform'
            },
            context_data={'department': 'analytics', 'batch_id': 'batch_001'}
        ),
        WorkItem(
            work_id="data_002",
            work_type="data_processing", 
            payload={
                'data': ['apple', 'banana', 'cherry', 'date', 'elderberry'],
                'operation': 'filter'
            },
            context_data={'department': 'analytics', 'batch_id': 'batch_002'}
        ),
    ]
    
    # Submit all work
    submitted_work_ids = []
    for work_item in work_items:
        work_id = await pool.submit_work(work_item)
        submitted_work_ids.append(work_id)
        print(f"   Submitted {work_item.work_type} work: {work_id}")
    
    # Monitor progress
    print(f"\n2. Monitoring work progress:")
    
    completed_work = set()
    while len(completed_work) < len(submitted_work_ids):
        await asyncio.sleep(0.1)
        
        # Check for completed work
        for work_id in submitted_work_ids:
            if work_id in pool.results and work_id not in completed_work:
                result = pool.results[work_id]
                status = "✓" if result['success'] else "✗"
                print(f"   {status} {work_id} completed by {result['worker_id']} "
                      f"in {result['duration']:.3f}s")
                completed_work.add(work_id)
        
        # Show pool stats
        if len(completed_work) % 2 == 0 and len(completed_work) < len(submitted_work_ids):
            stats = pool.get_pool_stats()
            print(f"   Pool status: {stats['busy_workers']} busy, "
                  f"{stats['idle_workers']} idle, queue: {stats['queue_size']}")
    
    print(f"\n3. Final results:")
    for work_id in submitted_work_ids:
        result = pool.results[work_id]
        if result['success']:
            print(f"   {work_id}: {result['result']}")
        else:
            print(f"   {work_id}: Error - {result['error']}")
    
    # Show final pool statistics
    final_stats = pool.get_pool_stats()
    print(f"\n4. Final pool statistics:")
    print(f"   Total work completed: {final_stats['total_work_completed']}")
    print(f"   Total work time: {final_stats['total_work_time']:.3f}s")
    print(f"   Average work time per worker:")
    
    for worker_stats in final_stats['workers']:
        avg_time = worker_stats['average_work_time']
        print(f"     {worker_stats['worker_id']}: {worker_stats['work_count']} items, "
              f"avg {avg_time:.3f}s each")
    
    # Stop the pool
    await pool.stop()

asyncio.run(demonstrate_context_aware_task_pool())
```

This completes Chapter 13 on Context Variables and Task Context. The chapter demonstrates:

1. **Understanding Context Variables** - How to use contextvars for maintaining request-specific state
2. **Task-Local Context** - How context propagates between tasks and managing task hierarchies  
3. **Context-Aware Patterns** - Practical patterns like decorators, permissions, and task pools

The examples show real-world usage patterns that are essential for building production asyncio libraries and applications where you need to maintain context across async operations.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content":"Write Chapter 1: Understanding Asynchronous Programming","status":"completed","id":"ch1"},{"content":"Write Chapter 2: The Event Loop - Heart of Asyncio","status":"completed","id":"ch2"},{"content":"Write Chapter 3: Coroutines - The Building Blocks","status":"completed","id":"ch3"},{"content":"Write Chapter 4: Tasks and Futures","status":"completed","id":"ch4"},{"content":"Write Chapter 5: Synchronization Primitives","status":"completed","id":"ch5"},{"content":"Write Chapter 6: Queues and Producer-Consumer Patterns","status":"completed","id":"ch6"},{"content":"Write Chapter 7: Streams - High-Level Network I/O","status":"completed","id":"ch7"},{"content":"Write Chapter 8: Transports and Protocols - Low-Level Network I/O","status":"completed","id":"ch8"},{"content":"Write Chapter 9: Subprocesses","status":"completed","id":"ch9"},{"content":"Write Chapter 10: Exception Handling and Debugging","status":"completed","id":"ch10"},{"content":"Write Chapter 11: Timeouts and Cancellation","status":"completed","id":"ch11"},{"content":"Write Chapter 12: Mixing Asyncio with Threads and Processes","status":"completed","id":"ch12"},{"content":"Write Chapter 13: Context Variables and Task Context","status":"completed","id":"ch13"},{"content":"Continue with remaining chapters 14-36","status":"in_progress","id":"remaining-chapters"}]