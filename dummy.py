from cse351 import *
import threading

mutex = threading.Lock()

def print_cool_stuff(mutex):
    with mutex:
        # critical section
        print("cool stuff- Samantha")

t = threading.Thread(target=print_cool_stuff, args=(mutex,))
t.start()
mutex.acquire()
# critical section
print("hello world")

t.join()