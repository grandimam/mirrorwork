# Written by Bohdan Shtepan <bohdan@shtepan.com>, February 2025

from lib.ledger import Account, Ledger
import pytest
from time import time
import threading

@pytest.mark.parametrize("num_threads, transfer_amount", [(5, 50)])
def test_concurrent_transfers(num_threads, transfer_amount):
    acc1 = Account(1, 1000)
    acc2 = Account(2, 1000)
    initial_total = acc1.get_balance() + acc2.get_balance()

    def transfer():
        Ledger.transfer_money(acc1, acc2, transfer_amount)

    threads = [threading.Thread(target=transfer) for _ in range(num_threads)]
    start_time = time()

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    end_time = time()
    final_total = acc1.get_balance() + acc2.get_balance()

    assert final_total == initial_total, "Total balance should remain constant"
    assert (end_time - start_time) < 5, "Potential deadlock detected"
