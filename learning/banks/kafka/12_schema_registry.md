# Chapter 12: Schema Registry

## Overview

Schema Registry provides schema management and compatibility enforcement for Kafka messages, enabling safe evolution of data formats over time.

## Learning Objectives

By the end of this chapter, you will:

- Understand schema evolution
- Use Avro/Protobuf with Kafka
- Configure compatibility modes
- Handle schema versioning

## Resources

| Resource | Time |
|----------|------|
| Read: https://docs.confluent.io/platform/current/schema-registry/index.html | 30 min |
| Hands-on: Set up Schema Registry, evolve schemas | 45 min |

## Core Concepts

### Why Schema Registry?

```
Without schema:
Producer sends: {"user_id": "123", "name": "Alice", "age": 30}
Consumer expects: {"userId": "123", "name": "Alice"}
Result: Parse error, field mismatch, runtime failures

With schema:
Producer: must conform to registered schema
Consumer: knows exact schema, can validate
Evolution: registry enforces compatibility rules
```

### How It Works

```
┌──────────────┐     Schema     ┌─────────────────┐
│   Producer   │ ──────────────►│ Schema Registry │
└──────┬───────┘   register     └────────┬────────┘
       │                                  │
       │ Message:                         │ Returns
       │ [schema_id][payload]             │ schema_id
       │                                  │
       ▼                                  │
┌──────────────┐                         │
│    Kafka     │                         │
└──────┬───────┘                         │
       │                                  │
       │                                  │
       ▼                                  │
┌──────────────┐     Get schema          │
│   Consumer   │ ◄───────────────────────┘
└──────────────┘     by schema_id
```

### Schema ID in Messages

```
Message format with Schema Registry:
┌─────────┬─────────────┬──────────────────┐
│ Magic   │ Schema ID   │ Payload          │
│ (1 byte)│ (4 bytes)   │ (serialized data)│
└─────────┴─────────────┴──────────────────┘

Magic byte: 0x00 (indicates schema registry format)
Schema ID: unique identifier for schema version
Payload: Avro/Protobuf/JSON encoded data
```

## Compatibility Modes

| Mode | Add Field | Remove Field | Use Case |
|------|-----------|--------------|----------|
| BACKWARD | Optional only | Any | Default. Consumers first |
| FORWARD | Any | Optional only | Producers first |
| FULL | Optional only | Optional only | Both directions |
| NONE | Any | Any | Development only |

### Backward Compatibility (Default)

```
Old schema:
{
  "name": "User",
  "fields": [
    {"name": "id", "type": "string"},
    {"name": "name", "type": "string"}
  ]
}

New schema (backward compatible):
{
  "name": "User",
  "fields": [
    {"name": "id", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "email", "type": ["null", "string"], "default": null}  // Optional
  ]
}

New consumers can read old messages (email=null)
```

### Forward Compatibility

```
Old schema:
{
  "name": "User",
  "fields": [
    {"name": "id", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "email", "type": "string"}
  ]
}

New schema (forward compatible):
{
  "name": "User",
  "fields": [
    {"name": "id", "type": "string"},
    {"name": "name", "type": "string"}
    // email removed
  ]
}

Old consumers can read new messages (ignore missing email)
```

## Key Questions to Understand

- Why not just use JSON?
- What's schema compatibility and why does it matter?
- How does the registry prevent breaking changes?

## Hands-On Exercises

### Exercise 1: Start Schema Registry

```bash
# Docker compose with Schema Registry
# docker-compose.yml
version: '3'
services:
  kafka:
    image: confluentinc/cp-kafka:latest
    # ... kafka config

  schema-registry:
    image: confluentinc/cp-schema-registry:latest
    ports:
      - "8081:8081"
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: kafka:9092

# Start
docker-compose up -d

# Test
curl http://localhost:8081/subjects
```

### Exercise 2: Register Schema

```bash
# Register Avro schema
curl -X POST -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{
    "schema": "{\"type\":\"record\",\"name\":\"User\",\"fields\":[{\"name\":\"id\",\"type\":\"string\"},{\"name\":\"name\",\"type\":\"string\"}]}"
  }' \
  http://localhost:8081/subjects/users-value/versions

# Get schema by ID
curl http://localhost:8081/schemas/ids/1

# Get latest schema for subject
curl http://localhost:8081/subjects/users-value/versions/latest

# List all subjects
curl http://localhost:8081/subjects
```

### Exercise 3: Python with Avro

```python
from confluent_kafka import Producer, Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer, AvroDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField

# Schema
user_schema = """
{
  "type": "record",
  "name": "User",
  "namespace": "com.example",
  "fields": [
    {"name": "id", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "email", "type": ["null", "string"], "default": null}
  ]
}
"""

# Schema Registry client
schema_registry = SchemaRegistryClient({'url': 'http://localhost:8081'})

# Serializer
avro_serializer = AvroSerializer(
    schema_registry,
    user_schema,
    lambda user, ctx: user  # Convert to dict
)

# Producer
producer = Producer({'bootstrap.servers': 'localhost:9092'})

def produce_user(user: dict):
    producer.produce(
        topic='users',
        key=user['id'].encode(),
        value=avro_serializer(
            user,
            SerializationContext('users', MessageField.VALUE)
        )
    )
    producer.flush()

# Produce
produce_user({'id': '1', 'name': 'Alice', 'email': 'alice@example.com'})
produce_user({'id': '2', 'name': 'Bob', 'email': None})
```

### Exercise 4: Consume with Schema

```python
# Deserializer
avro_deserializer = AvroDeserializer(
    schema_registry,
    user_schema,
    lambda user, ctx: user  # Keep as dict
)

# Consumer
consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'user-consumer',
    'auto.offset.reset': 'earliest',
})

consumer.subscribe(['users'])

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue

    user = avro_deserializer(
        msg.value(),
        SerializationContext('users', MessageField.VALUE)
    )
    print(f"User: {user}")
```

### Exercise 5: Schema Evolution

```python
# New schema with additional field
new_schema = """
{
  "type": "record",
  "name": "User",
  "namespace": "com.example",
  "fields": [
    {"name": "id", "type": "string"},
    {"name": "name", "type": "string"},
    {"name": "email", "type": ["null", "string"], "default": null},
    {"name": "phone", "type": ["null", "string"], "default": null}
  ]
}
"""

# Test compatibility before registering
curl -X POST -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"schema": "..."}' \
  http://localhost:8081/compatibility/subjects/users-value/versions/latest

# Register new version
new_serializer = AvroSerializer(schema_registry, new_schema)
```

## Schema Registry API

```bash
# Subjects
GET /subjects                           # List subjects
GET /subjects/{subject}/versions        # List versions
GET /subjects/{subject}/versions/{ver}  # Get specific version

# Schemas
GET /schemas/ids/{id}                   # Get by ID
POST /subjects/{subject}/versions       # Register new

# Compatibility
GET /config                             # Global compatibility
PUT /config                             # Set global compatibility
GET /config/{subject}                   # Subject compatibility
PUT /config/{subject}                   # Set subject compatibility
POST /compatibility/subjects/{subject}/versions/{ver}  # Test compatibility
```

## Protobuf Alternative

```python
from confluent_kafka.schema_registry.protobuf import ProtobufSerializer

# user.proto
# syntax = "proto3";
# message User {
#   string id = 1;
#   string name = 2;
#   optional string email = 3;
# }

from user_pb2 import User

serializer = ProtobufSerializer(
    User,
    schema_registry,
)

user = User(id='1', name='Alice', email='alice@example.com')
producer.produce('users', value=serializer(user, ctx))
```

## Interview Questions

- "Why use Schema Registry instead of just JSON?"
  - Not: "It's more efficient"
  - But: "Schema Registry enforces contracts between producers and consumers. Compatibility checks prevent breaking changes. Avro is more compact than JSON and has a schema for validation. Consumers know exactly what to expect."

- "How do you evolve schemas safely?"
  - "Use backward compatibility (default). Add new fields as optional with defaults. This lets new consumers read old messages and old consumers read new messages. Test compatibility before deployment."

- "What happens if compatibility check fails?"
  - "Schema Registry rejects the registration. Producer can't use the new schema. This prevents deploying breaking changes. We'd need to either make the schema compatible or create a new subject."

## Common Pitfalls

1. **Skipping compatibility checks** - Breaking consumers
2. **Required fields without defaults** - Not backward compatible
3. **Renaming fields** - Treated as remove + add
4. **Wrong subject naming** - Mismatch between topic and schema
5. **Not caching schemas** - Performance impact
