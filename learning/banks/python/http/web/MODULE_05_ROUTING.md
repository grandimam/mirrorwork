# Module 5: Routing Systems

## Overview

Routing is the process of matching an incoming HTTP request to a handler function. A good router is fast, flexible, and intuitive. In this module, you'll implement multiple routing strategies, from simple dictionary lookups to sophisticated radix tree algorithms used by production frameworks.

By the end, you'll understand how frameworks like Flask, FastAPI, and Express resolve URLs, and you'll have built your own high-performance router.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Parse and normalize URLs properly
2. Implement static route matching
3. Build dynamic route matching with path parameters
4. Construct a radix tree (trie) router for O(k) lookups
5. Handle route conflicts and priorities
6. Implement method-based routing
7. Create route groups and prefixes
8. Benchmark and compare routing strategies

---

## 5.1 URL Parsing

### URL Structure Review

```
  https://api.example.com:8080/users/123/posts?page=1&limit=10#comments
  └─┬──┘ └──────┬───────┘└─┬─┘└──────┬──────┘ └───────┬───────┘└───┬───┘
  scheme      host      port      path          query        fragment
```

For routing, we primarily care about:
- **Path**: The hierarchical part after the host
- **Method**: GET, POST, etc. (routed separately)

### Path Normalization

Before routing, normalize the path:

```python
from urllib.parse import unquote


def normalize_path(path: str) -> str:
    """
    Normalize a URL path for consistent routing.

    - Decode percent-encoding
    - Remove . and .. segments
    - Collapse multiple slashes
    - Ensure leading slash
    - Remove trailing slash (optional, but be consistent)
    """
    # Decode percent-encoding
    path = unquote(path)

    # Split into segments
    segments = path.split('/')

    # Resolve . and ..
    resolved = []
    for segment in segments:
        if segment == '..':
            if resolved:
                resolved.pop()
        elif segment == '.':
            continue
        elif segment:  # Skip empty (handles //)
            resolved.append(segment)

    # Rebuild path
    normalized = '/' + '/'.join(resolved)

    return normalized


# Examples:
assert normalize_path('/users/../posts') == '/posts'
assert normalize_path('/api//v1///users') == '/api/v1/users'
assert normalize_path('/hello%20world') == '/hello world'
assert normalize_path('relative/path') == '/relative/path'
```

### Query String Parsing

```python
from urllib.parse import parse_qs, parse_qsl


def parse_query_string(query: str) -> dict:
    """
    Parse query string into dictionary.

    parse_qs returns lists (for multi-value params).
    parse_qsl returns list of tuples (preserves order).
    """
    # parse_qs: {'key': ['value1', 'value2']}
    params = parse_qs(query, keep_blank_values=True)
    return params


# Example:
qs = "name=John&tags=python&tags=web&empty="
parsed = parse_query_string(qs)
# {'name': ['John'], 'tags': ['python', 'web'], 'empty': ['']}
```

---

## 5.2 Static Route Matching

### The Simplest Router

```python
from typing import Callable, Dict, Tuple, Optional
from dataclasses import dataclass


Handler = Callable  # Will be more specific later


@dataclass
class Route:
    """A registered route."""
    method: str
    path: str
    handler: Handler


class SimpleRouter:
    """
    Static route matching using dictionary lookup.
    O(1) lookup, but no dynamic segments.
    """

    def __init__(self):
        # Key: (method, path), Value: handler
        self.routes: Dict[Tuple[str, str], Handler] = {}

    def add_route(self, method: str, path: str, handler: Handler) -> None:
        """Register a route."""
        key = (method.upper(), normalize_path(path))
        if key in self.routes:
            raise ValueError(f"Route already exists: {method} {path}")
        self.routes[key] = handler

    def match(self, method: str, path: str) -> Optional[Handler]:
        """Find handler for request."""
        key = (method.upper(), normalize_path(path))
        return self.routes.get(key)

    # Convenience decorators
    def route(self, method: str, path: str):
        def decorator(handler: Handler):
            self.add_route(method, path, handler)
            return handler
        return decorator

    def get(self, path: str):
        return self.route('GET', path)

    def post(self, path: str):
        return self.route('POST', path)
```

### Limitations

- No dynamic segments: `/users/123` won't match `/users/{id}`
- No wildcards: `/static/*` won't match `/static/css/style.css`
- No regex patterns

---

## 5.3 Dynamic Route Matching

### Path Parameters

Most web frameworks support path parameters:

```
Pattern:   /users/{id}/posts/{post_id}
Request:   /users/123/posts/456
Extracted: {id: "123", post_id: "456"}
```

### Regex-Based Implementation

```python
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class RouteMatch:
    """Result of a successful route match."""
    handler: Any
    path_params: Dict[str, str] = field(default_factory=dict)


@dataclass
class CompiledRoute:
    """A route compiled to regex for matching."""
    method: str
    pattern: str           # Original pattern like /users/{id}
    regex: re.Pattern      # Compiled regex
    param_names: List[str] # ['id'] - parameter names in order
    handler: Any


class RegexRouter:
    """
    Dynamic route matching using regex.
    Supports {param} syntax for path parameters.
    """

    # Pattern to find {param} or {param:pattern} in route
    PARAM_PATTERN = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^}]+))?\}')

    def __init__(self):
        self.routes: List[CompiledRoute] = []

    def add_route(self, method: str, pattern: str, handler: Any) -> None:
        """
        Register a route with optional path parameters.

        Patterns:
        - /users              Static path
        - /users/{id}         Capture 'id' parameter
        - /users/{id:int}     Capture 'id' matching digits only (custom)
        - /files/{path:path}  Capture 'path' including slashes
        """
        method = method.upper()
        pattern = normalize_path(pattern)

        # Convert pattern to regex
        regex_pattern, param_names = self._compile_pattern(pattern)

        compiled = CompiledRoute(
            method=method,
            pattern=pattern,
            regex=re.compile(f'^{regex_pattern}$'),
            param_names=param_names,
            handler=handler
        )

        self.routes.append(compiled)

    def _compile_pattern(self, pattern: str) -> Tuple[str, List[str]]:
        """
        Convert route pattern to regex.

        /users/{id}/posts/{post_id}
        becomes: /users/(?P<id>[^/]+)/posts/(?P<post_id>[^/]+)
        """
        param_names = []
        regex_parts = []
        last_end = 0

        for match in self.PARAM_PATTERN.finditer(pattern):
            # Add literal part before this parameter
            literal = re.escape(pattern[last_end:match.start()])
            regex_parts.append(literal)

            # Extract parameter name and optional pattern
            param_name = match.group(1)
            param_pattern = match.group(2)

            param_names.append(param_name)

            # Determine regex for this parameter
            if param_pattern is None:
                # Default: match anything except /
                param_regex = '[^/]+'
            elif param_pattern == 'int':
                param_regex = r'\d+'
            elif param_pattern == 'path':
                # Match including slashes (for file paths)
                param_regex = '.+'
            elif param_pattern == 'uuid':
                param_regex = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
            else:
                # Custom regex
                param_regex = param_pattern

            regex_parts.append(f'(?P<{param_name}>{param_regex})')
            last_end = match.end()

        # Add remaining literal part
        regex_parts.append(re.escape(pattern[last_end:]))

        return ''.join(regex_parts), param_names

    def match(self, method: str, path: str) -> Optional[RouteMatch]:
        """Find matching route and extract path parameters."""
        method = method.upper()
        path = normalize_path(path)

        for route in self.routes:
            if route.method != method:
                continue

            match = route.regex.match(path)
            if match:
                params = {name: match.group(name) for name in route.param_names}
                return RouteMatch(handler=route.handler, path_params=params)

        return None

    # Decorators
    def route(self, method: str, pattern: str):
        def decorator(handler):
            self.add_route(method, pattern, handler)
            return handler
        return decorator

    def get(self, pattern: str):
        return self.route('GET', pattern)

    def post(self, pattern: str):
        return self.route('POST', pattern)


# Usage example
router = RegexRouter()

@router.get('/users')
def list_users(request):
    pass

@router.get('/users/{id:int}')
def get_user(request):
    pass

@router.get('/users/{id:int}/posts/{post_id}')
def get_user_post(request):
    pass

@router.get('/files/{filepath:path}')
def serve_file(request):
    pass

# Matching
match = router.match('GET', '/users/123')
print(match.path_params)  # {'id': '123'}

match = router.match('GET', '/users/123/posts/abc')
print(match.path_params)  # {'id': '123', 'post_id': 'abc'}

match = router.match('GET', '/files/static/css/style.css')
print(match.path_params)  # {'filepath': 'static/css/style.css'}
```

### Performance Considerations

Regex routing iterates through all routes: O(n) where n is number of routes.

For each route:
1. Check method: O(1)
2. Match regex: O(k) where k is path length

Total: O(n * k)

For most applications with < 100 routes, this is fine. For large APIs, we need something faster.

---

## 5.4 Trie-Based Routing (Radix Tree)

### Why a Trie?

A trie (prefix tree) allows O(k) lookups regardless of the number of routes:

```
Routes:
  /api/users
  /api/users/{id}
  /api/posts
  /api/posts/{id}
  /health

Trie structure:
                    [root]
                   /      \
                 api      health
                  |
            ┌─────┴─────┐
          users       posts
            |           |
          {id}        {id}
```

### Radix Tree Implementation

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


class NodeType(Enum):
    STATIC = 'static'       # Exact match: "users"
    PARAM = 'param'         # Parameter: "{id}"
    CATCHALL = 'catchall'   # Wildcard: "*" or "{path:path}"


@dataclass
class RouteNode:
    """Node in the radix tree."""
    # The path segment this node represents
    segment: str = ''
    node_type: NodeType = NodeType.STATIC

    # For PARAM nodes, the parameter name
    param_name: str = ''

    # Handler if this is a terminal node (method -> handler)
    handlers: Dict[str, Any] = field(default_factory=dict)

    # Child nodes (segment -> node)
    children: Dict[str, 'RouteNode'] = field(default_factory=dict)

    # Special children
    param_child: Optional['RouteNode'] = None
    catchall_child: Optional['RouteNode'] = None


class RadixRouter:
    """
    High-performance radix tree router.
    O(k) lookup where k is the number of path segments.
    """

    def __init__(self):
        self.root = RouteNode()

    def add_route(self, method: str, pattern: str, handler: Any) -> None:
        """Add a route to the tree."""
        method = method.upper()
        pattern = normalize_path(pattern)
        segments = self._split_path(pattern)

        node = self.root
        for segment in segments:
            node = self._insert_segment(node, segment)

        # Check for duplicate
        if method in node.handlers:
            raise ValueError(f"Route already exists: {method} {pattern}")

        node.handlers[method] = handler

    def _split_path(self, path: str) -> List[str]:
        """Split path into segments."""
        if path == '/':
            return []
        return [s for s in path.split('/') if s]

    def _insert_segment(self, parent: RouteNode, segment: str) -> RouteNode:
        """Insert a segment under parent, return the (new or existing) node."""

        # Check for parameter segment
        if segment.startswith('{') and segment.endswith('}'):
            # Parse parameter: {name} or {name:pattern}
            inner = segment[1:-1]
            if ':' in inner:
                param_name, param_type = inner.split(':', 1)
            else:
                param_name, param_type = inner, None

            # Catchall pattern (matches /)
            if param_type == 'path':
                if parent.catchall_child is None:
                    parent.catchall_child = RouteNode(
                        segment=segment,
                        node_type=NodeType.CATCHALL,
                        param_name=param_name
                    )
                return parent.catchall_child

            # Regular parameter
            if parent.param_child is None:
                parent.param_child = RouteNode(
                    segment=segment,
                    node_type=NodeType.PARAM,
                    param_name=param_name
                )
            return parent.param_child

        # Static segment
        if segment not in parent.children:
            parent.children[segment] = RouteNode(
                segment=segment,
                node_type=NodeType.STATIC
            )
        return parent.children[segment]

    def match(self, method: str, path: str) -> Optional[RouteMatch]:
        """Match a path and return handler + params."""
        method = method.upper()
        path = normalize_path(path)
        segments = self._split_path(path)

        params = {}
        node = self.root

        i = 0
        while i < len(segments):
            segment = segments[i]

            # Try static match first (highest priority)
            if segment in node.children:
                node = node.children[segment]
                i += 1
                continue

            # Try parameter match
            if node.param_child is not None:
                params[node.param_child.param_name] = segment
                node = node.param_child
                i += 1
                continue

            # Try catchall match (consumes rest of path)
            if node.catchall_child is not None:
                remaining = '/'.join(segments[i:])
                params[node.catchall_child.param_name] = remaining
                node = node.catchall_child
                i = len(segments)  # Consumed all
                continue

            # No match
            return None

        # Check if we have a handler for this method
        handler = node.handlers.get(method)
        if handler is None:
            # Check if any handlers exist (for 405 vs 404)
            if node.handlers:
                # Route exists but method not allowed
                return RouteMatch(handler=None, path_params=params)
            return None

        return RouteMatch(handler=handler, path_params=params)

    def get_allowed_methods(self, path: str) -> List[str]:
        """Get list of allowed methods for a path."""
        path = normalize_path(path)
        segments = self._split_path(path)

        node = self.root
        for segment in segments:
            if segment in node.children:
                node = node.children[segment]
            elif node.param_child:
                node = node.param_child
            elif node.catchall_child:
                node = node.catchall_child
                break
            else:
                return []

        return list(node.handlers.keys())

    # Decorators
    def route(self, method: str, pattern: str):
        def decorator(handler):
            self.add_route(method, pattern, handler)
            return handler
        return decorator

    def get(self, pattern: str):
        return self.route('GET', pattern)

    def post(self, pattern: str):
        return self.route('POST', pattern)

    def put(self, pattern: str):
        return self.route('PUT', pattern)

    def delete(self, pattern: str):
        return self.route('DELETE', pattern)
```

### Visualization

```python
def visualize_tree(node: RouteNode, prefix: str = '', is_last: bool = True) -> str:
    """Visualize the radix tree structure."""
    lines = []

    connector = '└── ' if is_last else '├── '
    lines.append(f"{prefix}{connector}{node.segment or '/'} "
                 f"({node.node_type.value})"
                 f"{' [' + ','.join(node.handlers.keys()) + ']' if node.handlers else ''}")

    prefix += '    ' if is_last else '│   '

    children = list(node.children.values())
    if node.param_child:
        children.append(node.param_child)
    if node.catchall_child:
        children.append(node.catchall_child)

    for i, child in enumerate(children):
        is_last_child = i == len(children) - 1
        lines.append(visualize_tree(child, prefix, is_last_child))

    return '\n'.join(lines)
```

---

## 5.5 Route Priority and Conflict Resolution

### The Problem

What happens when multiple routes could match?

```
Route 1: /users/{id}
Route 2: /users/me
Request: /users/me

Both match! Which should win?
```

### Priority Rules

Most frameworks use this priority order:

1. **Static segments** > **Parameters** > **Catchall**
2. **Longer paths** > **Shorter paths**
3. **First registered** (or explicit priority)

### Implementation with Priority

```python
@dataclass
class CompiledRoute:
    method: str
    pattern: str
    handler: Any
    priority: int  # Higher = more specific

    @staticmethod
    def calculate_priority(pattern: str) -> int:
        """
        Calculate priority based on pattern specificity.

        Static segments: +10 each
        Parameter segments: +5 each
        Catchall: +1
        """
        segments = [s for s in pattern.split('/') if s]
        priority = 0

        for segment in segments:
            if segment.startswith('{'):
                if ':path}' in segment:
                    priority += 1   # Catchall (lowest)
                else:
                    priority += 5   # Parameter
            else:
                priority += 10      # Static (highest)

        return priority


class PriorityRouter:
    """Router with priority-based matching."""

    def __init__(self):
        self.routes: List[CompiledRoute] = []
        self._sorted = True

    def add_route(self, method: str, pattern: str, handler: Any) -> None:
        route = CompiledRoute(
            method=method.upper(),
            pattern=normalize_path(pattern),
            handler=handler,
            priority=CompiledRoute.calculate_priority(pattern)
        )
        self.routes.append(route)
        self._sorted = False

    def _ensure_sorted(self):
        """Sort routes by priority (highest first)."""
        if not self._sorted:
            self.routes.sort(key=lambda r: r.priority, reverse=True)
            self._sorted = True

    def match(self, method: str, path: str) -> Optional[RouteMatch]:
        self._ensure_sorted()
        # ... matching logic with priority order
```

### Detecting Conflicts

```python
def detect_conflicts(routes: List[CompiledRoute]) -> List[Tuple[CompiledRoute, CompiledRoute]]:
    """Detect potentially ambiguous route pairs."""
    conflicts = []

    for i, route1 in enumerate(routes):
        for route2 in routes[i+1:]:
            if route1.method != route2.method:
                continue

            if routes_conflict(route1.pattern, route2.pattern):
                conflicts.append((route1, route2))

    return conflicts


def routes_conflict(pattern1: str, pattern2: str) -> bool:
    """Check if two patterns can match the same path."""
    # This is a simplified check
    # Full implementation would need to check all possible paths

    segs1 = [s for s in pattern1.split('/') if s]
    segs2 = [s for s in pattern2.split('/') if s]

    if len(segs1) != len(segs2):
        return False  # Different lengths can't conflict

    for s1, s2 in zip(segs1, segs2):
        is_param1 = s1.startswith('{')
        is_param2 = s2.startswith('{')

        if is_param1 and is_param2:
            continue  # Both params, could conflict
        if is_param1 or is_param2:
            continue  # One param matches anything
        if s1 != s2:
            return False  # Static segments differ

    return True
```

---

## 5.6 Method-Based Routing

### Multiple Methods, One Path

```python
class MethodRouter:
    """Route same path to different handlers based on method."""

    def __init__(self):
        # path -> method -> handler
        self.routes: Dict[str, Dict[str, Any]] = {}

    def add_route(self, method: str, path: str, handler: Any) -> None:
        path = normalize_path(path)
        if path not in self.routes:
            self.routes[path] = {}
        self.routes[path][method.upper()] = handler

    def match(self, method: str, path: str) -> Tuple[Optional[Any], List[str]]:
        """
        Returns (handler, allowed_methods).
        handler is None if method not allowed.
        allowed_methods is empty if path not found.
        """
        path = normalize_path(path)
        methods = self.routes.get(path)

        if methods is None:
            return None, []

        handler = methods.get(method.upper())
        allowed = list(methods.keys())

        return handler, allowed
```

### Automatic OPTIONS Handling

```python
def handle_options(self, request: HTTPRequest) -> HTTPResponse:
    """Auto-generate OPTIONS response."""
    _, allowed = self.match('OPTIONS', request.path)

    if not allowed:
        return Response.error(404)

    # Always include OPTIONS itself
    if 'OPTIONS' not in allowed:
        allowed.append('OPTIONS')

    return HTTPResponse(
        status_code=200,
        headers={
            'Allow': ', '.join(sorted(allowed)),
            'Content-Length': '0'
        }
    )
```

---

## 5.7 Route Groups and Prefixes

### The Problem

APIs often have shared prefixes:

```
/api/v1/users
/api/v1/users/{id}
/api/v1/posts
/api/v1/posts/{id}
```

Writing `/api/v1` repeatedly is tedious and error-prone.

### Route Groups

```python
from typing import Callable, List
from dataclasses import dataclass


@dataclass
class RouteDefinition:
    """Pending route to be registered."""
    method: str
    pattern: str
    handler: Callable


class RouteGroup:
    """
    Group routes under a common prefix.
    Can be nested for hierarchical APIs.
    """

    def __init__(self, prefix: str = ''):
        self.prefix = normalize_path(prefix) if prefix else ''
        self.routes: List[RouteDefinition] = []
        self.subgroups: List['RouteGroup'] = []

    def route(self, method: str, pattern: str):
        def decorator(handler):
            full_pattern = self.prefix + normalize_path(pattern)
            self.routes.append(RouteDefinition(method, full_pattern, handler))
            return handler
        return decorator

    def get(self, pattern: str):
        return self.route('GET', pattern)

    def post(self, pattern: str):
        return self.route('POST', pattern)

    def put(self, pattern: str):
        return self.route('PUT', pattern)

    def delete(self, pattern: str):
        return self.route('DELETE', pattern)

    def group(self, prefix: str) -> 'RouteGroup':
        """Create a nested group with additional prefix."""
        full_prefix = self.prefix + normalize_path(prefix)
        subgroup = RouteGroup(full_prefix)
        self.subgroups.append(subgroup)
        return subgroup

    def all_routes(self) -> List[RouteDefinition]:
        """Get all routes including subgroups."""
        routes = list(self.routes)
        for subgroup in self.subgroups:
            routes.extend(subgroup.all_routes())
        return routes


class Router:
    """Main router with group support."""

    def __init__(self):
        self.root_group = RouteGroup()
        self._radix = RadixRouter()
        self._built = False

    def _ensure_built(self):
        if not self._built:
            for route in self.root_group.all_routes():
                self._radix.add_route(route.method, route.pattern, route.handler)
            self._built = True

    def group(self, prefix: str) -> RouteGroup:
        return self.root_group.group(prefix)

    def get(self, pattern: str):
        return self.root_group.get(pattern)

    def post(self, pattern: str):
        return self.root_group.post(pattern)

    def match(self, method: str, path: str) -> Optional[RouteMatch]:
        self._ensure_built()
        return self._radix.match(method, path)


# Usage example:
router = Router()

# Root routes
@router.get('/')
def index(request):
    return Response.html("<h1>Home</h1>")

@router.get('/health')
def health(request):
    return Response.json({"status": "ok"})

# API v1 group
api_v1 = router.group('/api/v1')

@api_v1.get('/users')
def list_users(request):
    return Response.json({"users": []})

@api_v1.get('/users/{id}')
def get_user(request):
    return Response.json({"id": request.path_params['id']})

# Nested group
posts = api_v1.group('/posts')

@posts.get('')
def list_posts(request):
    return Response.json({"posts": []})

@posts.post('')
def create_post(request):
    return Response.json({"created": True})

# Registered routes:
# GET /
# GET /health
# GET /api/v1/users
# GET /api/v1/users/{id}
# GET /api/v1/posts
# POST /api/v1/posts
```

---

## 5.8 Complete Router Implementation

Here's a complete, production-ready router:

```python
"""
Complete Router Implementation

Features:
- Radix tree for O(k) lookups
- Path parameters with type hints
- Route groups with prefixes
- Method-based routing
- Priority-based conflict resolution
- Automatic OPTIONS handling
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
from urllib.parse import unquote


def normalize_path(path: str) -> str:
    """Normalize URL path."""
    path = unquote(path)
    segments = []
    for seg in path.split('/'):
        if seg == '..':
            if segments:
                segments.pop()
        elif seg and seg != '.':
            segments.append(seg)
    return '/' + '/'.join(segments)


@dataclass
class RouteMatch:
    """Result of route matching."""
    handler: Optional[Callable]
    path_params: Dict[str, str] = field(default_factory=dict)
    allowed_methods: List[str] = field(default_factory=list)


class NodeType(Enum):
    STATIC = 'static'
    PARAM = 'param'
    CATCHALL = 'catchall'


@dataclass
class TreeNode:
    """Node in radix tree."""
    segment: str = ''
    node_type: NodeType = NodeType.STATIC
    param_name: str = ''
    handlers: Dict[str, Callable] = field(default_factory=dict)
    children: Dict[str, TreeNode] = field(default_factory=dict)
    param_child: Optional[TreeNode] = None
    catchall_child: Optional[TreeNode] = None


class Router:
    """
    High-performance HTTP router.

    Usage:
        router = Router()

        @router.get('/users/{id}')
        def get_user(request):
            user_id = request.path_params['id']
            return Response.json({"id": user_id})

        # With groups
        api = router.group('/api/v1')

        @api.get('/posts')
        def list_posts(request):
            return Response.json({"posts": []})

        # Match requests
        match = router.match('GET', '/users/123')
        if match.handler:
            response = match.handler(request)
    """

    def __init__(self):
        self.root = TreeNode()
        self._groups: List[RouteGroup] = []

    def add_route(self, method: str, pattern: str, handler: Callable) -> None:
        """Register a route."""
        method = method.upper()
        pattern = normalize_path(pattern)
        segments = self._split_path(pattern)

        node = self.root
        for segment in segments:
            node = self._insert_node(node, segment)

        if method in node.handlers:
            raise ValueError(f"Duplicate route: {method} {pattern}")

        node.handlers[method] = handler

    def _split_path(self, path: str) -> List[str]:
        if path == '/':
            return []
        return [s for s in path.split('/') if s]

    def _insert_node(self, parent: TreeNode, segment: str) -> TreeNode:
        # Parameter segment: {name} or {name:type}
        if segment.startswith('{') and segment.endswith('}'):
            inner = segment[1:-1]
            name, ptype = (inner.split(':', 1) + [None])[:2]

            if ptype == 'path':
                if not parent.catchall_child:
                    parent.catchall_child = TreeNode(
                        segment=segment,
                        node_type=NodeType.CATCHALL,
                        param_name=name
                    )
                return parent.catchall_child

            if not parent.param_child:
                parent.param_child = TreeNode(
                    segment=segment,
                    node_type=NodeType.PARAM,
                    param_name=name
                )
            return parent.param_child

        # Static segment
        if segment not in parent.children:
            parent.children[segment] = TreeNode(
                segment=segment,
                node_type=NodeType.STATIC
            )
        return parent.children[segment]

    def match(self, method: str, path: str) -> RouteMatch:
        """Match request to handler."""
        method = method.upper()
        path = normalize_path(path)
        segments = self._split_path(path)

        params = {}
        node = self.root
        i = 0

        while i < len(segments):
            segment = segments[i]

            # Priority: static > param > catchall
            if segment in node.children:
                node = node.children[segment]
                i += 1
            elif node.param_child:
                params[node.param_child.param_name] = segment
                node = node.param_child
                i += 1
            elif node.catchall_child:
                params[node.catchall_child.param_name] = '/'.join(segments[i:])
                node = node.catchall_child
                i = len(segments)
            else:
                return RouteMatch(handler=None)

        allowed = list(node.handlers.keys())
        handler = node.handlers.get(method)

        return RouteMatch(
            handler=handler,
            path_params=params,
            allowed_methods=allowed
        )

    # Route group support
    def group(self, prefix: str) -> RouteGroup:
        """Create a route group with prefix."""
        group = RouteGroup(self, prefix)
        self._groups.append(group)
        return group

    # Decorator shortcuts
    def route(self, method: str, pattern: str):
        def decorator(handler: Callable):
            self.add_route(method, pattern, handler)
            return handler
        return decorator

    def get(self, pattern: str):
        return self.route('GET', pattern)

    def post(self, pattern: str):
        return self.route('POST', pattern)

    def put(self, pattern: str):
        return self.route('PUT', pattern)

    def delete(self, pattern: str):
        return self.route('DELETE', pattern)

    def patch(self, pattern: str):
        return self.route('PATCH', pattern)

    def options(self, pattern: str):
        return self.route('OPTIONS', pattern)


class RouteGroup:
    """Group routes under a common prefix."""

    def __init__(self, router: Router, prefix: str):
        self.router = router
        self.prefix = normalize_path(prefix) if prefix else ''

    def _full_path(self, pattern: str) -> str:
        if not pattern or pattern == '/':
            return self.prefix or '/'
        return self.prefix + normalize_path(pattern)

    def route(self, method: str, pattern: str):
        def decorator(handler: Callable):
            full = self._full_path(pattern)
            self.router.add_route(method, full, handler)
            return handler
        return decorator

    def get(self, pattern: str = ''):
        return self.route('GET', pattern)

    def post(self, pattern: str = ''):
        return self.route('POST', pattern)

    def put(self, pattern: str = ''):
        return self.route('PUT', pattern)

    def delete(self, pattern: str = ''):
        return self.route('DELETE', pattern)

    def group(self, prefix: str) -> RouteGroup:
        """Create nested group."""
        full_prefix = self._full_path(prefix)
        return RouteGroup(self.router, full_prefix)


# ============================================================================
# Integration with HTTP Server
# ============================================================================

def integrate_router(server_class):
    """Mixin or monkey-patch to add router to server."""

    original_init = server_class.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.router = Router()

    def dispatch(self, request):
        """Route request to handler."""
        match = self.router.match(request.method, request.path)

        if not match.handler:
            if match.allowed_methods:
                # 405 Method Not Allowed
                return HTTPResponse(
                    status_code=405,
                    headers={'Allow': ', '.join(match.allowed_methods)}
                )
            # 404 Not Found
            return Response.error(404)

        # Inject path params into request
        request.path_params = match.path_params

        return match.handler(request)

    server_class.__init__ = new_init
    server_class.dispatch = dispatch

    # Add routing decorators
    def get(self, pattern):
        return self.router.get(pattern)

    def post(self, pattern):
        return self.router.post(pattern)

    server_class.get = get
    server_class.post = post

    return server_class
```

---

## 5.9 Benchmarking

### Benchmark Script

```python
import time
from typing import Callable


def benchmark(name: str, func: Callable, iterations: int = 100000) -> float:
    """Benchmark a function."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    elapsed = time.perf_counter() - start
    per_op = (elapsed / iterations) * 1_000_000  # microseconds
    print(f"{name}: {per_op:.2f} μs/op ({iterations} iterations)")
    return per_op


# Compare routers
simple_router = SimpleRouter()
regex_router = RegexRouter()
radix_router = Router()

# Add same routes to each
patterns = [
    ('GET', '/'),
    ('GET', '/users'),
    ('GET', '/users/{id}'),
    ('GET', '/users/{id}/posts'),
    ('GET', '/users/{id}/posts/{post_id}'),
    ('POST', '/users'),
    ('PUT', '/users/{id}'),
    ('DELETE', '/users/{id}'),
]

for method, pattern in patterns:
    simple_router.add_route(method, pattern.replace('{id}', '123').replace('{post_id}', '456'), lambda r: None)
    regex_router.add_route(method, pattern, lambda r: None)
    radix_router.add_route(method, pattern, lambda r: None)

# Benchmark
print("\nStatic route (/):")
benchmark("Simple", lambda: simple_router.match('GET', '/'))
benchmark("Regex", lambda: regex_router.match('GET', '/'))
benchmark("Radix", lambda: radix_router.match('GET', '/'))

print("\nDynamic route (/users/123):")
benchmark("Regex", lambda: regex_router.match('GET', '/users/123'))
benchmark("Radix", lambda: radix_router.match('GET', '/users/123'))

print("\nDeep dynamic (/users/123/posts/456):")
benchmark("Regex", lambda: regex_router.match('GET', '/users/123/posts/456'))
benchmark("Radix", lambda: radix_router.match('GET', '/users/123/posts/456'))
```

### Expected Results

```
Static route (/):
Simple: 0.15 μs/op
Regex:  0.80 μs/op
Radix:  0.25 μs/op

Dynamic route (/users/123):
Regex:  1.50 μs/op
Radix:  0.40 μs/op

Deep dynamic (/users/123/posts/456):
Regex:  2.20 μs/op
Radix:  0.55 μs/op
```

The radix tree scales better with route complexity.

---

## 5.10 Lab: Build a High-Performance Router

### Requirements

Build a router that:

1. Uses radix tree for O(k) lookups
2. Supports path parameters: `/users/{id}`
3. Supports typed parameters: `/users/{id:int}`
4. Supports catchall: `/files/{path:path}`
5. Supports route groups with prefixes
6. Handles method-based routing
7. Returns 404 for unknown paths
8. Returns 405 for wrong methods (with Allow header)
9. Passes all unit tests

### Test Cases

```python
import unittest


class RouterTests(unittest.TestCase):

    def setUp(self):
        self.router = Router()

        @self.router.get('/')
        def index(r): return 'index'

        @self.router.get('/users')
        def users(r): return 'users'

        @self.router.get('/users/{id}')
        def user(r): return f'user:{r.path_params["id"]}'

        @self.router.post('/users')
        def create(r): return 'create'

        api = self.router.group('/api/v1')

        @api.get('/health')
        def health(r): return 'healthy'

    def test_static_route(self):
        match = self.router.match('GET', '/')
        self.assertIsNotNone(match.handler)

    def test_dynamic_route(self):
        match = self.router.match('GET', '/users/123')
        self.assertEqual(match.path_params['id'], '123')

    def test_method_routing(self):
        get_match = self.router.match('GET', '/users')
        post_match = self.router.match('POST', '/users')
        self.assertIsNotNone(get_match.handler)
        self.assertIsNotNone(post_match.handler)
        self.assertNotEqual(get_match.handler, post_match.handler)

    def test_not_found(self):
        match = self.router.match('GET', '/nonexistent')
        self.assertIsNone(match.handler)
        self.assertEqual(match.allowed_methods, [])

    def test_method_not_allowed(self):
        match = self.router.match('DELETE', '/users')
        self.assertIsNone(match.handler)
        self.assertIn('GET', match.allowed_methods)

    def test_group_prefix(self):
        match = self.router.match('GET', '/api/v1/health')
        self.assertIsNotNone(match.handler)

    def test_path_normalization(self):
        match = self.router.match('GET', '//users//123//')
        self.assertEqual(match.path_params.get('id'), '123')


if __name__ == '__main__':
    unittest.main()
```

---

## Exercises

### Exercise 5.1: Typed Parameters

Implement parameter type validation:

```python
@router.get('/users/{id:int}')
def get_user(request):
    # id should be validated as integer
    pass

@router.get('/posts/{slug:slug}')  # alphanumeric + hyphens
def get_post(request):
    pass
```

### Exercise 5.2: Optional Parameters

Implement optional path segments:

```python
@router.get('/files/{path:path}?')  # path is optional
def serve_files(request):
    path = request.path_params.get('path', 'index.html')
```

### Exercise 5.3: Route Constraints

Add constraints to routes:

```python
@router.get('/users/{id}', constraints={'id': r'\d+'})
def get_user(request):
    pass
```

### Exercise 5.4: Reverse Routing

Implement URL generation from route names:

```python
@router.get('/users/{id}', name='user.detail')
def get_user(request):
    pass

url = router.url_for('user.detail', id=123)
# Returns: '/users/123'
```

### Exercise 5.5: Route Middleware

Add per-route middleware support:

```python
def auth_required(handler):
    def wrapper(request):
        if not request.user:
            return Response.error(401)
        return handler(request)
    return wrapper

@router.get('/admin', middleware=[auth_required])
def admin(request):
    pass
```

---

## Deep Dive Questions

1. **Why do most frameworks prioritize static segments over parameters? What issues could arise if they didn't?**

2. **How would you implement route versioning (e.g., Accept-Version header)?**

3. **What's the memory trade-off between regex routing and radix tree routing?**

4. **How do frameworks like FastAPI extract type information from function signatures for automatic parameter conversion?**

5. **What are the security implications of route parameter parsing? (Hint: ReDoS)**

---

## Resources

### Framework Routers
- [Starlette Routing](https://github.com/encode/starlette/blob/master/starlette/routing.py)
- [Flask URL Routing](https://github.com/pallets/flask/blob/main/src/flask/sansio/blueprints.py)
- [FastAPI Router](https://github.com/tiangolo/fastapi/blob/master/fastapi/routing.py)

### Algorithms
- [Radix Tree (Wikipedia)](https://en.wikipedia.org/wiki/Radix_tree)
- [httprouter (Go)](https://github.com/julienschmidt/httprouter) — Fast radix tree router

### Papers
- "Fast and Scalable URL Routing" — Various benchmark comparisons

---

## Summary

You've built a complete routing system:

1. **URL Parsing** — Normalize and split paths correctly
2. **Static Matching** — O(1) dictionary lookup
3. **Dynamic Matching** — Regex-based with parameter extraction
4. **Radix Tree** — O(k) lookup for large route sets
5. **Route Priority** — Static > Parameter > Catchall
6. **Method Routing** — Same path, different handlers
7. **Route Groups** — Organize routes with shared prefixes
8. **Benchmarking** — Measure and compare performance

Your router now handles patterns like:
- `/users`
- `/users/{id}`
- `/users/{id:int}/posts/{post_id}`
- `/files/{path:path}`

In the next module, we'll handle what comes after routing: parsing request bodies in various formats.

---

## Next Module

**[Module 6: Request Body Handling →](./MODULE_06_REQUEST_BODY.md)**

We'll implement parsers for JSON, form data, multipart uploads, and streaming bodies.
