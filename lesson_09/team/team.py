""" 
Course: CSE 351
Team  : 
File  : Week 9 team.py
Author:  Luc Comeau
"""

# Include CSE 351 common Python files. 
from cse351 import *
import time
import random
import multiprocessing as mp

# number of cleaning staff and hotel guests
CLEANING_STAFF = 2
HOTEL_GUESTS = 5

# Run program for this number of seconds
TIME = 60

STARTING_PARTY_MESSAGE =  'Turning on the lights for the party vvvvvvvvvvvvvv'
STOPPING_PARTY_MESSAGE  = 'Turning off the lights  ^^^^^^^^^^^^^^^^^^^^^^^^^^'

STARTING_CLEANING_MESSAGE =  'Starting to clean the room >>>>>>>>>>>>>>>>>>>>>>>>>>>>>'
STOPPING_CLEANING_MESSAGE  = 'Finish cleaning the room <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<'

def cleaner_waiting():
    time.sleep(random.uniform(0, 2))

def cleaner_cleaning(id):
    print(f'Cleaner: {id}')
    time.sleep(random.uniform(0, 2))

def guest_waiting():
    time.sleep(random.uniform(0, 2))

def guest_partying(id, count):
    print(f'Guest: {id}, count = {count}')
    time.sleep(random.uniform(0, 1))

def cleaner(id, start_time, room_lock, mutex, cleaned_count):
    """
    do the following for TIME seconds
        cleaner will wait to try to clean the room (cleaner_waiting())
        get access to the room
        display message STARTING_CLEANING_MESSAGE
        Take some time cleaning (cleaner_cleaning())
        display message STOPPING_CLEANING_MESSAGE
    """
    while time.time() - start_time < TIME:
        # Wait before attempting to clean
        cleaner_waiting()

        # Get exclusive access to the room
        room_lock.acquire()
        try:
            # Announce cleaning and update cleaned_count
            with mutex:
                print(STARTING_CLEANING_MESSAGE)
                cleaned_count.value += 1

            # Do the cleaning work
            cleaner_cleaning(id)

            # Announce cleaning finished
            with mutex:
                print(STOPPING_CLEANING_MESSAGE)
        finally:
            room_lock.release()

def guest(id, start_time, room_lock, mutex, guest_count, party_count):
    """
    do the following for TIME seconds
        guest will wait to try to get access to the room (guest_waiting())
        get access to the room
        display message STARTING_PARTY_MESSAGE if this guest is the first one in the room
        Take some time partying (call guest_partying())
        display message STOPPING_PARTY_MESSAGE if the guest is the last one leaving in the room
    """
    while time.time() - start_time < TIME:
        # Wait before attempting to enter the room
        guest_waiting()

        # --- ENTRY SECTION (readers–writers pattern) ---
        mutex.acquire()
        guest_count.value += 1
        first_guest = False
        if guest_count.value == 1:
            # First guest blocks cleaners by taking the room lock
            room_lock.acquire()
            first_guest = True
        current_count = guest_count.value
        mutex.release()

        # If we are the first guest, turn on the lights and count a new party
        if first_guest:
            with mutex:
                print(STARTING_PARTY_MESSAGE)
                party_count.value += 1

        # Party in the room
        guest_partying(id, current_count)

        # --- EXIT SECTION ---
        mutex.acquire()
        guest_count.value -= 1
        last_guest = (guest_count.value == 0)
        mutex.release()

        # If we are the last guest, turn off the lights and free the room
        if last_guest:
            with mutex:
                print(STOPPING_PARTY_MESSAGE)
            room_lock.release()

def main():
    # Start time of the running of the program.
    start_time = time.time()

    # Locks
    room_lock = mp.Lock()   # controls exclusive access to the room
    mutex = mp.Lock()       # protects shared counters (guest_count, cleaned_count, party_count)

    # Shared counters
    guest_count   = mp.Value('i', 0)  # number of guests currently in the room
    cleaned_count = mp.Value('i', 0)  # number of times cleaned
    party_count   = mp.Value('i', 0)  # number of parties

    processes = []

    # Create cleaner processes
    for cid in range(1, CLEANING_STAFF + 1):
        p = mp.Process(target=cleaner,
                       args=(cid, start_time, room_lock, mutex, cleaned_count))
        p.start()
        processes.append(p)

    # Create guest processes
    for gid in range(1, HOTEL_GUESTS + 1):
        p = mp.Process(target=guest,
                       args=(gid, start_time, room_lock, mutex, guest_count, party_count))
        p.start()
        processes.append(p)

    # Wait for all processes to finish
    for p in processes:
        p.join()

    # Results
    print(f'Room was cleaned {cleaned_count.value} times, there were {party_count.value} parties')


if __name__ == '__main__':
    main()