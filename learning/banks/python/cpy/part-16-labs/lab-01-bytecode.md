# Lab 1: Bytecode Explorer

## Objective

Build a bytecode analysis tool that disassembles Python functions and visualizes execution flow.

## Prerequisites

- Understanding of Python bytecode (Part 2)
- Basic knowledge of the `dis` module

## Lab Setup

```python
# lab01_bytecode_explorer.py
import dis
import sys
import types
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class Instruction:
    """Represents a single bytecode instruction."""
    offset: int
    opname: str
    opcode: int
    arg: Optional[int]
    argval: any
    is_jump_target: bool

    def __str__(self):
        if self.arg is not None:
            return f"{self.offset:4d} {self.opname:<20} {self.arg:5d} ({self.argval})"
        return f"{self.offset:4d} {self.opname:<20}"
```

## Exercise 1: Basic Disassembler

Implement a function to extract bytecode instructions:

```python
def disassemble(func) -> List[Instruction]:
    """
    Disassemble a function and return list of Instructions.

    TODO: Implement this function using dis.get_instructions()
    """
    instructions = []

    # Your code here
    for instr in dis.get_instructions(func):
        instructions.append(Instruction(
            offset=instr.offset,
            opname=instr.opname,
            opcode=instr.opcode,
            arg=instr.arg,
            argval=instr.argval,
            is_jump_target=instr.is_jump_target
        ))

    return instructions

# Test
def example_func(x, y):
    if x > y:
        return x
    return y

instructions = disassemble(example_func)
for instr in instructions:
    print(instr)
```

## Exercise 2: Control Flow Graph

Build a control flow graph from bytecode:

```python
@dataclass
class BasicBlock:
    """A basic block in the control flow graph."""
    start_offset: int
    instructions: List[Instruction]
    successors: List[int]  # Offsets of successor blocks

class ControlFlowGraph:
    """Control flow graph for a function."""

    def __init__(self, func):
        self.func = func
        self.blocks: Dict[int, BasicBlock] = {}
        self._build()

    def _build(self):
        """
        TODO: Build the CFG by:
        1. Finding block boundaries (jump targets and after jumps)
        2. Creating BasicBlock objects
        3. Connecting successors
        """
        instructions = list(dis.get_instructions(self.func))

        # Find block starts
        block_starts = {0}
        for i, instr in enumerate(instructions):
            if instr.is_jump_target:
                block_starts.add(instr.offset)
            if 'JUMP' in instr.opname or instr.opname == 'RETURN_VALUE':
                if i + 1 < len(instructions):
                    block_starts.add(instructions[i + 1].offset)

        # Create blocks
        sorted_starts = sorted(block_starts)
        for i, start in enumerate(sorted_starts):
            end = sorted_starts[i + 1] if i + 1 < len(sorted_starts) else float('inf')

            block_instrs = [
                Instruction(
                    offset=instr.offset,
                    opname=instr.opname,
                    opcode=instr.opcode,
                    arg=instr.arg,
                    argval=instr.argval,
                    is_jump_target=instr.is_jump_target
                )
                for instr in instructions
                if start <= instr.offset < end
            ]

            if block_instrs:
                self.blocks[start] = BasicBlock(
                    start_offset=start,
                    instructions=block_instrs,
                    successors=[]
                )

        # Connect successors
        self._connect_successors()

    def _connect_successors(self):
        """Connect blocks based on control flow."""
        sorted_offsets = sorted(self.blocks.keys())

        for i, offset in enumerate(sorted_offsets):
            block = self.blocks[offset]
            if not block.instructions:
                continue

            last_instr = block.instructions[-1]

            # Handle different instruction types
            if last_instr.opname == 'RETURN_VALUE':
                pass  # No successors
            elif 'JUMP_FORWARD' in last_instr.opname or 'JUMP_BACKWARD' in last_instr.opname:
                if last_instr.argval in self.blocks:
                    block.successors.append(last_instr.argval)
            elif 'JUMP' in last_instr.opname:  # Conditional jump
                if last_instr.argval in self.blocks:
                    block.successors.append(last_instr.argval)
                if i + 1 < len(sorted_offsets):
                    block.successors.append(sorted_offsets[i + 1])
            else:
                if i + 1 < len(sorted_offsets):
                    block.successors.append(sorted_offsets[i + 1])

    def visualize(self):
        """Print ASCII visualization of CFG."""
        print("Control Flow Graph:")
        print("=" * 50)

        for offset in sorted(self.blocks.keys()):
            block = self.blocks[offset]
            print(f"\nBlock at offset {offset}:")
            print("-" * 30)
            for instr in block.instructions:
                print(f"  {instr}")
            if block.successors:
                print(f"  -> Successors: {block.successors}")
            print()

# Test
def test_func(n):
    total = 0
    for i in range(n):
        if i % 2 == 0:
            total += i
    return total

cfg = ControlFlowGraph(test_func)
cfg.visualize()
```

## Exercise 3: Stack Simulator

Simulate the evaluation stack:

```python
class StackSimulator:
    """Simulates Python's evaluation stack."""

    def __init__(self):
        self.stack = []
        self.trace = []

    def push(self, value):
        self.stack.append(value)
        self.trace.append(f"PUSH {value} -> {self.stack[:]}")

    def pop(self):
        value = self.stack.pop()
        self.trace.append(f"POP {value} <- {self.stack[:]}")
        return value

    def peek(self, n=0):
        return self.stack[-(n+1)]

    def simulate_instruction(self, instr: Instruction):
        """
        TODO: Simulate common instructions.
        Handle: LOAD_CONST, LOAD_FAST, STORE_FAST,
                BINARY_ADD, BINARY_SUBTRACT, COMPARE_OP,
                POP_TOP, RETURN_VALUE
        """
        op = instr.opname

        if op == 'LOAD_CONST':
            self.push(f"const:{instr.argval}")
        elif op == 'LOAD_FAST':
            self.push(f"local:{instr.argval}")
        elif op == 'STORE_FAST':
            value = self.pop()
            self.trace.append(f"STORE {instr.argval} = {value}")
        elif op in ('BINARY_ADD', 'BINARY_OP') and 'ADD' in str(instr.argval):
            right = self.pop()
            left = self.pop()
            self.push(f"({left} + {right})")
        elif op == 'BINARY_SUBTRACT' or (op == 'BINARY_OP' and 'SUB' in str(instr.argval)):
            right = self.pop()
            left = self.pop()
            self.push(f"({left} - {right})")
        elif op == 'COMPARE_OP':
            right = self.pop()
            left = self.pop()
            self.push(f"({left} {instr.argval} {right})")
        elif op == 'POP_TOP':
            self.pop()
        elif op == 'RETURN_VALUE':
            value = self.pop()
            self.trace.append(f"RETURN {value}")
        elif op == 'RESUME':
            pass  # No stack effect
        elif op == 'POP_JUMP_IF_FALSE' or op == 'POP_JUMP_IF_TRUE':
            self.pop()
        else:
            self.trace.append(f"UNHANDLED: {op}")

    def simulate(self, func):
        """Simulate execution of a function's bytecode."""
        for instr in dis.get_instructions(func):
            self.simulate_instruction(Instruction(
                offset=instr.offset,
                opname=instr.opname,
                opcode=instr.opcode,
                arg=instr.arg,
                argval=instr.argval,
                is_jump_target=instr.is_jump_target
            ))

        print("Stack Simulation Trace:")
        for line in self.trace:
            print(f"  {line}")

# Test
def add(a, b):
    return a + b

sim = StackSimulator()
sim.simulate(add)
```

## Exercise 4: Bytecode Optimizer

Implement simple peephole optimizations:

```python
class BytecodeOptimizer:
    """Simple bytecode optimizer."""

    def __init__(self, instructions: List[Instruction]):
        self.instructions = instructions
        self.optimizations_applied = []

    def optimize(self) -> List[Instruction]:
        """Apply all optimizations."""
        self.constant_folding()
        self.dead_code_elimination()
        return self.instructions

    def constant_folding(self):
        """
        TODO: Fold constant expressions.
        Example: LOAD_CONST 2, LOAD_CONST 3, BINARY_ADD
                 -> LOAD_CONST 5
        """
        i = 0
        while i < len(self.instructions) - 2:
            instr1 = self.instructions[i]
            instr2 = self.instructions[i + 1]
            instr3 = self.instructions[i + 2]

            if (instr1.opname == 'LOAD_CONST' and
                instr2.opname == 'LOAD_CONST' and
                instr3.opname == 'BINARY_ADD'):

                try:
                    result = instr1.argval + instr2.argval
                    # Replace with single LOAD_CONST
                    self.instructions[i] = Instruction(
                        offset=instr1.offset,
                        opname='LOAD_CONST',
                        opcode=instr1.opcode,
                        arg=None,
                        argval=result,
                        is_jump_target=instr1.is_jump_target
                    )
                    # Mark for removal
                    del self.instructions[i + 1:i + 3]
                    self.optimizations_applied.append(
                        f"Folded {instr1.argval} + {instr2.argval} = {result}"
                    )
                except:
                    pass
            i += 1

    def dead_code_elimination(self):
        """
        TODO: Remove code after unconditional jumps/returns.
        """
        i = 0
        while i < len(self.instructions):
            instr = self.instructions[i]

            if instr.opname == 'RETURN_VALUE':
                # Remove instructions until next jump target
                j = i + 1
                while j < len(self.instructions):
                    if self.instructions[j].is_jump_target:
                        break
                    j += 1

                if j > i + 1:
                    removed = self.instructions[i + 1:j]
                    del self.instructions[i + 1:j]
                    self.optimizations_applied.append(
                        f"Removed {len(removed)} dead instructions"
                    )
            i += 1

    def report(self):
        """Print optimization report."""
        print("Optimizations Applied:")
        for opt in self.optimizations_applied:
            print(f"  - {opt}")
```

## Challenge: Complete Bytecode Analyzer

Build a complete tool that:
1. Disassembles any function
2. Builds control flow graph
3. Simulates stack operations
4. Identifies potential optimizations

```python
class BytecodeAnalyzer:
    """Complete bytecode analysis tool."""

    def __init__(self, func):
        self.func = func
        self.code = func.__code__
        self.instructions = list(disassemble(func))
        self.cfg = ControlFlowGraph(func)

    def analyze(self):
        """Run complete analysis."""
        print(f"Analysis of: {self.func.__name__}")
        print("=" * 60)

        # Code object info
        print(f"\nCode Object Info:")
        print(f"  Argument count: {self.code.co_argcount}")
        print(f"  Local variables: {self.code.co_varnames}")
        print(f"  Constants: {self.code.co_consts}")
        print(f"  Stack size: {self.code.co_stacksize}")

        # Bytecode
        print(f"\nBytecode ({len(self.instructions)} instructions):")
        for instr in self.instructions:
            print(f"  {instr}")

        # CFG
        print(f"\nControl Flow Graph ({len(self.cfg.blocks)} blocks):")
        self.cfg.visualize()

        # Stack simulation
        print("\nStack Simulation:")
        sim = StackSimulator()
        sim.simulate(self.func)

# Final test
def complex_func(x, y, z):
    if x > 0:
        result = y + z
    else:
        result = y - z
    return result * 2

analyzer = BytecodeAnalyzer(complex_func)
analyzer.analyze()
```

## Expected Output

Running the complete analyzer should produce:
- Code object metadata
- Full bytecode listing
- Control flow graph with basic blocks
- Stack simulation trace

## Submission

1. Complete all TODO sections
2. Run analyzer on 3 different functions
3. Document any patterns you observe
4. Bonus: Add support for closures and nested functions

---

[Next: Lab 2 - Memory Profiler →](lab-02-memory-profiler.md)
