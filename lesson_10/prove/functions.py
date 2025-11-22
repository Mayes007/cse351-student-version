"""
Course: CSE 351, week 10
File: functions.py
Author: Samantha Mayes

Instructions:

Depth First Search
https://www.youtube.com/watch?v=9RHO6jU--GU

Breadth First Search
https://www.youtube.com/watch?v=86g8jAQug04


Requesting a family from the server:
family_id = 6128784944
data = get_data_from_server('{TOP_API_URL}/family/{family_id}')

Example JSON returned from the server
{
    'id': 6128784944, 
    'husband_id': 2367673859,        # use with the Person API
    'wife_id': 2373686152,           # use with the Person API
    'children': [2380738417, 2185423094, 2192483455]    # use with the Person API
}

Requesting an individual from the server:
person_id = 2373686152
data = get_data_from_server('{TOP_API_URL}/person/{person_id}')

Example JSON returned from the server
{
    'id': 2373686152, 
    'name': 'Stella', 
    'birth': '9-3-1846', 
    'parent_id': 5428641880,   # use with the Family API
    'family_id': 6128784944    # use with the Family API
}


--------------------------------------------------------------------------------------
You will lose 10% if you don't detail your part 1 and part 2 code below

Describe how to speed up part 1

<Add your comments here>
For part 1 I would still use a rescursive depth first search over the family graph, but I would speed it up by:
-Feching the Family record once per family ID using a visited set
-For each family, fetching the husband, wife, and all children in parallel using multiple threads. Each thread calls the Person API for one person.
- Protecting the shared Tree object with a single lock when adding people and families so the dictionary updates are thread safe.
The recursion order is still DFS, I recurse from the a family to the parents of the husband and wife, but each family's people are retrieved concurrently so that multiple 0.25-second API calls overlap 
intead of happening one at a time.


Describe how to speed up part 2

<Add your comments here>
For part 2 (BFS) I implement a **breadth-first search** using a
`queue.Queue` of family IDs. I add the starting family to the queue, and
then run a pool of worker threads (for example, 20 workers). Each worker:
- Takes the next family ID from the queue.
- Calls the Family API, adds that Family to the Tree, then fetches the
  husband, wife, and all children (sequentially, but in parallel with
  other workers).
- Looks up the parents of the husband and wife and enqueues their
  parent family IDs if they haven’t been visited yet.
A shared `visited_families` set (with a lock) prevents duplicate work.
Using multiple workers means many families are being retrieved in
parallel, so many 0.25-second server calls overlap and the BFS finishes
much faster than a single-threaded version.


Extra (Optional) 10% Bonus to speed up part 3

<Add your comments here>
For the bonus BFS (limit 5) I use the same BFS + queue idea, but I
restrict the worker pool to **exactly 5 threads**. Each worker repeatedly
pops a family ID from the queue, fetches that family and its people, and
enqueues the parents for further processing. Because there are only 5
worker threads making API calls, the server never sees more than 5
active threads from this client, but the queue keeps those 5 workers
busy as long as there is more work to do.

"""
from common import *
import queue
import threading


def _fetch_family(family_id, tree, tree_lock):
    """
    Fetch a Family from the server and store it in the tree (if not already).
    Returns the Family object or None if not found.
    """
    if family_id is None or family_id == 0:
        return None

    # If we already have this family, return it directly.
    with tree_lock:
        if tree.does_family_exist(family_id):
            return tree.get_family(family_id)

    data = get_data_from_server(f'{TOP_API_URL}/family/{family_id}')
    if data is None:
        return None

    family = Family(data)

    with tree_lock:
        if not tree.does_family_exist(family.get_id()):
            tree.add_family(family)

    # print(f'Fetched family {family.get_id()}')   # helpful for debugging
    return family

def _fetch_person(person_id, tree, tree_lock):
    """
    Fetch a Person from the server and store it in the tree (if not already).
    Returns the Person object or None if not found.
    """
    if person_id is None or person_id == 0:
        return None

    # If we already have this person, return it directly.
    with tree_lock:
        if tree.does_person_exist(person_id):
            return tree.get_person(person_id)

    data = get_data_from_server(f'{TOP_API_URL}/person/{person_id}')
    if data is None:
        return None

    person = Person(data)

    with tree_lock:
        if not tree.does_person_exist(person.get_id()):
            tree.add_person(person)

    # print(f'Fetched person {person.get_id()}')   # helpful for debugging
    return person


def depth_fs_pedigree(family_id, tree):
    """
    Depth-first retrieval (recursive) using _fetch_family and _fetch_person.

    For each family:
      - fetch the Family from the server
      - fetch husband, wife, and all children (using threads so those API calls overlap)
      - then recursively go to the parents of the husband and wife (DFS).
    """
    tree_lock = threading.Lock()
    visited_families = set()

    def dfs(current_family_id):
        if current_family_id is None or current_family_id == 0:
            return

        # avoid re-processing the same family
        if current_family_id in visited_families:
            return
        visited_families.add(current_family_id)

        # get this family
        family = _fetch_family(current_family_id, tree, tree_lock)
        if family is None:
            return

        # collect all person ids in this family
        husband_id = family.get_husband()
        wife_id = family.get_wife()

        person_ids = []
        if husband_id is not None and husband_id != 0:
            person_ids.append(husband_id)
        if wife_id is not None and wife_id != 0:
            person_ids.append(wife_id)
        for child_id in family.get_children():
            if child_id is not None and child_id != 0:
                person_ids.append(child_id)

        # fetch all people for this family in parallel
        threads = []
        for pid in person_ids:
            t = threading.Thread(target=_fetch_person, args=(pid, tree, tree_lock))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # now recurse to parents (DFS)
        with tree_lock:
            husband = tree.get_person(husband_id) if husband_id else None
            wife = tree.get_person(wife_id) if wife_id else None

        parent_family_ids = []
        if husband is not None:
            parent_family_ids.append(husband.get_parentid())
        if wife is not None:
            parent_family_ids.append(wife.get_parentid())

        for pfid in parent_family_ids:
            if pfid is not None and pfid != 0:
                dfs(pfid)

    # kick off DFS from the starting family id
    dfs(family_id)
# -----------------------------------------------------------------------------
def breadth_fs_pedigree(family_id, tree):
    # KEEP this function even if you don't implement it
     # Breadth-first retrieval (no recursion) using a queue + worker threads
    tree_lock = threading.Lock()
    visited_lock = threading.Lock()

    family_queue = queue.Queue()
    visited_families = set()

    # Mark the starting family and enqueue it
    visited_families.add(family_id)
    family_queue.put(family_id)

    # Number of worker threads for "fast as possible" BFS
    num_workers = 20

    def process_family(fid):
        """
        Worker-level logic to process a single family ID:
        - Fetch the Family
        - Fetch husband, wife, and children
        - Enqueue parents (for BFS) if not visited
        """
        family = _fetch_family(fid, tree, tree_lock)
        if family is None:
            return

        husband_id = family.get_husband()
        wife_id = family.get_wife()

        # Fetch spouses and children (sequentially here, but in parallel with
        # other workers because multiple threads are running)
        person_ids = []
        if husband_id is not None and husband_id != 0:
            person_ids.append(husband_id)
        if wife_id is not None and wife_id != 0:
            person_ids.append(wife_id)

        for child_id in family.get_children():
            if child_id is not None and child_id != 0:
                person_ids.append(child_id)

        for pid in person_ids:
            _fetch_person(pid, tree, tree_lock)

        # After we know spouses, enqueue their parent families (BFS)
        with tree_lock:
            husband = tree.get_person(husband_id) if husband_id else None
            wife = tree.get_person(wife_id) if wife_id else None

        parent_ids = []
        if husband is not None:
            parent_ids.append(husband.get_parentid())
        if wife is not None:
            parent_ids.append(wife.get_parentid())

        for pfid in parent_ids:
            if pfid is None or pfid == 0:
                continue
            with visited_lock:
                if pfid not in visited_families:
                    visited_families.add(pfid)
                    family_queue.put(pfid)

    def worker():
        while True:
            fid = family_queue.get()
            if fid is None:
                # Sentinel value: worker should exit
                family_queue.task_done()
                break

            process_family(fid)
            family_queue.task_done()

    # Start the worker threads
    threads = []
    for _ in range(num_workers):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    # Wait until all families have been processed
    family_queue.join()

    # Stop workers by sending sentinel values
    for _ in range(num_workers):
        family_queue.put(None)
    for t in threads:
        t.join()

    # TODO - implement breadth first retrieval
    # TODO - Printing out people and families that are retrieved from the server will help debugging

    pass

# -----------------------------------------------------------------------------
def breadth_fs_pedigree_limit5(family_id, tree):
    # KEEP this function even if you don't implement it
     # Breadth-first retrieval
    # Limit number of concurrent connections to the FS server to 5
    tree_lock = threading.Lock()
    visited_lock = threading.Lock()

    family_queue = queue.Queue()
    visited_families = set()

    # Starting point
    visited_families.add(family_id)
    family_queue.put(family_id)

    # Exactly 5 workers to respect the "limit 5" requirement
    num_workers = 5

    def process_family(fid):
        family = _fetch_family(fid, tree, tree_lock)
        if family is None:
            return

        husband_id = family.get_husband()
        wife_id = family.get_wife()

        # Fetch all people in this family
        person_ids = []
        if husband_id is not None and husband_id != 0:
            person_ids.append(husband_id)
        if wife_id is not None and wife_id != 0:
            person_ids.append(wife_id)

        for child_id in family.get_children():
            if child_id is not None and child_id != 0:
                person_ids.append(child_id)

        for pid in person_ids:
            _fetch_person(pid, tree, tree_lock)

        # Enqueue parents of the spouses (BFS style)
        with tree_lock:
            husband = tree.get_person(husband_id) if husband_id else None
            wife = tree.get_person(wife_id) if wife_id else None

        parent_ids = []
        if husband is not None:
            parent_ids.append(husband.get_parentid())
        if wife is not None:
            parent_ids.append(wife.get_parentid())

        for pfid in parent_ids:
            if pfid is None or pfid == 0:
                continue
            with visited_lock:
                if pfid not in visited_families:
                    visited_families.add(pfid)
                    family_queue.put(pfid)

    def worker():
        while True:
            fid = family_queue.get()
            if fid is None:
                family_queue.task_done()
                break
            process_family(fid)
            family_queue.task_done()

    # Start 5 worker threads
    threads = []
    for _ in range(num_workers):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    # Wait for all queued families to finish
    family_queue.join()

    # Send sentinel to stop the workers
    for _ in range(num_workers):
        family_queue.put(None)
    for t in threads:
        t.join()
    # TODO - implement breadth first retrieval
    #      - Limit number of concurrent connections to the FS server to 5
    # TODO - Printing out people and families that are retrieved from the server will help debugging

    pass