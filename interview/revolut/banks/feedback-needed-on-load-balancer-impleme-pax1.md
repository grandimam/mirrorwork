# Interview Post: Feedback Needed on Load Balancer Implementation for Revolut Senior Engineer Role

**Source:** LeetCode Discuss  
**URL:** https://leetcode.com/discuss/post/5670371/feedback-needed-on-load-balancer-impleme-pax1/  
**Posted by:** Anonymous User  
**Date:** Aug 21, 2024 (last edited Aug 23, 2024)  
**Views:** 1,400  
**Tags:** Revolut, Interview

---

## Context / Interview Prompt

> I recently interviewed for a **Senior Software Engineer** role at **Revolut** and was asked to implement **production-ready code for a load balancer** with a maximum of 10 servers. I was rejected after this round and was advised to ensure the code is production-ready. Could someone provide feedback on what might be missing or need improvement to make the code production-ready? Any insights would be greatly appreciated!

**The task in one line:** Implement a production-ready Load Balancer in Java that supports a maximum of 10 servers.

---

## Code Submitted

### File 1 — `LoadBalancer.java`

```java
// LoadBalancer.java
package com.example;

import java.util.List;
import java.util.ArrayList;

public class LoadBalancer {
    private List<Server> servers;
    private static final int MAX_COUNT = 10;

    public LoadBalancer() {
        servers = new ArrayList<>();
    }

    public String addInstance(Server server) {
        synchronized (this) {
            if (this.servers.size() >= MAX_COUNT || servers.contains(server)) {
                return "We can't add the server";
            } else {
                servers.add(server);
                return "Successfully added";
            }
        }
    }

    public List<Server> getServerList() {
        return new ArrayList<>(servers);
    }
}
```

### File 2 — `Server.java`

```java
// Server.java
package com.example;

public class Server {
    private String id;
    private String address;

    public Server(String id, String address) {
        this.id = id;
        this.address = address;
    }

    private String getId() {
        return id;
    }

    private String getAddress() {
        return address;
    }

    @Override
    public String toString() {
        return "Server [id=" + id + ", address=" + address + "]";
    }

    @Override
    public int hashCode() {
        return (address == null) ? 0 : address.hashCode();
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (obj == null || getClass() != obj.getClass()) return false;
        Server other = (Server) obj;
        return (address == null) ? other.address == null : address.equals(other.address);
    }
}
```

### File 3 — `LoadBalancerTest.java`

```java
// LoadBalancerTest.java
package com.example;

import java.util.List;
import org.junit.Assert;
import org.junit.Test;

public class LoadBalancerTest {

    @Test
    public void testAddInstance() {
        Server server = new Server("1", "localhost:8080");
        LoadBalancer loadBalancer = new LoadBalancer();
        Assert.assertEquals(0, loadBalancer.getServerList().size());
        Assert.assertEquals("Successfully added", loadBalancer.addInstance(server));
        Assert.assertEquals(1, loadBalancer.getServerList().size());
    }

    @Test
    public void testLoadBalancerSize() {
        LoadBalancer loadBalancer = new LoadBalancer();
        for (int i = 0; i < 10; i++) {
            Server server = new Server(String.valueOf(i), "localhost:808" + i);
            loadBalancer.addInstance(server);
        }
        Assert.assertEquals(10, loadBalancer.getServerList().size());
    }

    @Test
    public void testAddEqualServer() {
        Server server1 = new Server("1", "localhost:8080");
        Server server2 = new Server("2", "localhost:8080"); // same address, different id
        LoadBalancer loadBalancer = new LoadBalancer();
        loadBalancer.addInstance(server1);
        loadBalancer.addInstance(server2);
        Assert.assertEquals(1, loadBalancer.getServerList().size());
    }
}
```

---

## Community Feedback (5 Comments)

### Comment 1 — Ayub (Nov 20, 2024)

> "Bro at least its wrong to return String in register function. It's hard to test this code. You should throw an exception or return a boolean..."

**Takeaway:** `addInstance()` returns a `String` ("Successfully added" / "We can't add the server"). This is poor API design. A production-ready method should either throw a meaningful exception (e.g., `IllegalStateException`) or return a `boolean`. Returning arbitrary strings makes the API fragile and hard to test reliably.

---

### Comment 2 — Anonymous (Oct 6, 2024)

> "I found a related article. Might be helpful."  
> https://medium.com/@majnun.abdurahmanov/the-strategy-design-pattern-bfa68d30d54a

**Takeaway:** Points to the **Strategy Design Pattern** as the right design approach. A production load balancer should have a pluggable balancing algorithm (round-robin, random, least-connections, etc.) behind an interface, not hard-coded logic.

---

### Comment 3 — harsh2328 (Aug 22, 2024)

> "You need to have a getServer() method and some strategy to actually balance the load?"

**Takeaway:** The most fundamental gap — there is **no `getServer()` method** at all. A load balancer's entire purpose is to select a server for an incoming request. Without this method, the class does not actually function as a load balancer.

---

### Comment 4 — Rajesh Kumar (Jan 20, 2026)

> "Here are a few things that you need to consider, as the interview asked for production-ready code..."

Specific issues listed:

1. **No `getServer()` method** — This is the core functionality of the task. There is no way to actually route a request to a server.
2. **No `deRegister()` method** — Servers need to be removed from the pool (e.g., when they go down or are scaled in). This is completely missing.
3. **No correctness tests** — The tests only cover server registration. There are no tests that verify the load balancing behavior itself.
4. **No thread-safety tests** — `synchronized` is used but there are zero concurrency tests to validate that the implementation is actually thread-safe under concurrent access.

> **Summary (in their words):** "You have missed the core functionality of the load balancer."

---

### Comment 5 — veinhorn (Jan 17, 2025)

> "Maybe they expected you to make it more extensible by following SOLID principles or use more advanced design patterns..."

**Takeaway:** For a **Senior Engineer** role, Revolut likely expected adherence to **SOLID principles** — specifically, an interface for `LoadBalancingStrategy`, dependency injection of the strategy, and an overall extensible, maintainable design rather than a single monolithic class.

---

## What Was Missing — Full Gap Analysis

| Gap                                        | Detail                                                                               |
| ------------------------------------------ | ------------------------------------------------------------------------------------ |
| No `getServer()` method                    | The core feature — selecting a server for an incoming request — is completely absent |
| No load balancing strategy                 | No round-robin, random, least-connections, or pluggable strategy pattern             |
| No `deRegister()` method                   | No way to remove a server from the pool                                              |
| Poor return type on `addInstance()`        | Returns `String` instead of throwing an exception or returning `boolean`             |
| No thread-safety tests                     | `synchronized` is used but never validated under concurrency                         |
| No correctness tests for balancing         | Tests only cover registration, not actual load distribution behavior                 |
| Not SOLID / not extensible                 | No interface, no strategy abstraction — not production-grade for a Senior role       |
| `getId()` and `getAddress()` are `private` | These should be `public` so the load balancer can actually use server metadata       |

---

## Key Lesson

For a **"production-ready" coding task at a Senior Engineer level**, the interviewer expects:

- **Full feature set:** register, deregister, and `getServer()` with a real balancing strategy
- **Proper error handling:** exceptions or booleans, not magic strings
- **Concurrency correctness:** `synchronized` or `ReentrantReadWriteLock`, and tests that prove it
- **Extensible design:** Strategy Pattern + SOLID principles (open for extension, closed for modification)
- **Meaningful tests:** covering correctness of load distribution, edge cases, and thread safety — not just happy-path registration
