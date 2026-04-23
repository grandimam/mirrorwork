# Chapter 17: Building Async Libraries

## 17.1 Library Design Principles

When building async libraries, following good design principles ensures your library is easy to use, performant, and maintainable. This chapter covers the essential patterns for creating professional asyncio libraries.

### Core Design Principles

```python
import asyncio
import abc
from typing import Optional, Dict, Any, Callable, AsyncIterator, Union, TypeVar, Generic
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import weakref
import time
import logging

T = TypeVar('T')
R = TypeVar('R')

class AsyncLibraryBase(abc.ABC):
    """Base class for async libraries with common patterns"""
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"{self.__module__}.{self.name}")
        self._closed = False
        self._cleanup_callbacks = []
        
    @abc.abstractmethod
    async def initialize(self) -> None:
        """Initialize the library component"""
        pass
    
    @abc.abstractmethod
    async def close(self) -> None:
        """Clean up resources"""
        pass
    
    def add_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """Add a cleanup callback"""
        self._cleanup_callbacks.append(callback)
    
    def _check_not_closed(self) -> None:
        """Check if library is not closed"""
        if self._closed:
            raise RuntimeError(f"{self.name} is closed")
    
    async def _run_cleanup_callbacks(self) -> None:
        """Run all cleanup callbacks"""
        for callback in self._cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                self.logger.error(f"Error in cleanup callback: {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

@dataclass
class LibraryConfig:
    """Configuration class for async libraries"""
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_logging: bool = True
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    def validate(self) -> None:
        """Validate configuration"""
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("Max retries cannot be negative")
        if self.retry_delay < 0:
            raise ValueError("Retry delay cannot be negative")

class EventEmitter:
    """Simple event emitter for async libraries"""
    
    def __init__(self):
        self._listeners: Dict[str, list] = {}
        self._max_listeners = 10
    
    def on(self, event: str, callback: Callable) -> None:
        """Add event listener"""
        if event not in self._listeners:
            self._listeners[event] = []
        
        if len(self._listeners[event]) >= self._max_listeners:
            raise RuntimeError(f"Too many listeners for event '{event}'")
        
        self._listeners[event].append(callback)
    
    def off(self, event: str, callback: Callable) -> None:
        """Remove event listener"""
        if event in self._listeners:
            try:
                self._listeners[event].remove(callback)
            except ValueError:
                pass
    
    async def emit(self, event: str, *args, **kwargs) -> None:
        """Emit event to all listeners"""
        if event in self._listeners:
            for callback in self._listeners[event].copy():
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    # Log error but don't stop other listeners
                    logging.error(f"Error in event listener for '{event}': {e}")

async def demonstrate_library_base():
    """Demonstrate base library patterns"""
    
    print("=== Library Design Principles ===")
    
    class MyAsyncLibrary(AsyncLibraryBase):
        """Example async library implementation"""
        
        def __init__(self, config: LibraryConfig):
            super().__init__("MyAsyncLibrary")
            self.config = config
            self.config.validate()
            self.events = EventEmitter()
            self._connections = []
            
        async def initialize(self) -> None:
            """Initialize the library"""
            self.logger.info(f"Initializing {self.name}")
            
            # Simulate initialization
            await asyncio.sleep(0.1)
            
            # Set up event listeners
            self.events.on('connection_created', self._on_connection_created)
            self.events.on('connection_closed', self._on_connection_closed)
            
            self.logger.info(f"{self.name} initialized successfully")
        
        async def create_connection(self, target: str) -> str:
            """Create a new connection"""
            self._check_not_closed()
            
            connection_id = f"conn_{len(self._connections)}_{int(time.time())}"
            
            # Simulate connection creation
            await asyncio.sleep(0.05)
            
            self._connections.append({
                'id': connection_id,
                'target': target,
                'created_at': time.time()
            })
            
            await self.events.emit('connection_created', connection_id, target)
            
            return connection_id
        
        async def close_connection(self, connection_id: str) -> bool:
            """Close a connection"""
            self._check_not_closed()
            
            for i, conn in enumerate(self._connections):
                if conn['id'] == connection_id:
                    del self._connections[i]
                    await self.events.emit('connection_closed', connection_id)
                    return True
            
            return False
        
        async def execute_operation(self, operation: str, **kwargs) -> str:
            """Execute an operation with retry logic"""
            self._check_not_closed()
            
            for attempt in range(self.config.max_retries + 1):
                try:
                    # Simulate operation that might fail
                    if attempt < 2:  # Fail first 2 attempts
                        raise ConnectionError("Simulated connection error")
                    
                    await asyncio.sleep(0.1)  # Simulate work
                    result = f"Operation '{operation}' completed successfully"
                    
                    if kwargs:
                        result += f" with params: {kwargs}"
                    
                    return result
                
                except Exception as e:
                    if attempt == self.config.max_retries:
                        raise  # Final attempt failed
                    
                    self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(self.config.retry_delay)
        
        def _on_connection_created(self, connection_id: str, target: str) -> None:
            """Handle connection created event"""
            self.logger.info(f"Connection created: {connection_id} -> {target}")
        
        def _on_connection_closed(self, connection_id: str) -> None:
            """Handle connection closed event"""
            self.logger.info(f"Connection closed: {connection_id}")
        
        async def close(self) -> None:
            """Close the library"""
            if self._closed:
                return
            
            self.logger.info(f"Closing {self.name}")
            
            # Close all connections
            connection_ids = [conn['id'] for conn in self._connections]
            for conn_id in connection_ids:
                await self.close_connection(conn_id)
            
            # Run cleanup callbacks
            await self._run_cleanup_callbacks()
            
            self._closed = True
            self.logger.info(f"{self.name} closed")
        
        @property
        def stats(self) -> Dict[str, Any]:
            """Get library statistics"""
            return {
                'active_connections': len(self._connections),
                'is_closed': self._closed,
                'config': {
                    'timeout': self.config.timeout,
                    'max_retries': self.config.max_retries
                }
            }
    
    print("1. Using library with context manager:")
    
    config = LibraryConfig(
        timeout=10.0,
        max_retries=2,
        retry_delay=0.1,
        enable_logging=True
    )
    
    async with MyAsyncLibrary(config) as lib:
        print(f"   Library stats: {lib.stats}")
        
        # Create some connections
        conn1 = await lib.create_connection("server1.example.com")
        conn2 = await lib.create_connection("server2.example.com")
        
        print(f"   Created connections: {conn1}, {conn2}")
        
        # Execute operations
        result = await lib.execute_operation("backup_data", table="users")
        print(f"   Operation result: {result}")
        
        # Close one connection
        await lib.close_connection(conn1)
        
        print(f"   Final stats: {lib.stats}")
    
    print("   Library automatically closed via context manager")

asyncio.run(demonstrate_library_base())
```

### Plugin Architecture

```python
import asyncio
import abc
import importlib
from typing import Dict, Any, List, Optional, Type, Callable
from dataclasses import dataclass
from pathlib import Path
import json

class PluginBase(abc.ABC):
    """Base class for plugins"""
    
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Plugin name"""
        pass
    
    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Plugin version"""
        pass
    
    @abc.abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin"""
        pass
    
    @abc.abstractmethod
    async def cleanup(self) -> None:
        """Cleanup plugin resources"""
        pass
    
    def get_dependencies(self) -> List[str]:
        """Get list of plugin dependencies"""
        return []

@dataclass
class PluginInfo:
    """Information about a plugin"""
    name: str
    version: str
    description: str
    author: str
    entry_point: str
    config_schema: Dict[str, Any]
    dependencies: List[str]

class PluginRegistry:
    """Registry for managing plugins"""
    
    def __init__(self):
        self._plugins: Dict[str, PluginBase] = {}
        self._plugin_info: Dict[str, PluginInfo] = {}
        self._hooks: Dict[str, List[Callable]] = {}
    
    def register_plugin(self, plugin: PluginBase, info: PluginInfo) -> None:
        """Register a plugin"""
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' already registered")
        
        self._plugins[plugin.name] = plugin
        self._plugin_info[plugin.name] = info
        
        print(f"   Registered plugin: {plugin.name} v{plugin.version}")
    
    def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister a plugin"""
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
            del self._plugin_info[plugin_name]
            print(f"   Unregistered plugin: {plugin_name}")
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """Get a plugin by name"""
        return self._plugins.get(plugin_name)
    
    def list_plugins(self) -> List[str]:
        """List all registered plugins"""
        return list(self._plugins.keys())
    
    def register_hook(self, hook_name: str, callback: Callable) -> None:
        """Register a hook callback"""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(callback)
    
    async def call_hooks(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Call all hooks for a given name"""
        results = []
        
        if hook_name in self._hooks:
            for callback in self._hooks[hook_name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        result = await callback(*args, **kwargs)
                    else:
                        result = callback(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    print(f"   Hook '{hook_name}' error: {e}")
        
        return results

class AsyncLibraryWithPlugins(AsyncLibraryBase):
    """Async library with plugin support"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("PluggableLibrary")
        self.config = config
        self.registry = PluginRegistry()
        self._initialized_plugins = set()
    
    async def initialize(self) -> None:
        """Initialize the library"""
        self.logger.info("Initializing pluggable library")
        
        # Load and initialize plugins
        await self._load_plugins()
        
        self.logger.info("Pluggable library initialized")
    
    async def _load_plugins(self) -> None:
        """Load plugins from configuration"""
        plugin_configs = self.config.get('plugins', {})
        
        for plugin_name, plugin_config in plugin_configs.items():
            try:
                await self._load_single_plugin(plugin_name, plugin_config)
            except Exception as e:
                self.logger.error(f"Failed to load plugin '{plugin_name}': {e}")
    
    async def _load_single_plugin(self, plugin_name: str, plugin_config: Dict[str, Any]) -> None:
        """Load a single plugin"""
        # This is a simplified plugin loading mechanism
        # In a real implementation, you'd load from files or packages
        
        plugin_class = self._get_plugin_class(plugin_name)
        if not plugin_class:
            raise ValueError(f"Plugin class not found: {plugin_name}")
        
        plugin_instance = plugin_class()
        
        # Create plugin info
        info = PluginInfo(
            name=plugin_instance.name,
            version=plugin_instance.version,
            description=plugin_config.get('description', ''),
            author=plugin_config.get('author', 'Unknown'),
            entry_point=plugin_name,
            config_schema={},
            dependencies=plugin_instance.get_dependencies()
        )
        
        # Register plugin
        self.registry.register_plugin(plugin_instance, info)
        
        # Initialize plugin
        await plugin_instance.initialize(plugin_config)
        self._initialized_plugins.add(plugin_name)
        
        print(f"   Loaded and initialized plugin: {plugin_name}")
    
    def _get_plugin_class(self, plugin_name: str) -> Optional[Type[PluginBase]]:
        """Get plugin class - simplified for demo"""
        # In a real implementation, this would dynamically import plugin modules
        plugin_classes = {
            'data_processor': DataProcessorPlugin,
            'cache_manager': CacheManagerPlugin,
            'metrics_collector': MetricsCollectorPlugin
        }
        
        return plugin_classes.get(plugin_name)
    
    async def process_data(self, data: Any) -> Any:
        """Process data using plugins"""
        self._check_not_closed()
        
        # Call pre-processing hooks
        await self.registry.call_hooks('before_process', data)
        
        # Use data processor plugin if available
        data_processor = self.registry.get_plugin('data_processor')
        if data_processor:
            result = await data_processor.process(data)
        else:
            result = f"Default processing of: {data}"
        
        # Call post-processing hooks
        await self.registry.call_hooks('after_process', result)
        
        return result
    
    async def close(self) -> None:
        """Close the library and cleanup plugins"""
        if self._closed:
            return
        
        self.logger.info("Closing pluggable library")
        
        # Cleanup plugins in reverse order
        for plugin_name in reversed(list(self._initialized_plugins)):
            try:
                plugin = self.registry.get_plugin(plugin_name)
                if plugin:
                    await plugin.cleanup()
                self.registry.unregister_plugin(plugin_name)
            except Exception as e:
                self.logger.error(f"Error cleaning up plugin '{plugin_name}': {e}")
        
        self._initialized_plugins.clear()
        
        await self._run_cleanup_callbacks()
        self._closed = True
        
        self.logger.info("Pluggable library closed")

# Example plugin implementations
class DataProcessorPlugin(PluginBase):
    """Example data processing plugin"""
    
    @property
    def name(self) -> str:
        return "data_processor"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin"""
        self.processing_mode = config.get('mode', 'standard')
        print(f"   Data processor initialized with mode: {self.processing_mode}")
    
    async def cleanup(self) -> None:
        """Cleanup plugin resources"""
        print(f"   Data processor plugin cleaned up")
    
    async def process(self, data: Any) -> Any:
        """Process data"""
        await asyncio.sleep(0.05)  # Simulate processing
        
        if self.processing_mode == 'enhanced':
            return f"Enhanced processing result: {data}"
        else:
            return f"Standard processing result: {data}"

class CacheManagerPlugin(PluginBase):
    """Example cache management plugin"""
    
    @property
    def name(self) -> str:
        return "cache_manager"
    
    @property
    def version(self) -> str:
        return "1.2.0"
    
    def get_dependencies(self) -> List[str]:
        return ["data_processor"]
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin"""
        self.cache_size = config.get('cache_size', 100)
        self._cache = {}
        print(f"   Cache manager initialized with size: {self.cache_size}")
    
    async def cleanup(self) -> None:
        """Cleanup plugin resources"""
        self._cache.clear()
        print(f"   Cache manager plugin cleaned up")
    
    async def get(self, key: str) -> Any:
        """Get from cache"""
        return self._cache.get(key)
    
    async def set(self, key: str, value: Any) -> None:
        """Set cache value"""
        if len(self._cache) >= self.cache_size:
            # Simple eviction: remove first item
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[key] = value

class MetricsCollectorPlugin(PluginBase):
    """Example metrics collection plugin"""
    
    @property
    def name(self) -> str:
        return "metrics_collector"
    
    @property
    def version(self) -> str:
        return "2.1.0"
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin"""
        self.metrics = {}
        self.collection_interval = config.get('interval', 10.0)
        print(f"   Metrics collector initialized with interval: {self.collection_interval}s")
    
    async def cleanup(self) -> None:
        """Cleanup plugin resources"""
        print(f"   Metrics collector plugin cleaned up")
    
    def record_metric(self, name: str, value: float) -> None:
        """Record a metric"""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append({'value': value, 'timestamp': time.time()})
    
    def get_metrics(self) -> Dict[str, List]:
        """Get collected metrics"""
        return self.metrics.copy()

async def demonstrate_plugin_architecture():
    """Demonstrate plugin architecture"""
    
    print("=== Plugin Architecture ===")
    
    config = {
        'plugins': {
            'data_processor': {
                'mode': 'enhanced',
                'description': 'Enhanced data processing plugin'
            },
            'cache_manager': {
                'cache_size': 50,
                'description': 'In-memory cache manager'
            },
            'metrics_collector': {
                'interval': 5.0,
                'description': 'System metrics collector'
            }
        }
    }
    
    print("1. Initializing library with plugins:")
    
    async with AsyncLibraryWithPlugins(config) as lib:
        print(f"   Available plugins: {lib.registry.list_plugins()}")
        
        # Use plugins through the main library interface
        result1 = await lib.process_data("sample data 1")
        result2 = await lib.process_data("sample data 2")
        
        print(f"   Processing results:")
        print(f"     {result1}")
        print(f"     {result2}")
        
        # Access plugins directly if needed
        cache_plugin = lib.registry.get_plugin('cache_manager')
        if cache_plugin:
            await cache_plugin.set('test_key', 'test_value')
            cached_value = await cache_plugin.get('test_key')
            print(f"   Cache test: {cached_value}")
        
        metrics_plugin = lib.registry.get_plugin('metrics_collector')
        if metrics_plugin:
            metrics_plugin.record_metric('processing_time', 0.123)
            metrics_plugin.record_metric('processing_time', 0.156)
            metrics = metrics_plugin.get_metrics()
            print(f"   Collected metrics: {metrics}")
    
    print("   Library and plugins automatically closed")

asyncio.run(demonstrate_plugin_architecture())
```

## 17.2 API Design Patterns

Creating intuitive and consistent APIs is crucial for library adoption and ease of use.

### Fluent Interface Pattern

```python
import asyncio
from typing import Dict, Any, List, Optional, Union, Self
from dataclasses import dataclass, field
from enum import Enum
import json
import time

class QueryType(Enum):
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

@dataclass
class QueryCondition:
    """Represents a query condition"""
    field: str
    operator: str
    value: Any

@dataclass
class QueryBuilder:
    """Fluent query builder for database operations"""
    
    query_type: Optional[QueryType] = None
    table: Optional[str] = None
    fields: List[str] = field(default_factory=list)
    conditions: List[QueryCondition] = field(default_factory=list)
    joins: List[str] = field(default_factory=list)
    order_by: List[str] = field(default_factory=list)
    limit_count: Optional[int] = None
    offset_count: Optional[int] = None
    values: Dict[str, Any] = field(default_factory=dict)
    
    def select(self, *fields: str) -> Self:
        """Start a SELECT query"""
        self.query_type = QueryType.SELECT
        self.fields.extend(fields)
        return self
    
    def insert_into(self, table: str) -> Self:
        """Start an INSERT query"""
        self.query_type = QueryType.INSERT
        self.table = table
        return self
    
    def update(self, table: str) -> Self:
        """Start an UPDATE query"""
        self.query_type = QueryType.UPDATE
        self.table = table
        return self
    
    def delete_from(self, table: str) -> Self:
        """Start a DELETE query"""
        self.query_type = QueryType.DELETE
        self.table = table
        return self
    
    def from_table(self, table: str) -> Self:
        """Specify table for SELECT"""
        self.table = table
        return self
    
    def where(self, field: str, operator: str = "=", value: Any = None) -> Self:
        """Add WHERE condition"""
        self.conditions.append(QueryCondition(field, operator, value))
        return self
    
    def and_where(self, field: str, operator: str = "=", value: Any = None) -> Self:
        """Add AND WHERE condition"""
        return self.where(field, operator, value)
    
    def join(self, table: str, on_condition: str) -> Self:
        """Add JOIN clause"""
        self.joins.append(f"JOIN {table} ON {on_condition}")
        return self
    
    def left_join(self, table: str, on_condition: str) -> Self:
        """Add LEFT JOIN clause"""
        self.joins.append(f"LEFT JOIN {table} ON {on_condition}")
        return self
    
    def order_by_field(self, field: str, direction: str = "ASC") -> Self:
        """Add ORDER BY clause"""
        self.order_by.append(f"{field} {direction}")
        return self
    
    def limit(self, count: int) -> Self:
        """Add LIMIT clause"""
        self.limit_count = count
        return self
    
    def offset(self, count: int) -> Self:
        """Add OFFSET clause"""
        self.offset_count = count
        return self
    
    def set_values(self, **values) -> Self:
        """Set values for INSERT/UPDATE"""
        self.values.update(values)
        return self
    
    def set_value(self, field: str, value: Any) -> Self:
        """Set single value for INSERT/UPDATE"""
        self.values[field] = value
        return self
    
    def build(self) -> str:
        """Build the final query string"""
        if not self.query_type:
            raise ValueError("Query type not specified")
        
        if self.query_type == QueryType.SELECT:
            return self._build_select()
        elif self.query_type == QueryType.INSERT:
            return self._build_insert()
        elif self.query_type == QueryType.UPDATE:
            return self._build_update()
        elif self.query_type == QueryType.DELETE:
            return self._build_delete()
    
    def _build_select(self) -> str:
        """Build SELECT query"""
        fields_str = ", ".join(self.fields) if self.fields else "*"
        query = f"SELECT {fields_str} FROM {self.table}"
        
        if self.joins:
            query += " " + " ".join(self.joins)
        
        if self.conditions:
            where_clauses = [f"{c.field} {c.operator} ?" for c in self.conditions]
            query += " WHERE " + " AND ".join(where_clauses)
        
        if self.order_by:
            query += " ORDER BY " + ", ".join(self.order_by)
        
        if self.limit_count:
            query += f" LIMIT {self.limit_count}"
        
        if self.offset_count:
            query += f" OFFSET {self.offset_count}"
        
        return query
    
    def _build_insert(self) -> str:
        """Build INSERT query"""
        if not self.values:
            raise ValueError("No values specified for INSERT")
        
        fields = ", ".join(self.values.keys())
        placeholders = ", ".join("?" * len(self.values))
        
        return f"INSERT INTO {self.table} ({fields}) VALUES ({placeholders})"
    
    def _build_update(self) -> str:
        """Build UPDATE query"""
        if not self.values:
            raise ValueError("No values specified for UPDATE")
        
        set_clauses = [f"{field} = ?" for field in self.values.keys()]
        query = f"UPDATE {self.table} SET " + ", ".join(set_clauses)
        
        if self.conditions:
            where_clauses = [f"{c.field} {c.operator} ?" for c in self.conditions]
            query += " WHERE " + " AND ".join(where_clauses)
        
        return query
    
    def _build_delete(self) -> str:
        """Build DELETE query"""
        query = f"DELETE FROM {self.table}"
        
        if self.conditions:
            where_clauses = [f"{c.field} {c.operator} ?" for c in self.conditions]
            query += " WHERE " + " AND ".join(where_clauses)
        
        return query
    
    def get_parameters(self) -> List[Any]:
        """Get query parameters in order"""
        params = []
        
        # Add values for INSERT/UPDATE
        if self.values and self.query_type in [QueryType.INSERT, QueryType.UPDATE]:
            params.extend(self.values.values())
        
        # Add condition parameters
        params.extend([c.value for c in self.conditions])
        
        return params

class AsyncDatabaseClient:
    """Example database client using fluent interface"""
    
    def __init__(self):
        self._connections = []
        self._query_count = 0
    
    async def connect(self, connection_string: str) -> None:
        """Connect to database"""
        await asyncio.sleep(0.1)  # Simulate connection
        self._connections.append(connection_string)
        print(f"   Connected to database: {connection_string}")
    
    async def execute_query(self, query_builder: QueryBuilder) -> Dict[str, Any]:
        """Execute query from builder"""
        if not self._connections:
            raise RuntimeError("Not connected to database")
        
        query = query_builder.build()
        params = query_builder.get_parameters()
        
        self._query_count += 1
        
        # Simulate query execution
        await asyncio.sleep(0.05)
        
        print(f"   Executing query {self._query_count}: {query}")
        if params:
            print(f"   Parameters: {params}")
        
        # Return mock result
        return {
            "query": query,
            "parameters": params,
            "rows_affected": 1,
            "execution_time": 0.05
        }
    
    def query(self) -> QueryBuilder:
        """Create new query builder"""
        return QueryBuilder()
    
    async def close(self) -> None:
        """Close database connection"""
        self._connections.clear()
        print(f"   Database connection closed. Total queries: {self._query_count}")

async def demonstrate_fluent_interface():
    """Demonstrate fluent interface pattern"""
    
    print("=== Fluent Interface Pattern ===")
    
    db = AsyncDatabaseClient()
    await db.connect("postgresql://localhost/mydb")
    
    print("\n1. SELECT queries with fluent interface:")
    
    # Simple SELECT
    result1 = await db.execute_query(
        db.query()
          .select("id", "name", "email")
          .from_table("users")
          .where("active", "=", True)
          .order_by_field("name", "ASC")
          .limit(10)
    )
    print(f"   Result 1: {result1['rows_affected']} rows")
    
    # Complex SELECT with joins
    result2 = await db.execute_query(
        db.query()
          .select("u.name", "p.title", "c.name")
          .from_table("users u")
          .join("posts p", "p.user_id = u.id")
          .left_join("categories c", "c.id = p.category_id")
          .where("u.active", "=", True)
          .and_where("p.published", "=", True)
          .order_by_field("p.created_at", "DESC")
          .limit(5)
          .offset(10)
    )
    print(f"   Result 2: {result2['rows_affected']} rows")
    
    print("\n2. INSERT/UPDATE/DELETE with fluent interface:")
    
    # INSERT
    result3 = await db.execute_query(
        db.query()
          .insert_into("users")
          .set_values(name="John Doe", email="john@example.com", active=True)
    )
    print(f"   Insert result: {result3['rows_affected']} rows")
    
    # UPDATE
    result4 = await db.execute_query(
        db.query()
          .update("users")
          .set_value("last_login", time.time())
          .set_value("login_count", 5)
          .where("email", "=", "john@example.com")
    )
    print(f"   Update result: {result4['rows_affected']} rows")
    
    # DELETE
    result5 = await db.execute_query(
        db.query()
          .delete_from("users")
          .where("active", "=", False)
          .and_where("last_login", "<", time.time() - 86400)
    )
    print(f"   Delete result: {result5['rows_affected']} rows")
    
    await db.close()

asyncio.run(demonstrate_fluent_interface())
```

### Builder Pattern for Complex Objects

```python
import asyncio
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import time

class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

class RetryStrategy(Enum):
    NONE = "none"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"

@dataclass
class HttpClientConfig:
    """Configuration for HTTP client"""
    base_url: str = ""
    timeout: float = 30.0
    max_redirects: int = 10
    verify_ssl: bool = True
    headers: Dict[str, str] = field(default_factory=dict)
    auth: Optional[tuple] = None
    retry_strategy: RetryStrategy = RetryStrategy.NONE
    max_retries: int = 3
    retry_delay: float = 1.0
    
class HttpRequestBuilder:
    """Builder for HTTP requests"""
    
    def __init__(self, client_config: HttpClientConfig):
        self.client_config = client_config
        self.reset()
    
    def reset(self) -> Self:
        """Reset builder to initial state"""
        self._method = HttpMethod.GET
        self._path = ""
        self._headers = {}
        self._query_params = {}
        self._body = None
        self._timeout = None
        self._follow_redirects = True
        self._stream = False
        self._callbacks = {
            'before_request': [],
            'after_response': [],
            'on_error': []
        }
        return self
    
    def method(self, http_method: Union[HttpMethod, str]) -> Self:
        """Set HTTP method"""
        if isinstance(http_method, str):
            http_method = HttpMethod(http_method.upper())
        self._method = http_method
        return self
    
    def get(self, path: str = "") -> Self:
        """Set GET method and path"""
        self._method = HttpMethod.GET
        self._path = path
        return self
    
    def post(self, path: str = "") -> Self:
        """Set POST method and path"""
        self._method = HttpMethod.POST
        self._path = path
        return self
    
    def put(self, path: str = "") -> Self:
        """Set PUT method and path"""
        self._method = HttpMethod.PUT
        self._path = path
        return self
    
    def delete(self, path: str = "") -> Self:
        """Set DELETE method and path"""
        self._method = HttpMethod.DELETE
        self._path = path
        return self
    
    def path(self, path: str) -> Self:
        """Set request path"""
        self._path = path
        return self
    
    def header(self, name: str, value: str) -> Self:
        """Add request header"""
        self._headers[name] = value
        return self
    
    def headers(self, headers: Dict[str, str]) -> Self:
        """Add multiple headers"""
        self._headers.update(headers)
        return self
    
    def auth(self, username: str, password: str) -> Self:
        """Set basic authentication"""
        import base64
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers["Authorization"] = f"Basic {credentials}"
        return self
    
    def bearer_token(self, token: str) -> Self:
        """Set bearer token authentication"""
        self._headers["Authorization"] = f"Bearer {token}"
        return self
    
    def query(self, name: str, value: str) -> Self:
        """Add query parameter"""
        self._query_params[name] = value
        return self
    
    def query_params(self, params: Dict[str, str]) -> Self:
        """Add multiple query parameters"""
        self._query_params.update(params)
        return self
    
    def json_body(self, data: Dict[str, Any]) -> Self:
        """Set JSON body"""
        self._body = json.dumps(data)
        self._headers["Content-Type"] = "application/json"
        return self
    
    def text_body(self, text: str) -> Self:
        """Set text body"""
        self._body = text
        self._headers["Content-Type"] = "text/plain"
        return self
    
    def form_data(self, data: Dict[str, str]) -> Self:
        """Set form data body"""
        from urllib.parse import urlencode
        self._body = urlencode(data)
        self._headers["Content-Type"] = "application/x-www-form-urlencoded"
        return self
    
    def timeout(self, seconds: float) -> Self:
        """Set request timeout"""
        self._timeout = seconds
        return self
    
    def no_redirects(self) -> Self:
        """Disable redirect following"""
        self._follow_redirects = False
        return self
    
    def stream_response(self) -> Self:
        """Enable response streaming"""
        self._stream = True
        return self
    
    def before_request(self, callback: Callable) -> Self:
        """Add before request callback"""
        self._callbacks['before_request'].append(callback)
        return self
    
    def after_response(self, callback: Callable) -> Self:
        """Add after response callback"""
        self._callbacks['after_response'].append(callback)
        return self
    
    def on_error(self, callback: Callable) -> Self:
        """Add error callback"""
        self._callbacks['on_error'].append(callback)
        return self
    
    def build_request(self) -> Dict[str, Any]:
        """Build the final request configuration"""
        # Construct URL
        url = self.client_config.base_url.rstrip('/') + '/' + self._path.lstrip('/')
        
        if self._query_params:
            from urllib.parse import urlencode
            url += '?' + urlencode(self._query_params)
        
        # Merge headers
        final_headers = {**self.client_config.headers, **self._headers}
        
        # Use client timeout if not overridden
        timeout = self._timeout if self._timeout is not None else self.client_config.timeout
        
        return {
            'method': self._method.value,
            'url': url,
            'headers': final_headers,
            'body': self._body,
            'timeout': timeout,
            'follow_redirects': self._follow_redirects,
            'stream': self._stream,
            'callbacks': self._callbacks.copy()
        }
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the built request"""
        request_config = self.build_request()
        
        # Call before request callbacks
        for callback in request_config['callbacks']['before_request']:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(request_config)
                else:
                    callback(request_config)
            except Exception as e:
                print(f"   Before request callback error: {e}")
        
        try:
            # Simulate HTTP request
            start_time = time.time()
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # Mock response
            response = {
                'status_code': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': '{"success": true, "data": "mock response"}',
                'url': request_config['url'],
                'method': request_config['method'],
                'elapsed_time': time.time() - start_time
            }
            
            # Call after response callbacks
            for callback in request_config['callbacks']['after_response']:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(response)
                    else:
                        callback(response)
                except Exception as e:
                    print(f"   After response callback error: {e}")
            
            return response
        
        except Exception as e:
            # Call error callbacks
            for callback in request_config['callbacks']['on_error']:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(e)
                    else:
                        callback(e)
                except Exception as callback_error:
                    print(f"   Error callback error: {callback_error}")
            
            raise

class AsyncHttpClient:
    """HTTP client with builder pattern"""
    
    def __init__(self, config: HttpClientConfig):
        self.config = config
        self._session_headers = {}
    
    def request(self) -> HttpRequestBuilder:
        """Create a new request builder"""
        return HttpRequestBuilder(self.config)
    
    def set_session_header(self, name: str, value: str) -> None:
        """Set header for all requests in this session"""
        self._session_headers[name] = value
        self.config.headers[name] = value
    
    async def close(self) -> None:
        """Close the HTTP client"""
        print("   HTTP client closed")

async def demonstrate_builder_pattern():
    """Demonstrate builder pattern for complex objects"""
    
    print("=== Builder Pattern ===")
    
    # Create HTTP client with configuration
    config = HttpClientConfig(
        base_url="https://api.example.com",
        timeout=10.0,
        headers={"User-Agent": "AsyncLibrary/1.0"}
    )
    
    client = AsyncHttpClient(config)
    
    print("1. Simple requests using builder:")
    
    # Simple GET request
    response1 = await (client.request()
                      .get("/users")
                      .query("page", "1")
                      .query("limit", "10")
                      .header("Accept", "application/json")
                      .execute())
    
    print(f"   GET response: {response1['status_code']} - {response1['elapsed_time']:.3f}s")
    
    # POST request with JSON body
    response2 = await (client.request()
                      .post("/users")
                      .json_body({
                          "name": "John Doe",
                          "email": "john@example.com"
                      })
                      .bearer_token("abc123def456")
                      .execute())
    
    print(f"   POST response: {response2['status_code']} - {response2['elapsed_time']:.3f}s")
    
    print("\n2. Complex requests with callbacks:")
    
    def log_request(request_config):
        print(f"     → Sending {request_config['method']} to {request_config['url']}")
    
    def log_response(response):
        print(f"     ← Received {response['status_code']} in {response['elapsed_time']:.3f}s")
    
    def handle_error(error):
        print(f"     ✗ Request failed: {error}")
    
    response3 = await (client.request()
                      .put("/users/123")
                      .json_body({"name": "Jane Doe"})
                      .timeout(5.0)
                      .before_request(log_request)
                      .after_response(log_response)
                      .on_error(handle_error)
                      .execute())
    
    print(f"   PUT response processed with callbacks")
    
    print("\n3. Batch requests with reusable builder:")
    
    # Create reusable builder for similar requests
    api_builder = (client.request()
                   .header("API-Version", "v1")
                   .bearer_token("xyz789abc123")
                   .timeout(15.0))
    
    # Clone and customize for different endpoints
    endpoints = ["/stats", "/health", "/version"]
    
    tasks = []
    for endpoint in endpoints:
        # Create a fresh builder for each request
        request_builder = HttpRequestBuilder(config)
        request_builder._headers = api_builder._headers.copy()
        request_builder._timeout = api_builder._timeout
        
        tasks.append(
            request_builder.get(endpoint)
                          .query("format", "json")
                          .execute()
        )
    
    batch_responses = await asyncio.gather(*tasks)
    
    print(f"   Batch requests completed:")
    for i, response in enumerate(batch_responses):
        print(f"     {endpoints[i]}: {response['status_code']}")
    
    await client.close()

asyncio.run(demonstrate_builder_pattern())
```

This completes Chapter 17 on Building Async Libraries. The chapter demonstrates:

1. **Library Design Principles** - Base classes, configuration, event systems, and plugin architecture
2. **API Design Patterns** - Fluent interfaces and builder patterns for creating intuitive APIs

These patterns are essential for creating professional, maintainable, and user-friendly asyncio libraries that developers will enjoy using.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content":"Write Chapter 1: Understanding Asynchronous Programming","status":"completed","id":"ch1"},{"content":"Write Chapter 2: The Event Loop - Heart of Asyncio","status":"completed","id":"ch2"},{"content":"Write Chapter 3: Coroutines - The Building Blocks","status":"completed","id":"ch3"},{"content":"Write Chapter 4: Tasks and Futures","status":"completed","id":"ch4"},{"content":"Write Chapter 5: Synchronization Primitives","status":"completed","id":"ch5"},{"content":"Write Chapter 6: Queues and Producer-Consumer Patterns","status":"completed","id":"ch6"},{"content":"Write Chapter 7: Streams - High-Level Network I/O","status":"completed","id":"ch7"},{"content":"Write Chapter 8: Transports and Protocols - Low-Level Network I/O","status":"completed","id":"ch8"},{"content":"Write Chapter 9: Subprocesses","status":"completed","id":"ch9"},{"content":"Write Chapter 10: Exception Handling and Debugging","status":"completed","id":"ch10"},{"content":"Write Chapter 11: Timeouts and Cancellation","status":"completed","id":"ch11"},{"content":"Write Chapter 12: Mixing Asyncio with Threads and Processes","status":"completed","id":"ch12"},{"content":"Write Chapter 13: Context Variables and Task Context","status":"completed","id":"ch13"},{"content":"Write Chapter 14: Async Patterns and Idioms","status":"completed","id":"ch14"},{"content":"Write Chapter 15: Performance and Optimization","status":"completed","id":"ch15"},{"content":"Write Chapter 17: Building Async Libraries","status":"completed","id":"ch17"},{"content":"Continue with remaining chapters 18-36","status":"in_progress","id":"remaining-chapters"}]