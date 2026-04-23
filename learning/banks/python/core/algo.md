# Data Structures & Algorithm Complexity

## Data Structures

### Array / List

| Operation | Average | Worst |
|-----------|---------|-------|
| Access | O(1) | O(1) |
| Search | O(n) | O(n) |
| Insert (end) | O(1)* | O(n) |
| Insert (middle) | O(n) | O(n) |
| Delete (end) | O(1) | O(1) |
| Delete (middle) | O(n) | O(n) |

*amortized for dynamic arrays

### Linked List (Singly)

| Operation | Average | Worst |
|-----------|---------|-------|
| Access | O(n) | O(n) |
| Search | O(n) | O(n) |
| Insert (head) | O(1) | O(1) |
| Insert (tail) | O(n) | O(n) |
| Delete (head) | O(1) | O(1) |
| Delete (tail) | O(n) | O(n) |

### Doubly Linked List

| Operation | Average | Worst |
|-----------|---------|-------|
| Access | O(n) | O(n) |
| Search | O(n) | O(n) |
| Insert (head/tail) | O(1) | O(1) |
| Delete (given node) | O(1) | O(1) |
| Delete (by value) | O(n) | O(n) |

### Stack

| Operation | Average | Worst |
|-----------|---------|-------|
| Push | O(1) | O(1) |
| Pop | O(1) | O(1) |
| Peek | O(1) | O(1) |
| Search | O(n) | O(n) |

### Queue

| Operation | Average | Worst |
|-----------|---------|-------|
| Enqueue | O(1) | O(1) |
| Dequeue | O(1) | O(1) |
| Peek | O(1) | O(1) |
| Search | O(n) | O(n) |

### Hash Table / Dict

| Operation | Average | Worst |
|-----------|---------|-------|
| Access | O(1) | O(n) |
| Search | O(1) | O(n) |
| Insert | O(1) | O(n) |
| Delete | O(1) | O(n) |

Space: O(n)

### Set (Hash Set)

| Operation | Average | Worst |
|-----------|---------|-------|
| Add | O(1) | O(n) |
| Remove | O(1) | O(n) |
| Contains | O(1) | O(n) |
| Union | O(m+n) | O(m+n) |
| Intersection | O(min(m,n)) | O(m*n) |

### Binary Search Tree (BST)

| Operation | Average | Worst (unbalanced) |
|-----------|---------|---------------------|
| Access | O(log n) | O(n) |
| Search | O(log n) | O(n) |
| Insert | O(log n) | O(n) |
| Delete | O(log n) | O(n) |

### Balanced BST (AVL / Red-Black Tree)

| Operation | Average | Worst |
|-----------|---------|-------|
| Access | O(log n) | O(log n) |
| Search | O(log n) | O(log n) |
| Insert | O(log n) | O(log n) |
| Delete | O(log n) | O(log n) |

### Heap (Min/Max) — Binary Heap

| Operation | Average | Worst |
|-----------|---------|-------|
| Find min/max | O(1) | O(1) |
| Insert | O(1)* | O(log n) |
| Extract min/max | O(log n) | O(log n) |
| Heapify (build) | O(n) | O(n) |

*amortized

### Trie (Prefix Tree)

| Operation | Complexity |
|-----------|-----------|
| Insert | O(m) |
| Search | O(m) |
| Delete | O(m) |
| Prefix search | O(m + k) |

m = key length, k = number of matches

### Graph (Adjacency List)

| Operation | Complexity |
|-----------|-----------|
| Add vertex | O(1) |
| Add edge | O(1) |
| Remove vertex | O(V + E) |
| Remove edge | O(E) |
| Query edge | O(V) |

Space: O(V + E)

### Graph (Adjacency Matrix)

| Operation | Complexity |
|-----------|-----------|
| Add vertex | O(V^2) |
| Add edge | O(1) |
| Remove edge | O(1) |
| Query edge | O(1) |

Space: O(V^2)

---

## Sorting Algorithms

| Algorithm | Best | Average | Worst | Space | Stable |
|-----------|------|---------|-------|-------|--------|
| Bubble Sort | O(n) | O(n^2) | O(n^2) | O(1) | Yes |
| Selection Sort | O(n^2) | O(n^2) | O(n^2) | O(1) | No |
| Insertion Sort | O(n) | O(n^2) | O(n^2) | O(1) | Yes |
| Merge Sort | O(n log n) | O(n log n) | O(n log n) | O(n) | Yes |
| Quick Sort | O(n log n) | O(n log n) | O(n^2) | O(log n) | No |
| Heap Sort | O(n log n) | O(n log n) | O(n log n) | O(1) | No |
| Tim Sort | O(n) | O(n log n) | O(n log n) | O(n) | Yes |
| Counting Sort | O(n + k) | O(n + k) | O(n + k) | O(k) | Yes |
| Radix Sort | O(nk) | O(nk) | O(nk) | O(n + k) | Yes |
| Bucket Sort | O(n + k) | O(n + k) | O(n^2) | O(n) | Yes |

k = range of input values

---

## Searching Algorithms

| Algorithm | Best | Average | Worst | Space |
|-----------|------|---------|-------|-------|
| Linear Search | O(1) | O(n) | O(n) | O(1) |
| Binary Search | O(1) | O(log n) | O(log n) | O(1) |
| Jump Search | O(1) | O(sqrt(n)) | O(sqrt(n)) | O(1) |
| Interpolation Search | O(1) | O(log log n) | O(n) | O(1) |
| Exponential Search | O(1) | O(log n) | O(log n) | O(1) |

---

## Graph Algorithms

| Algorithm | Time | Space | Notes |
|-----------|------|-------|-------|
| BFS | O(V + E) | O(V) | shortest path (unweighted) |
| DFS | O(V + E) | O(V) | topological sort, cycle detection |
| Dijkstra | O((V + E) log V) | O(V) | shortest path (non-negative weights) |
| Bellman-Ford | O(VE) | O(V) | shortest path (handles negative weights) |
| Floyd-Warshall | O(V^3) | O(V^2) | all-pairs shortest path |
| A* | O(E) | O(V) | heuristic-based shortest path |
| Kruskal's | O(E log E) | O(V) | MST (edge-based) |
| Prim's | O((V + E) log V) | O(V) | MST (vertex-based) |
| Topological Sort | O(V + E) | O(V) | DAG ordering |
| Tarjan's SCC | O(V + E) | O(V) | strongly connected components |
| Kosaraju's SCC | O(V + E) | O(V) | strongly connected components |

---

## Dynamic Programming Patterns

| Pattern | Example Problems | Complexity (typical) |
|---------|-----------------|---------------------|
| 0/1 Knapsack | subset sum, partition equal | O(n * W) |
| Unbounded Knapsack | coin change, rod cutting | O(n * W) |
| LCS | longest common subsequence | O(m * n) |
| LIS | longest increasing subsequence | O(n log n) |
| Matrix Chain | optimal parenthesization | O(n^3) |
| Interval DP | burst balloons, palindrome partition | O(n^2) to O(n^3) |
| Tree DP | max path sum, house robber III | O(n) |
| Bitmask DP | TSP, assignment problem | O(2^n * n) |
| Digit DP | count numbers with property | O(digits * state) |

---

## String Algorithms

| Algorithm | Time | Space | Use Case |
|-----------|------|-------|----------|
| KMP | O(n + m) | O(m) | pattern matching |
| Rabin-Karp | O(n + m) avg | O(1) | pattern matching (multiple) |
| Z-Algorithm | O(n + m) | O(n + m) | pattern matching |
| Manacher's | O(n) | O(n) | longest palindromic substring |
| Suffix Array | O(n log n) | O(n) | substring queries |
| Trie | O(m) per op | O(alphabet * m * n) | prefix operations |

n = text length, m = pattern length

---

## Space Complexity Summary

| Structure | Space |
|-----------|-------|
| Array | O(n) |
| Linked List | O(n) |
| Hash Table | O(n) |
| BST | O(n) |
| Heap | O(n) |
| Trie | O(alphabet * m * n) |
| Adjacency List | O(V + E) |
| Adjacency Matrix | O(V^2) |
