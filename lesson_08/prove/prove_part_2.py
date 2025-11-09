"""
Course: CSE 351 
Assignment: 08 Prove Part 2
File:   prove_part_2.py
Author: Samantha Mayes

Purpose: Part 2 of assignment 8, finding the path to the end of a maze using recursion.

Instructions:
- Do not create classes for this assignment, just functions.
- Do not use any other Python modules other than the ones included.
- You MUST use recursive threading to find the end of the maze.
- Each thread MUST have a different color than the previous thread:
    - Use get_color() to get the color for each thread; you will eventually have duplicated colors.
    - Keep using the same color for each branch that a thread is exploring.
    - When you hit an intersection spin off new threads for each option and give them their own colors.

This code is not interested in tracking the path to the end position. Once you have completed this
program however, describe how you could alter the program to display the found path to the exit
position:

What would be your strategy?

I would have each visited maze square remember where it came from by storing a “parent”
pointer. For example, I could keep a dictionary that maps (row, col) to the previous
(row, col) that we moved from. When a thread finds the exit, it can follow these parent
links backwards from the exit cell to the start cell, building a list of positions that
form the solution path. Then I could reverse that list and redraw those cells in a
special solution color.

Why would it work?

This works because the parent pointers record the exact route that led to the exit.
Each time we move into a new square, we only set its parent once, so the parent chain
from the exit back to the start always describes one valid path through the maze.
By following the chain from the exit to the start and reversing it, we reconstruct
the path in the correct order and can display it even though the search was done
with multiple threads.

"""

import math
import threading 
from screen import Screen
from maze import Maze
import sys
import cv2

# Include cse 351 files
from cse351 import *

SCREEN_SIZE = 700
COLOR = (0, 0, 255)
COLORS = (
    (0,0,255),
    (0,255,0),
    (255,0,0),
    (255,255,0),
    (0,255,255),
    (255,0,255),
    (128,0,0),
    (128,128,0),
    (0,128,0),
    (128,0,128),
    (0,128,128),
    (0,0,128),
    (72,61,139),
    (143,143,188),
    (226,138,43),
    (128,114,250)
)
SLOW_SPEED = 100
FAST_SPEED = 0

# Globals
current_color_index = 0
thread_count = 0
stop = False
speed = SLOW_SPEED

threads = []
thread_lock = threading.Lock()

def get_color():
    """ Returns a different color when called """
    global current_color_index
    if current_color_index >= len(COLORS):
        current_color_index = 0
    color = COLORS[current_color_index]
    current_color_index += 1
    return color


# TODO: Add any function(s) you need, if any, here.
def _walk_maze(maze, row, col, color):
    """Recursive walker for a single thread starting at (row, col)."""
    global stop

    # If someone already found the exit, stop exploring.
    if stop:
        return

    # If this thread has reached the end, signal everyone to stop.
    if maze.at_end(row, col):
        stop = True
        return

    # Compute valid next moves from this cell.
    valid_moves = []
    for next_row, next_col in maze.get_possible_moves(row, col):
        if maze.can_move_here(next_row, next_col):
            valid_moves.append((next_row, next_col))

    # No where else to go from here.
    if not valid_moves:
        return

    # Current thread will follow the first move;
    # extra moves each get their own new thread.
    first_move = valid_moves[0]
    other_moves = valid_moves[1:]

    # Spawn new threads for each additional branch.
    for nr, nc in other_moves:
        if stop:
            break

        new_color = get_color()

        def branch_start(r=nr, c=nc, col=new_color):
            # Each branch thread first moves into its starting cell,
            # then continues walking recursively.
            if stop:
                return
            maze.move(r, c, col)
            _walk_maze(maze, r, c, col)

        t = threading.Thread(target=branch_start)

        # Track how many threads we create and keep them in a list.
        global thread_count, threads
        with thread_lock:
            thread_count += 1
            threads.append(t)

        t.start()

    # Continue down the first branch in this same thread.
    if not stop:
        nr, nc = first_move
        maze.move(nr, nc, color)
        _walk_maze(maze, nr, nc, color)

def solve_find_end(maze):
    """ Finds the end position using threads. Nothing is returned. """
    global stop, thread_count, threads

    # Reset globals for each new maze
    stop = False
    thread_count = 0
    threads = []

    # Get the starting position
    start_row, start_col = maze.get_start_pos()
    start_color = get_color()

    # Initial worker thread: starts at the maze entrance
    def start_thread():
        if stop:
            return
        maze.move(start_row, start_col, start_color)
        _walk_maze(maze, start_row, start_col, start_color)

    t0 = threading.Thread(target=start_thread)
    thread_count += 1
    threads.append(t0)
    t0.start()

    # Wait for all created threads to finish
    for t in threads:
        t.join()




def find_end(log, filename, delay):
    """ Do not change this function """

    global thread_count
    global speed

    # create a Screen Object that will contain all of the drawing commands
    screen = Screen(SCREEN_SIZE, SCREEN_SIZE)
    screen.background((255, 255, 0))

    maze = Maze(screen, SCREEN_SIZE, SCREEN_SIZE, filename, delay=delay)

    solve_find_end(maze)

    log.write(f'Number of drawing commands = {screen.get_command_count()}')
    log.write(f'Number of threads created  = {thread_count}')

    done = False
    while not done:
        if screen.play_commands(speed): 
            key = cv2.waitKey(0)
            if key == ord('1'):
                speed = SLOW_SPEED
            elif key == ord('2'):
                speed = FAST_SPEED
            elif key == ord('q'):
                exit()
            elif key != ord('p'):
                done = True
        else:
            done = True


def find_ends(log):
    """ Do not change this function """

    files = (
        ('very-small.bmp', True),
        ('very-small-loops.bmp', True),
        ('small.bmp', True),
        ('small-loops.bmp', True),
        ('small-odd.bmp', True),
        ('small-open.bmp', False),
        ('large.bmp', False),
        ('large-loops.bmp', False),
        ('large-squares.bmp', False),
        ('large-open.bmp', False)
    )

    log.write('*' * 40)
    log.write('Part 2')
    for filename, delay in files:
        filename = f'./mazes/{filename}'
        log.write()
        log.write(f'File: {filename}')
        find_end(log, filename, delay)
    log.write('*' * 40)


def main():
    """ Do not change this function """
    sys.setrecursionlimit(5000)
    log = Log(show_terminal=True)
    find_ends(log)


if __name__ == "__main__":
    main()