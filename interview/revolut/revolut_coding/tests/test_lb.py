# Written by Bohdan Shtepan <bohdan@shtepan.com>, February 2025

import pytest
from lib.lb import LoadBalancer, NoServersAvailableError, RoundRobinSelectionStrategy, RandomSelectionStrategy
from typing import List
from random import randint
from threading import Thread

@pytest.mark.parametrize('max_instances', [-1, 0])
def test_lb_init_raises(max_instances: int):
    with pytest.raises(ValueError):
        LoadBalancer(max_instances=max_instances)

@pytest.mark.parametrize('max_instances', [5, 10, 100])
def test_lb_init(max_instances: int):
    assert LoadBalancer(max_instances=max_instances)

@pytest.mark.parametrize('max_instances,servers,expected', [
    (5, ['server1'], [True]),
    (2, ['server1', 'server2', 'server3'], [True, True, False]),
    (5, ['server1', 'server2', 'server1'], [True, True, False]),
])
def test_lb_register(max_instances: int, servers: List[str], expected: List[bool]):
    lb = LoadBalancer(max_instances=max_instances)
    for server, want in zip(servers, expected):
        assert lb.register(server) == want

def test_lb_unregister():
    lb = LoadBalancer()
    assert not lb.unregister('server1')
    lb.register('server1')
    assert not lb.unregister('server2')
    assert lb.unregister('server1')


def test_lb_get():
    lb = LoadBalancer()
    with pytest.raises(NoServersAvailableError):
        lb.get()
    servers = ['server1', 'server2', 'server3']
    for server in servers:
        lb.register(server)
    assert lb.get() in servers


def test_no_deadlocks():
    lb = LoadBalancer()
    threads = []

    def register_and_unregister():
        for _ in range(1000):
            server = f"server{randint(1, 10)}"
            lb.register(server)
            lb.unregister(server)
            try:
                lb.get()
            except NoServersAvailableError:
                pass

    for _ in range(10):
        thread = Thread(target=register_and_unregister)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert True

def test_round_robin_strategy():
    round_robin_strategy = RoundRobinSelectionStrategy()
    lb = LoadBalancer(strategy=round_robin_strategy)
    servers = []
    servers_got = []

    for i in range(10):
        servers.append(f"server{i}")

    for server in servers:
        lb.register(server)

    for i in range(len(servers)):
        servers_got.append(lb.get())

    assert servers == servers_got

def test_random_strategy():
    random_strategy = RandomSelectionStrategy()
    lb = LoadBalancer(strategy=random_strategy)
    servers = set()

    for _ in range(20):
        server = f"server{randint(1, 10)}"

        servers.add(server)
        lb.register(server)

    for _ in range(10):
        assert lb.get() in servers

def test_random_strategy_equal_distribution():
    random_strategy = RandomSelectionStrategy()
    lb = LoadBalancer(strategy=random_strategy)
    servers = [f"server{i}" for i in range(10)]
    results = {server: 0 for server in servers}
    num_trials = 100000

    for server in servers:
        lb.register(server)

    for _ in range(num_trials):
        got = lb.get()
        results[got] += 1

    expected_freq = num_trials / len(servers)
    max_deviation = max(
        abs((freq - expected_freq) / expected_freq) for freq in results.values()
    )

    assert max_deviation < 0.5
