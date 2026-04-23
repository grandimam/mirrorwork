# Written by Bohdan Shtepan <bohdan@shtepan.com>, February 2025

from lib.ledger_lock_free import Account, Ledger
from decimal import Decimal
from threading import Thread
from time import time


def test_ledger_money_transfer_concurrency():
    acc1 = Account(1, Decimal(1000))
    acc2 = Account(2, Decimal(500))
    ledger = Ledger()
    initial_total = acc1.balance + acc2.balance
    num_threads = 20
    amount = Decimal(50)

    def transfer():
        ledger.transfer_money(acc1, acc2, amount)

    threads = [Thread(target=transfer) for _ in range(num_threads)]
    start_time = time()

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    ledger.transaction_queue.join()

    end_time = time()
    final_total = acc1.balance + acc2.balance

    assert initial_total == final_total
    assert end_time - start_time < 5
