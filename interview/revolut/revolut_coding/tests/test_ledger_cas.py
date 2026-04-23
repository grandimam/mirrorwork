# Written by Bohdan Shtepan <bohdan@shtepan.com>, February 2025

from lib.ledger_cas import Account, Ledger
from threading import Thread
from time import time

def test_ledger_money_transfer_concurrency():
    acc1 = Account(1, 1000)
    acc2 = Account(2, 500)
    initial_total = acc1.get_balance() + acc2.get_balance()
    num_threads = 20
    amount = 50

    def transfer():
        Ledger.transfer_money(acc1, acc2, amount)

    threads = [Thread(target=transfer) for _ in range(num_threads)]
    start_time = time()

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    end_time = time()
    final_total = acc1.get_balance() + acc2.get_balance()

    assert initial_total == final_total
    assert end_time - start_time < 5
