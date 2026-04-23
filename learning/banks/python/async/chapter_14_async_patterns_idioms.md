# Chapter 14: Async Patterns and Idioms

## 14.1 Common Async Design Patterns

Understanding common async design patterns helps you structure your code effectively and avoid common pitfalls. This chapter covers essential patterns for building robust async applications.

### The Async Context Manager Pattern

```python
import asyncio
import time
import aiofiles
import tempfile
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

class AsyncResourceManager:
    """Example of async context manager for resource management"""
    
    def __init__(self, resource_name: str, setup_time: float = 0.1, cleanup_time: float = 0.05):
        self.resource_name = resource_name
        self.setup_time = setup_time
        self.cleanup_time = cleanup_time
        self.resource = None
        self.start_time = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        print(f"   Setting up resource: {self.resource_name}")
        self.start_time = time.time()
        
        # Simulate async setup
        await asyncio.sleep(self.setup_time)
        
        # Create the resource
        self.resource = {
            'name': self.resource_name,
            'id': f"resource_{int(time.time() * 1000)}",
            'created_at': self.start_time
        }
        
        print(f"   Resource ready: {self.resource['id']}")
        return self.resource
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.resource:
            print(f"   Cleaning up resource: {self.resource['id']}")
            
            # Simulate async cleanup
            await asyncio.sleep(self.cleanup_time)
            
            duration = time.time() - self.start_time
            print(f"   Resource {self.resource['id']} was active for {duration:.3f}s")
            
            if exc_type:
                print(f"   Resource cleanup after exception: {exc_type.__name__}")
        
        return False  # Don't suppress exceptions

@asynccontextmanager
async def async_database_connection(connection_string: str) -> AsyncGenerator[dict, None]:
    """Async context manager using decorator"""
    print(f"   Connecting to database: {connection_string}")
    
    # Simulate connection setup
    await asyncio.sleep(0.1)
    
    connection = {
        'connection_string': connection_string,
        'connection_id': f"conn_{int(time.time() * 1000)}",
        'connected_at': time.time()
    }
    
    try:
        print(f"   Database connected: {connection['connection_id']}")
        yield connection
    
    finally:
        # Cleanup always happens
        print(f"   Closing database connection: {connection['connection_id']}")
        await asyncio.sleep(0.05)  # Simulate cleanup
        print(f"   Database connection closed")

async def demonstrate_async_context_managers():
    """Demonstrate async context manager patterns"""
    
    print("=== Async Context Manager Pattern ===")
    
    print("1. Class-based async context manager:")
    
    async def use_resource_manager():
        """Example using class-based context manager"""
        async with AsyncResourceManager("DatabaseConnection") as db:
            print(f"   Using resource: {db['name']} (ID: {db['id']})")
            await asyncio.sleep(0.2)  # Simulate work
            return f"Work completed with {db['id']}"
    
    result = await use_resource_manager()
    print(f"   Result: {result}")
    
    print("\n2. Decorator-based async context manager:")
    
    async def use_database_connection():
        """Example using decorator-based context manager"""
        async with async_database_connection("postgresql://localhost/mydb") as conn:
            print(f"   Executing query on: {conn['connection_id']}")
            await asyncio.sleep(0.15)  # Simulate query
            return f"Query result from {conn['connection_id']}"
    
    result = await use_database_connection()
    print(f"   Result: {result}")
    
    print("\n3. Exception handling in async context managers:")
    
    async def test_exception_handling():
        """Test exception handling in context managers"""
        try:
            async with AsyncResourceManager("FailingResource") as resource:
                print(f"   Working with: {resource['id']}")
                await asyncio.sleep(0.1)
                
                # Simulate an error
                raise ValueError("Simulated processing error")
        
        except ValueError as e:
            print(f"   Caught exception: {e}")
            return "Exception handled"
    
    result = await test_exception_handling()
    print(f"   Result: {result}")
    
    print("\n4. Nested async context managers:")
    
    async def nested_context_usage():
        """Example of nested async context managers"""
        async with AsyncResourceManager("OuterResource", 0.05, 0.03) as outer:
            async with async_database_connection("sqlite:///test.db") as db:
                async with AsyncResourceManager("InnerResource", 0.03, 0.02) as inner:
                    print(f"   Using nested resources:")
                    print(f"     Outer: {outer['id']}")
                    print(f"     Database: {db['connection_id']}")
                    print(f"     Inner: {inner['id']}")
                    
                    await asyncio.sleep(0.1)
                    return "Nested operation completed"
    
    result = await nested_context_usage()
    print(f"   Result: {result}")

asyncio.run(demonstrate_async_context_managers())
```

### The Async Factory Pattern

```python
import asyncio
import abc
from typing import Dict, Any, Type, Optional
from dataclasses import dataclass
from enum import Enum

class ConnectionType(Enum):
    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    HTTP_CLIENT = "http_client"

@dataclass
class ConnectionConfig:
    """Configuration for connections"""
    connection_type: ConnectionType
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    extra_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}

class AsyncConnection(abc.ABC):
    """Abstract base class for async connections"""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.is_connected = False
        self.connection_id = None
    
    @abc.abstractmethod
    async def connect(self) -> bool:
        """Establish connection"""
        pass
    
    @abc.abstractmethod
    async def disconnect(self) -> bool:
        """Close connection"""
        pass
    
    @abc.abstractmethod
    async def execute(self, operation: str, *args, **kwargs) -> Any:
        """Execute operation"""
        pass
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

class DatabaseConnection(AsyncConnection):
    """Simulated database connection"""
    
    async def connect(self) -> bool:
        print(f"   Connecting to database: {self.config.host}:{self.config.port}")
        await asyncio.sleep(0.1)  # Simulate connection time
        
        self.connection_id = f"db_{self.config.host}_{int(time.time() * 1000)}"
        self.is_connected = True
        
        print(f"   Database connected: {self.connection_id}")
        return True
    
    async def disconnect(self) -> bool:
        if self.is_connected:
            print(f"   Disconnecting database: {self.connection_id}")
            await asyncio.sleep(0.05)  # Simulate disconnection
            self.is_connected = False
            print(f"   Database disconnected: {self.connection_id}")
        return True
    
    async def execute(self, query: str, params: dict = None) -> dict:
        if not self.is_connected:
            raise RuntimeError("Database not connected")
        
        print(f"   Executing query: {query[:50]}...")
        await asyncio.sleep(0.05)  # Simulate query time
        
        return {
            'query': query,
            'params': params,
            'result': f"Query result from {self.connection_id}",
            'rows_affected': 1
        }

class CacheConnection(AsyncConnection):
    """Simulated cache connection"""
    
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.cache_data = {}
    
    async def connect(self) -> bool:
        print(f"   Connecting to cache: {self.config.host}:{self.config.port}")
        await asyncio.sleep(0.05)  # Simulate connection time
        
        self.connection_id = f"cache_{self.config.host}_{int(time.time() * 1000)}"
        self.is_connected = True
        
        print(f"   Cache connected: {self.connection_id}")
        return True
    
    async def disconnect(self) -> bool:
        if self.is_connected:
            print(f"   Disconnecting cache: {self.connection_id}")
            await asyncio.sleep(0.02)  # Simulate disconnection
            self.is_connected = False
            print(f"   Cache disconnected: {self.connection_id}")
        return True
    
    async def execute(self, operation: str, key: str = None, value: Any = None) -> Any:
        if not self.is_connected:
            raise RuntimeError("Cache not connected")
        
        await asyncio.sleep(0.01)  # Simulate operation time
        
        if operation == "get":
            result = self.cache_data.get(key)
            print(f"   Cache GET {key}: {'HIT' if result else 'MISS'}")
            return result
        
        elif operation == "set":
            self.cache_data[key] = value
            print(f"   Cache SET {key}: {value}")
            return True
        
        elif operation == "delete":
            result = self.cache_data.pop(key, None)
            print(f"   Cache DELETE {key}: {'FOUND' if result else 'NOT_FOUND'}")
            return result is not None
        
        else:
            raise ValueError(f"Unknown cache operation: {operation}")

class HTTPClientConnection(AsyncConnection):
    """Simulated HTTP client connection"""
    
    async def connect(self) -> bool:
        print(f"   Initializing HTTP client for: {self.config.host}")
        await asyncio.sleep(0.03)  # Simulate setup time
        
        self.connection_id = f"http_{self.config.host}_{int(time.time() * 1000)}"
        self.is_connected = True
        
        print(f"   HTTP client ready: {self.connection_id}")
        return True
    
    async def disconnect(self) -> bool:
        if self.is_connected:
            print(f"   Closing HTTP client: {self.connection_id}")
            await asyncio.sleep(0.01)  # Simulate cleanup
            self.is_connected = False
            print(f"   HTTP client closed: {self.connection_id}")
        return True
    
    async def execute(self, method: str, path: str, data: dict = None) -> dict:
        if not self.is_connected:
            raise RuntimeError("HTTP client not connected")
        
        url = f"http://{self.config.host}:{self.config.port}{path}"
        print(f"   HTTP {method} {url}")
        
        # Simulate network request time
        await asyncio.sleep(0.1)
        
        return {
            'method': method,
            'url': url,
            'status_code': 200,
            'response_data': f"Response from {self.config.host}",
            'connection_id': self.connection_id
        }

class AsyncConnectionFactory:
    """Factory for creating async connections"""
    
    _connection_types: Dict[ConnectionType, Type[AsyncConnection]] = {
        ConnectionType.DATABASE: DatabaseConnection,
        ConnectionType.CACHE: CacheConnection,
        ConnectionType.HTTP_CLIENT: HTTPClientConnection,
    }
    
    @classmethod
    def register_connection_type(cls, connection_type: ConnectionType, 
                                connection_class: Type[AsyncConnection]):
        """Register a new connection type"""
        cls._connection_types[connection_type] = connection_class
    
    @classmethod
    async def create_connection(cls, config: ConnectionConfig) -> AsyncConnection:
        """Create and return a connection based on configuration"""
        
        if config.connection_type not in cls._connection_types:
            raise ValueError(f"Unknown connection type: {config.connection_type}")
        
        connection_class = cls._connection_types[config.connection_type]
        connection = connection_class(config)
        
        return connection
    
    @classmethod
    async def create_and_connect(cls, config: ConnectionConfig) -> AsyncConnection:
        """Create connection and establish connection immediately"""
        connection = await cls.create_connection(config)
        await connection.connect()
        return connection

class ConnectionPool:
    """Simple connection pool using the factory pattern"""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections: Dict[str, AsyncConnection] = {}
        self.connection_usage: Dict[str, int] = {}
    
    def _get_pool_key(self, config: ConnectionConfig) -> str:
        """Generate a unique key for connection pooling"""
        return f"{config.connection_type.value}_{config.host}_{config.port}_{config.database or ''}"
    
    async def get_connection(self, config: ConnectionConfig) -> AsyncConnection:
        """Get connection from pool or create new one"""
        pool_key = self._get_pool_key(config)
        
        if pool_key in self.connections:
            connection = self.connections[pool_key]
            if connection.is_connected:
                self.connection_usage[pool_key] += 1
                print(f"   Reusing pooled connection: {connection.connection_id}")
                return connection
        
        # Create new connection
        if len(self.connections) >= self.max_connections:
            # Simple eviction: remove least used connection
            least_used_key = min(self.connection_usage.keys(), 
                               key=lambda k: self.connection_usage[k])
            await self.connections[least_used_key].disconnect()
            del self.connections[least_used_key]
            del self.connection_usage[least_used_key]
        
        connection = await AsyncConnectionFactory.create_and_connect(config)
        self.connections[pool_key] = connection
        self.connection_usage[pool_key] = 1
        
        print(f"   Created new pooled connection: {connection.connection_id}")
        return connection
    
    async def close_all(self):
        """Close all connections in the pool"""
        print(f"   Closing {len(self.connections)} pooled connections")
        
        close_tasks = [
            conn.disconnect() 
            for conn in self.connections.values() 
            if conn.is_connected
        ]
        
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        self.connections.clear()
        self.connection_usage.clear()

async def demonstrate_async_factory_pattern():
    """Demonstrate async factory pattern usage"""
    
    print("=== Async Factory Pattern ===")
    
    print("1. Creating different connection types:")
    
    # Configuration for different connection types
    configs = [
        ConnectionConfig(
            connection_type=ConnectionType.DATABASE,
            host="db.example.com",
            port=5432,
            username="user",
            database="myapp"
        ),
        ConnectionConfig(
            connection_type=ConnectionType.CACHE,
            host="cache.example.com",
            port=6379
        ),
        ConnectionConfig(
            connection_type=ConnectionType.HTTP_CLIENT,
            host="api.example.com",
            port=443
        )
    ]
    
    # Create connections using factory
    connections = []
    for config in configs:
        conn = await AsyncConnectionFactory.create_connection(config)
        connections.append(conn)
        print(f"   Created {config.connection_type.value} connection")
    
    print("\n2. Using connections with context managers:")
    
    # Use database connection
    async with connections[0] as db:
        result = await db.execute("SELECT * FROM users WHERE active = ?", {"active": True})
        print(f"   Database result: {result['result']}")
    
    # Use cache connection
    async with connections[1] as cache:
        await cache.execute("set", "user:123", {"name": "Alice", "email": "alice@example.com"})
        cached_user = await cache.execute("get", "user:123")
        print(f"   Cache result: {cached_user}")
    
    # Use HTTP client
    async with connections[2] as http:
        response = await http.execute("GET", "/api/users/123")
        print(f"   HTTP result: {response['response_data']}")
    
    print("\n3. Using connection pool:")
    
    pool = ConnectionPool(max_connections=5)
    
    async def worker_with_pool(worker_id: int):
        """Worker that uses pooled connections"""
        print(f"   Worker {worker_id} starting")
        
        # Use database connection from pool
        db_config = ConnectionConfig(
            connection_type=ConnectionType.DATABASE,
            host="pooled-db.example.com", 
            port=5432,
            database="pooled_app"
        )
        
        db_conn = await pool.get_connection(db_config)
        result = await db_conn.execute(f"SELECT * FROM worker_data WHERE worker_id = {worker_id}")
        print(f"   Worker {worker_id} DB result: {result['rows_affected']} rows")
        
        # Use cache connection from pool
        cache_config = ConnectionConfig(
            connection_type=ConnectionType.CACHE,
            host="pooled-cache.example.com",
            port=6379
        )
        
        cache_conn = await pool.get_connection(cache_config)
        await cache_conn.execute("set", f"worker:{worker_id}", f"data_for_worker_{worker_id}")
        cached_data = await cache_conn.execute("get", f"worker:{worker_id}")
        print(f"   Worker {worker_id} Cache result: {cached_data}")
        
        print(f"   Worker {worker_id} completed")
    
    # Run multiple workers concurrently
    worker_tasks = [worker_with_pool(i) for i in range(6)]
    await asyncio.gather(*worker_tasks)
    
    # Clean up pool
    await pool.close_all()
    
    print("\n4. Factory pattern with custom connection types:")
    
    class MessageQueueConnection(AsyncConnection):
        """Custom message queue connection"""
        
        async def connect(self) -> bool:
            print(f"   Connecting to message queue: {self.config.host}:{self.config.port}")
            await asyncio.sleep(0.08)
            self.connection_id = f"mq_{self.config.host}_{int(time.time() * 1000)}"
            self.is_connected = True
            print(f"   Message queue connected: {self.connection_id}")
            return True
        
        async def disconnect(self) -> bool:
            if self.is_connected:
                print(f"   Disconnecting message queue: {self.connection_id}")
                await asyncio.sleep(0.03)
                self.is_connected = False
                print(f"   Message queue disconnected: {self.connection_id}")
            return True
        
        async def execute(self, operation: str, queue: str = None, message: Any = None) -> Any:
            if not self.is_connected:
                raise RuntimeError("Message queue not connected")
            
            await asyncio.sleep(0.02)
            
            if operation == "publish":
                print(f"   Published message to {queue}: {message}")
                return True
            elif operation == "consume":
                print(f"   Consumed message from {queue}")
                return f"Message from {queue} via {self.connection_id}"
            else:
                raise ValueError(f"Unknown MQ operation: {operation}")
    
    # Register custom connection type
    AsyncConnectionFactory.register_connection_type(
        ConnectionType.MESSAGE_QUEUE, 
        MessageQueueConnection
    )
    
    # Use custom connection type
    mq_config = ConnectionConfig(
        connection_type=ConnectionType.MESSAGE_QUEUE,
        host="mq.example.com",
        port=5672
    )
    
    async with await AsyncConnectionFactory.create_and_connect(mq_config) as mq:
        await mq.execute("publish", "user_events", {"user_id": 123, "action": "login"})
        message = await mq.execute("consume", "user_events")
        print(f"   Message queue result: {message}")

asyncio.run(demonstrate_async_factory_pattern())
```

### The Async Observer Pattern

```python
import asyncio
import time
from typing import List, Callable, Any, Dict, Set
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

class EventType(Enum):
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    DATA_UPDATED = "data_updated"
    SYSTEM_ERROR = "system_error"
    PERFORMANCE_ALERT = "performance_alert"

@dataclass
class Event:
    """Represents an event in the system"""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: f"evt_{int(time.time() * 1000000)}")
    source: str = "system"

class AsyncObserver(ABC):
    """Abstract base class for async observers"""
    
    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """Handle an event asynchronously"""
        pass
    
    @property
    @abstractmethod
    def observer_name(self) -> str:
        """Name of this observer"""
        pass
    
    def interested_in(self, event_type: EventType) -> bool:
        """Override to filter events this observer cares about"""
        return True

class AsyncEventSubject:
    """Subject that notifies async observers of events"""
    
    def __init__(self):
        self.observers: Dict[str, AsyncObserver] = {}
        self.event_history: List[Event] = []
        self.max_history = 1000
    
    def register_observer(self, observer: AsyncObserver) -> None:
        """Register an observer"""
        self.observers[observer.observer_name] = observer
        print(f"   Registered observer: {observer.observer_name}")
    
    def unregister_observer(self, observer_name: str) -> None:
        """Unregister an observer"""
        if observer_name in self.observers:
            del self.observers[observer_name]
            print(f"   Unregistered observer: {observer_name}")
    
    async def notify_observers(self, event: Event) -> Dict[str, Any]:
        """Notify all interested observers of an event"""
        
        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history = self.event_history[-self.max_history:]
        
        print(f"   Notifying observers of event: {event.event_type.value} ({event.event_id})")
        
        # Find interested observers
        interested_observers = [
            observer for observer in self.observers.values()
            if observer.interested_in(event.event_type)
        ]
        
        if not interested_observers:
            print(f"   No observers interested in {event.event_type.value}")
            return {"notified": 0, "results": []}
        
        # Notify observers concurrently
        notification_tasks = [
            self._notify_single_observer(observer, event)
            for observer in interested_observers
        ]
        
        results = await asyncio.gather(*notification_tasks, return_exceptions=True)
        
        # Analyze results
        successful_notifications = sum(1 for r in results if not isinstance(r, Exception))
        failed_notifications = len(results) - successful_notifications
        
        print(f"   Notification complete: {successful_notifications} successful, {failed_notifications} failed")
        
        return {
            "notified": len(interested_observers),
            "successful": successful_notifications,
            "failed": failed_notifications,
            "results": results
        }
    
    async def _notify_single_observer(self, observer: AsyncObserver, event: Event) -> str:
        """Notify a single observer with error handling"""
        try:
            await observer.handle_event(event)
            return f"Success: {observer.observer_name}"
        except Exception as e:
            print(f"   Observer {observer.observer_name} failed: {e}")
            return f"Failed: {observer.observer_name} - {e}"
    
    def get_event_history(self, event_type: EventType = None, limit: int = 10) -> List[Event]:
        """Get recent event history"""
        events = self.event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:] if events else []

# Concrete observer implementations
class LoggingObserver(AsyncObserver):
    """Observer that logs events"""
    
    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level
        self.events_logged = 0
    
    async def handle_event(self, event: Event) -> None:
        await asyncio.sleep(0.01)  # Simulate logging I/O
        
        self.events_logged += 1
        
        timestamp = time.strftime('%H:%M:%S', time.localtime(event.timestamp))
        print(f"   [LOG {self.log_level}] {timestamp} - {event.event_type.value}: "
              f"{event.data} (Source: {event.source})")
    
    @property
    def observer_name(self) -> str:
        return f"LoggingObserver_{self.log_level}"
    
    def interested_in(self, event_type: EventType) -> bool:
        # Log all events
        return True

class MetricsObserver(AsyncObserver):
    """Observer that tracks metrics"""
    
    def __init__(self):
        self.event_counts: Dict[EventType, int] = {}
        self.total_events = 0
    
    async def handle_event(self, event: Event) -> None:
        await asyncio.sleep(0.005)  # Simulate metrics collection
        
        self.total_events += 1
        self.event_counts[event.event_type] = self.event_counts.get(event.event_type, 0) + 1
        
        print(f"   [METRICS] Event count updated: {event.event_type.value} -> "
              f"{self.event_counts[event.event_type]}")
    
    @property
    def observer_name(self) -> str:
        return "MetricsObserver"
    
    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_events": self.total_events,
            "event_counts": {et.value: count for et, count in self.event_counts.items()}
        }

class AlertObserver(AsyncObserver):
    """Observer that handles alerts"""
    
    def __init__(self, alert_threshold: int = 3):
        self.alert_threshold = alert_threshold
        self.error_count = 0
        self.alerts_sent = 0
    
    async def handle_event(self, event: Event) -> None:
        if event.event_type == EventType.SYSTEM_ERROR:
            self.error_count += 1
            
            if self.error_count >= self.alert_threshold:
                await self._send_alert(event)
                self.error_count = 0  # Reset counter after alert
    
    async def _send_alert(self, event: Event):
        """Simulate sending an alert"""
        await asyncio.sleep(0.1)  # Simulate alert sending time
        
        self.alerts_sent += 1
        print(f"   [ALERT] Critical alert sent! Error threshold reached. "
              f"Latest error: {event.data.get('error_message', 'Unknown error')}")
    
    @property
    def observer_name(self) -> str:
        return "AlertObserver"
    
    def interested_in(self, event_type: EventType) -> bool:
        # Only interested in system errors
        return event_type == EventType.SYSTEM_ERROR

class NotificationObserver(AsyncObserver):
    """Observer that sends user notifications"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.notifications_sent = 0
    
    async def handle_event(self, event: Event) -> None:
        # Check if this event is relevant to our user
        if self._is_relevant_to_user(event):
            await self._send_notification(event)
    
    def _is_relevant_to_user(self, event: Event) -> bool:
        """Check if event is relevant to this user"""
        if event.event_type in [EventType.USER_LOGIN, EventType.USER_LOGOUT]:
            return event.data.get('user_id') == self.user_id
        
        elif event.event_type == EventType.DATA_UPDATED:
            # Example: notify if user owns the updated data
            return event.data.get('owner_id') == self.user_id
        
        return False
    
    async def _send_notification(self, event: Event):
        """Send notification to user"""
        await asyncio.sleep(0.08)  # Simulate notification sending
        
        self.notifications_sent += 1
        
        message = self._generate_message(event)
        print(f"   [NOTIFICATION] To user {self.user_id}: {message}")
    
    def _generate_message(self, event: Event) -> str:
        """Generate user-friendly message"""
        if event.event_type == EventType.USER_LOGIN:
            return f"You logged in successfully from {event.data.get('ip_address', 'unknown location')}"
        elif event.event_type == EventType.DATA_UPDATED:
            return f"Your {event.data.get('data_type', 'data')} has been updated"
        else:
            return f"Event: {event.event_type.value}"
    
    @property
    def observer_name(self) -> str:
        return f"NotificationObserver_{self.user_id}"
    
    def interested_in(self, event_type: EventType) -> bool:
        # Interested in user-related events
        return event_type in [EventType.USER_LOGIN, EventType.USER_LOGOUT, EventType.DATA_UPDATED]

class EventFilterObserver(AsyncObserver):
    """Observer that filters and forwards events based on criteria"""
    
    def __init__(self, filter_criteria: Dict[str, Any], target_subject: AsyncEventSubject):
        self.filter_criteria = filter_criteria
        self.target_subject = target_subject
        self.filtered_events = 0
        self.forwarded_events = 0
    
    async def handle_event(self, event: Event) -> None:
        if self._matches_criteria(event):
            # Forward filtered event to target subject
            filtered_event = Event(
                event_type=event.event_type,
                data={**event.data, "filtered": True, "original_source": event.source},
                timestamp=event.timestamp,
                source=f"filtered_from_{event.source}"
            )
            
            await self.target_subject.notify_observers(filtered_event)
            self.forwarded_events += 1
            
            print(f"   [FILTER] Forwarded event {event.event_id} to target subject")
        else:
            self.filtered_events += 1
    
    def _matches_criteria(self, event: Event) -> bool:
        """Check if event matches filter criteria"""
        for key, expected_value in self.filter_criteria.items():
            if key == "event_type":
                if event.event_type != expected_value:
                    return False
            elif key in event.data:
                if event.data[key] != expected_value:
                    return False
        return True
    
    @property
    def observer_name(self) -> str:
        return f"EventFilterObserver_{id(self)}"

async def demonstrate_async_observer_pattern():
    """Demonstrate async observer pattern"""
    
    print("=== Async Observer Pattern ===")
    
    # Create main event subject
    main_subject = AsyncEventSubject()
    
    # Create observers
    logging_observer = LoggingObserver("INFO")
    metrics_observer = MetricsObserver()
    alert_observer = AlertObserver(alert_threshold=2)
    user1_observer = NotificationObserver("user_123")
    user2_observer = NotificationObserver("user_456")
    
    # Register observers
    main_subject.register_observer(logging_observer)
    main_subject.register_observer(metrics_observer)
    main_subject.register_observer(alert_observer)
    main_subject.register_observer(user1_observer)
    main_subject.register_observer(user2_observer)
    
    print("\n1. Publishing various events:")
    
    # Create test events
    events = [
        Event(
            event_type=EventType.USER_LOGIN,
            data={"user_id": "user_123", "ip_address": "192.168.1.100"},
            source="auth_service"
        ),
        Event(
            event_type=EventType.DATA_UPDATED,
            data={"data_type": "profile", "owner_id": "user_123"},
            source="profile_service"
        ),
        Event(
            event_type=EventType.SYSTEM_ERROR,
            data={"error_message": "Database connection failed", "severity": "high"},
            source="db_service"
        ),
        Event(
            event_type=EventType.USER_LOGIN,
            data={"user_id": "user_456", "ip_address": "10.0.0.50"},
            source="auth_service"
        ),
        Event(
            event_type=EventType.SYSTEM_ERROR,
            data={"error_message": "Cache timeout", "severity": "medium"},
            source="cache_service"
        ),
        Event(
            event_type=EventType.PERFORMANCE_ALERT,
            data={"metric": "response_time", "value": 5.2, "threshold": 3.0},
            source="monitoring_service"
        ),
        Event(
            event_type=EventType.USER_LOGOUT,
            data={"user_id": "user_123"},
            source="auth_service"
        )
    ]
    
    # Publish events one by one
    for event in events:
        print(f"\n--- Publishing {event.event_type.value} event ---")
        result = await main_subject.notify_observers(event)
        await asyncio.sleep(0.2)  # Brief pause between events
    
    print("\n2. Observer statistics:")
    
    print(f"   Logging Observer: {logging_observer.events_logged} events logged")
    
    metrics = metrics_observer.get_metrics()
    print(f"   Metrics Observer: {metrics}")
    
    print(f"   Alert Observer: {alert_observer.alerts_sent} alerts sent, "
          f"{alert_observer.error_count} errors pending")
    
    print(f"   User 123 Notifications: {user1_observer.notifications_sent} notifications sent")
    print(f"   User 456 Notifications: {user2_observer.notifications_sent} notifications sent")
    
    print("\n3. Event filtering and forwarding:")
    
    # Create secondary subject for filtered events
    filtered_subject = AsyncEventSubject()
    filtered_logging = LoggingObserver("FILTERED")
    filtered_subject.register_observer(filtered_logging)
    
    # Create filter observer that forwards only user events to secondary subject
    filter_observer = EventFilterObserver(
        filter_criteria={"event_type": EventType.USER_LOGIN},
        target_subject=filtered_subject
    )
    main_subject.register_observer(filter_observer)
    
    # Publish more events to test filtering
    test_events = [
        Event(
            event_type=EventType.USER_LOGIN,
            data={"user_id": "user_789"},
            source="test_service"
        ),
        Event(
            event_type=EventType.SYSTEM_ERROR,
            data={"error_message": "Test error"},
            source="test_service"
        ),
        Event(
            event_type=EventType.USER_LOGIN,
            data={"user_id": "user_999"},
            source="test_service"
        )
    ]
    
    print("\n--- Testing event filtering ---")
    for event in test_events:
        await main_subject.notify_observers(event)
        await asyncio.sleep(0.1)
    
    print(f"\n   Filter Observer: {filter_observer.forwarded_events} forwarded, "
          f"{filter_observer.filtered_events} filtered out")
    
    print("\n4. Event history:")
    recent_events = main_subject.get_event_history(limit=5)
    print(f"   Recent events ({len(recent_events)}):")
    for event in recent_events:
        timestamp = time.strftime('%H:%M:%S', time.localtime(event.timestamp))
        print(f"     {timestamp} - {event.event_type.value} from {event.source}")
    
    user_events = main_subject.get_event_history(EventType.USER_LOGIN, limit=3)
    print(f"   Recent user login events ({len(user_events)}):")
    for event in user_events:
        user_id = event.data.get('user_id', 'unknown')
        timestamp = time.strftime('%H:%M:%S', time.localtime(event.timestamp))
        print(f"     {timestamp} - User {user_id} logged in")

asyncio.run(demonstrate_async_observer_pattern())
```

## 14.2 Async Iteration Patterns

Understanding how to work with async iterators and generators is crucial for processing streams of data efficiently.

### Async Generators and Iterators

```python
import asyncio
import random
import time
from typing import AsyncIterator, AsyncGenerator, List, Any, Optional
from dataclasses import dataclass

@dataclass
class DataPoint:
    """Represents a single data point"""
    timestamp: float
    value: float
    source: str
    metadata: dict = None

async def simple_async_generator() -> AsyncGenerator[int, None]:
    """Simple async generator that yields numbers"""
    for i in range(5):
        print(f"   Generating value: {i}")
        await asyncio.sleep(0.1)  # Simulate async work
        yield i

async def data_stream_generator(source: str, count: int = 10) -> AsyncGenerator[DataPoint, None]:
    """Generate a stream of data points"""
    for i in range(count):
        # Simulate varying generation times
        await asyncio.sleep(random.uniform(0.05, 0.15))
        
        data_point = DataPoint(
            timestamp=time.time(),
            value=random.uniform(10, 100),
            source=source,
            metadata={"sequence": i, "batch": i // 3}
        )
        
        print(f"   {source}: Generated data point {i} (value: {data_point.value:.2f})")
        yield data_point

class AsyncDataIterator:
    """Custom async iterator for data processing"""
    
    def __init__(self, data_source: List[Any], chunk_size: int = 3, delay: float = 0.1):
        self.data_source = data_source
        self.chunk_size = chunk_size
        self.delay = delay
        self.index = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.data_source):
            raise StopAsyncIteration
        
        # Get next chunk
        chunk = self.data_source[self.index:self.index + self.chunk_size]
        self.index += self.chunk_size
        
        # Simulate processing time
        await asyncio.sleep(self.delay)
        
        print(f"   Iterator: Returning chunk of {len(chunk)} items")
        return chunk

async def demonstrate_async_iteration():
    """Demonstrate async iteration patterns"""
    
    print("=== Async Iteration Patterns ===")
    
    print("1. Simple async generator:")
    
    async for value in simple_async_generator():
        print(f"   Received value: {value}")
    
    print("\n2. Data stream processing:")
    
    async def process_data_stream():
        """Process data from an async generator"""
        total_values = 0
        sum_values = 0.0
        
        async for data_point in data_stream_generator("sensor_A", 5):
            total_values += 1
            sum_values += data_point.value
            
            print(f"   Processing: {data_point.source} at {data_point.timestamp:.3f}, "
                  f"value: {data_point.value:.2f}")
        
        average = sum_values / total_values if total_values > 0 else 0
        print(f"   Stream summary: {total_values} points, average value: {average:.2f}")
    
    await process_data_stream()
    
    print("\n3. Custom async iterator:")
    
    sample_data = list(range(1, 21))  # Numbers 1-20
    async_iter = AsyncDataIterator(sample_data, chunk_size=4, delay=0.05)
    
    chunk_count = 0
    async for chunk in async_iter:
        chunk_count += 1
        print(f"   Chunk {chunk_count}: {chunk}")
    
    print("\n4. Concurrent stream processing:")
    
    async def concurrent_stream_processing():
        """Process multiple streams concurrently"""
        
        # Create multiple data streams
        streams = [
            data_stream_generator("sensor_A", 4),
            data_stream_generator("sensor_B", 4),
            data_stream_generator("sensor_C", 4)
        ]
        
        # Process streams concurrently using asyncio.gather with async generators
        async def process_single_stream(stream_generator, stream_name):
            """Process a single stream"""
            data_points = []
            async for data_point in stream_generator:
                data_points.append(data_point)
            
            # Calculate statistics
            if data_points:
                values = [dp.value for dp in data_points]
                return {
                    "stream_name": stream_name,
                    "count": len(data_points),
                    "min_value": min(values),
                    "max_value": max(values),
                    "avg_value": sum(values) / len(values)
                }
            return {"stream_name": stream_name, "count": 0}
        
        # Process all streams concurrently
        tasks = [
            process_single_stream(stream, f"stream_{i}")
            for i, stream in enumerate(streams)
        ]
        
        results = await asyncio.gather(*tasks)
        
        print("   Concurrent processing results:")
        for result in results:
            if result["count"] > 0:
                print(f"     {result['stream_name']}: {result['count']} points, "
                      f"avg: {result['avg_value']:.2f}, "
                      f"range: {result['min_value']:.2f}-{result['max_value']:.2f}")
            else:
                print(f"     {result['stream_name']}: No data")
    
    await concurrent_stream_processing()

asyncio.run(demonstrate_async_iteration())
```

### Stream Processing Patterns

```python
import asyncio
import time
import random
from typing import AsyncIterator, List, Callable, Any, Optional, TypeVar
from collections import deque
from dataclasses import dataclass

T = TypeVar('T')
U = TypeVar('U')

@dataclass
class StreamItem:
    """Generic stream item with metadata"""
    data: Any
    timestamp: float = None
    sequence_id: int = None
    metadata: dict = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.metadata is None:
            self.metadata = {}

class AsyncStreamProcessor:
    """Utility class for stream processing operations"""
    
    @staticmethod
    async def map_stream(stream: AsyncIterator[T], 
                        transform_func: Callable[[T], U]) -> AsyncIterator[U]:
        """Map transformation function over async stream"""
        async for item in stream:
            transformed = transform_func(item)
            yield transformed
    
    @staticmethod
    async def filter_stream(stream: AsyncIterator[T], 
                           predicate: Callable[[T], bool]) -> AsyncIterator[T]:
        """Filter stream items based on predicate"""
        async for item in stream:
            if predicate(item):
                yield item
    
    @staticmethod
    async def batch_stream(stream: AsyncIterator[T], 
                          batch_size: int, 
                          timeout: Optional[float] = None) -> AsyncIterator[List[T]]:
        """Batch stream items into groups"""
        batch = []
        last_yield_time = time.time()
        
        async for item in stream:
            batch.append(item)
            
            # Yield batch if size reached or timeout exceeded
            should_yield = (
                len(batch) >= batch_size or
                (timeout and time.time() - last_yield_time >= timeout)
            )
            
            if should_yield:
                yield batch
                batch = []
                last_yield_time = time.time()
        
        # Yield remaining items
        if batch:
            yield batch
    
    @staticmethod
    async def take_stream(stream: AsyncIterator[T], count: int) -> AsyncIterator[T]:
        """Take only the first 'count' items from stream"""
        taken = 0
        async for item in stream:
            if taken >= count:
                break
            yield item
            taken += 1
    
    @staticmethod
    async def skip_stream(stream: AsyncIterator[T], count: int) -> AsyncIterator[T]:
        """Skip the first 'count' items from stream"""
        skipped = 0
        async for item in stream:
            if skipped < count:
                skipped += 1
                continue
            yield item
    
    @staticmethod
    async def buffer_stream(stream: AsyncIterator[T], 
                           buffer_size: int) -> AsyncIterator[T]:
        """Buffer stream items to smooth out irregular timing"""
        buffer = deque()
        stream_iter = aiter(stream)
        
        # Fill initial buffer
        for _ in range(buffer_size):
            try:
                item = await anext(stream_iter)
                buffer.append(item)
            except StopAsyncIteration:
                break
        
        # Yield from buffer while refilling
        while buffer:
            yield buffer.popleft()
            
            # Try to refill buffer
            try:
                item = await anext(stream_iter)
                buffer.append(item)
            except StopAsyncIteration:
                pass
    
    @staticmethod
    async def merge_streams(*streams: AsyncIterator[T]) -> AsyncIterator[T]:
        """Merge multiple streams into one, yielding items as they arrive"""
        
        # Convert streams to tasks
        stream_tasks = []
        for i, stream in enumerate(streams):
            async def stream_wrapper(stream, stream_id):
                async for item in stream:
                    yield (stream_id, item)
            
            stream_tasks.append(stream_wrapper(stream, i))
        
        # Create iterators for all streams
        stream_iters = [aiter(task) for task in stream_tasks]
        active_streams = set(range(len(stream_iters)))
        
        while active_streams:
            # Create tasks to get next item from each active stream
            next_item_tasks = {}
            
            for stream_id in list(active_streams):
                async def get_next_item(stream_iter, sid):
                    try:
                        return await anext(stream_iter)
                    except StopAsyncIteration:
                        return None
                
                task = asyncio.create_task(get_next_item(stream_iters[stream_id], stream_id))
                next_item_tasks[stream_id] = task
            
            if not next_item_tasks:
                break
            
            # Wait for first stream to produce an item
            done, pending = await asyncio.wait(
                next_item_tasks.values(),
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            
            # Process completed tasks
            for task in done:
                result = await task
                
                if result is None:
                    # Stream ended, remove from active streams
                    for sid, t in next_item_tasks.items():
                        if t == task:
                            active_streams.discard(sid)
                            break
                else:
                    stream_id, item = result
                    yield item

async def generate_sensor_data(sensor_id: str, 
                              duration: float = 2.0, 
                              frequency: float = 0.1) -> AsyncIterator[StreamItem]:
    """Generate simulated sensor data"""
    start_time = time.time()
    sequence = 0
    
    while time.time() - start_time < duration:
        await asyncio.sleep(frequency + random.uniform(-0.02, 0.02))
        
        data = {
            "sensor_id": sensor_id,
            "temperature": random.uniform(20, 30),
            "humidity": random.uniform(40, 60),
            "pressure": random.uniform(1000, 1020)
        }
        
        yield StreamItem(
            data=data,
            sequence_id=sequence,
            metadata={"sensor_type": "environmental"}
        )
        
        sequence += 1

async def generate_event_stream(event_type: str, 
                               count: int = 10) -> AsyncIterator[StreamItem]:
    """Generate simulated event data"""
    for i in range(count):
        await asyncio.sleep(random.uniform(0.05, 0.2))
        
        data = {
            "event_type": event_type,
            "event_id": f"{event_type}_{i}",
            "severity": random.choice(["low", "medium", "high"]),
            "message": f"Event {i} of type {event_type}"
        }
        
        yield StreamItem(
            data=data,
            sequence_id=i,
            metadata={"category": "system_event"}
        )

async def demonstrate_stream_processing():
    """Demonstrate stream processing patterns"""
    
    print("=== Stream Processing Patterns ===")
    
    print("1. Basic stream transformations:")
    
    # Create a simple data stream
    async def number_stream():
        for i in range(10):
            await asyncio.sleep(0.05)
            yield StreamItem(data=i)
    
    # Transform: multiply by 2
    transformed_stream = AsyncStreamProcessor.map_stream(
        number_stream(),
        lambda item: StreamItem(
            data=item.data * 2,
            timestamp=item.timestamp,
            metadata={"transformed": True}
        )
    )
    
    # Filter: only even results
    filtered_stream = AsyncStreamProcessor.filter_stream(
        transformed_stream,
        lambda item: item.data % 4 == 0  # Even after multiplication by 2
    )
    
    print("   Processing transformed and filtered stream:")
    async for item in filtered_stream:
        print(f"   Item: {item.data} (timestamp: {item.timestamp:.3f})")
    
    print("\n2. Stream batching:")
    
    # Create larger stream for batching
    async def large_stream():
        for i in range(15):
            await asyncio.sleep(0.03)
            yield StreamItem(data=f"item_{i}")
    
    batched_stream = AsyncStreamProcessor.batch_stream(
        large_stream(),
        batch_size=4,
        timeout=0.2
    )
    
    batch_count = 0
    async for batch in batched_stream:
        batch_count += 1
        items = [item.data for item in batch]
        print(f"   Batch {batch_count}: {items}")
    
    print("\n3. Stream slicing (take/skip):")
    
    async def counted_stream():
        for i in range(20):
            await asyncio.sleep(0.02)
            yield StreamItem(data=f"data_{i}")
    
    # Skip first 5, then take next 8
    sliced_stream = AsyncStreamProcessor.take_stream(
        AsyncStreamProcessor.skip_stream(counted_stream(), 5),
        8
    )
    
    print("   Sliced stream (skip 5, take 8):")
    async for item in sliced_stream:
        print(f"   {item.data}")
    
    print("\n4. Stream buffering:")
    
    async def irregular_stream():
        """Stream with irregular timing"""
        delays = [0.01, 0.15, 0.02, 0.12, 0.03, 0.1, 0.02, 0.08]
        for i, delay in enumerate(delays):
            await asyncio.sleep(delay)
            yield StreamItem(data=f"irregular_{i}")
    
    print("   Original irregular stream timing:")
    start_time = time.time()
    async for item in irregular_stream():
        elapsed = time.time() - start_time
        print(f"   {elapsed:.3f}s: {item.data}")
    
    print("\n   Buffered stream (buffer size 3):")
    start_time = time.time()
    buffered_stream = AsyncStreamProcessor.buffer_stream(irregular_stream(), 3)
    async for item in buffered_stream:
        elapsed = time.time() - start_time
        print(f"   {elapsed:.3f}s: {item.data}")
    
    print("\n5. Merging multiple streams:")
    
    async def process_merged_streams():
        """Process multiple streams concurrently"""
        
        # Create multiple streams with different characteristics
        sensor_stream = generate_sensor_data("temp_01", duration=1.0, frequency=0.1)
        event_stream = generate_event_stream("alert", count=5)
        
        async def simple_data_stream():
            for i in range(6):
                await asyncio.sleep(0.15)
                yield StreamItem(data=f"simple_data_{i}")
        
        # Merge all streams
        merged = AsyncStreamProcessor.merge_streams(
            sensor_stream,
            event_stream,
            simple_data_stream()
        )
        
        print("   Merged stream output:")
        item_count = 0
        start_time = time.time()
        
        async for item in merged:
            elapsed = time.time() - start_time
            item_count += 1
            
            if "sensor_id" in item.data:
                temp = item.data.get("temperature", 0)
                print(f"   {elapsed:.3f}s: Sensor data - temp: {temp:.1f}°C")
            elif "event_type" in item.data:
                event_id = item.data.get("event_id", "unknown")
                severity = item.data.get("severity", "unknown")
                print(f"   {elapsed:.3f}s: Event - {event_id} ({severity})")
            else:
                print(f"   {elapsed:.3f}s: Simple data - {item.data}")
        
        print(f"   Total merged items: {item_count}")
    
    await process_merged_streams()
    
    print("\n6. Complex stream processing pipeline:")
    
    async def complex_pipeline():
        """Demonstrate a complex stream processing pipeline"""
        
        # Generate sensor data stream
        raw_stream = generate_sensor_data("multi_sensor", duration=1.5, frequency=0.08)
        
        # Step 1: Filter out readings with extreme temperatures
        filtered_stream = AsyncStreamProcessor.filter_stream(
            raw_stream,
            lambda item: 22 <= item.data.get("temperature", 0) <= 28
        )
        
        # Step 2: Add computed features
        enhanced_stream = AsyncStreamProcessor.map_stream(
            filtered_stream,
            lambda item: StreamItem(
                data={
                    **item.data,
                    "comfort_index": (
                        item.data.get("temperature", 25) * 0.7 + 
                        item.data.get("humidity", 50) * 0.3
                    ),
                    "processed_at": time.time()
                },
                timestamp=item.timestamp,
                sequence_id=item.sequence_id,
                metadata={**item.metadata, "enhanced": True}
            )
        )
        
        # Step 3: Batch for processing efficiency
        batched_stream = AsyncStreamProcessor.batch_stream(
            enhanced_stream,
            batch_size=3,
            timeout=0.3
        )
        
        print("   Complex pipeline output:")
        batch_num = 0
        total_items = 0
        
        async for batch in batched_stream:
            batch_num += 1
            total_items += len(batch)
            
            # Process batch statistics
            temperatures = [item.data["temperature"] for item in batch]
            comfort_indices = [item.data["comfort_index"] for item in batch]
            
            avg_temp = sum(temperatures) / len(temperatures)
            avg_comfort = sum(comfort_indices) / len(comfort_indices)
            
            print(f"   Batch {batch_num} ({len(batch)} items): "
                  f"avg temp: {avg_temp:.1f}°C, avg comfort: {avg_comfort:.1f}")
        
        print(f"   Pipeline processed {total_items} items in {batch_num} batches")
    
    await complex_pipeline()

asyncio.run(demonstrate_stream_processing())
```

This completes Chapter 14 on Async Patterns and Idioms. The chapter demonstrates:

1. **Common Async Design Patterns** - Context managers, factory pattern, and observer pattern
2. **Async Iteration Patterns** - Generators, iterators, and stream processing

These patterns are fundamental for building well-structured asyncio applications and provide the building blocks for more complex systems. The examples show practical implementations that can be adapted for real-world use cases.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content":"Write Chapter 1: Understanding Asynchronous Programming","status":"completed","id":"ch1"},{"content":"Write Chapter 2: The Event Loop - Heart of Asyncio","status":"completed","id":"ch2"},{"content":"Write Chapter 3: Coroutines - The Building Blocks","status":"completed","id":"ch3"},{"content":"Write Chapter 4: Tasks and Futures","status":"completed","id":"ch4"},{"content":"Write Chapter 5: Synchronization Primitives","status":"completed","id":"ch5"},{"content":"Write Chapter 6: Queues and Producer-Consumer Patterns","status":"completed","id":"ch6"},{"content":"Write Chapter 7: Streams - High-Level Network I/O","status":"completed","id":"ch7"},{"content":"Write Chapter 8: Transports and Protocols - Low-Level Network I/O","status":"completed","id":"ch8"},{"content":"Write Chapter 9: Subprocesses","status":"completed","id":"ch9"},{"content":"Write Chapter 10: Exception Handling and Debugging","status":"completed","id":"ch10"},{"content":"Write Chapter 11: Timeouts and Cancellation","status":"completed","id":"ch11"},{"content":"Write Chapter 12: Mixing Asyncio with Threads and Processes","status":"completed","id":"ch12"},{"content":"Write Chapter 13: Context Variables and Task Context","status":"completed","id":"ch13"},{"content":"Write Chapter 14: Async Patterns and Idioms","status":"completed","id":"ch14"},{"content":"Continue with remaining chapters 15-36","status":"in_progress","id":"remaining-chapters"}]