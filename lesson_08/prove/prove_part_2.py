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
pointer (for example, a dictionary that maps (row, col) -> previous (row, col) on the path).
When a thread reaches the exit, I would follow these parent links backward from the end
square to the start to reconstruct the path, then draw that path in a single color.

Why would it work?

Because every move in the search is from a valid neighbor, each parent pointer forms one
step of a real path through the maze. The thread that finds the exit has a continuous chain
of parents all the way back to the start. Walking those links in reverse guarantees we get a
correct start-to-end path that we can then display after all threads have stopped.

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

def get_color():
    """ Returns a different color when called """
    global current_color_index
    if current_color_index >= len(COLORS):
        current_color_index = 0
    color = COLORS[current_color_index]
    current_color_index += 1
    return color


# TODO: Add any function(s) you need, if any, here.


def solve_find_end(maze):
    """ Finds the end position using threads. Nothing is returned. """
    # When one of the threads finds the end position, stop all of them.
    global stop
    stop = False

    def search(row, col, color):
        """Recursive search that spins off threads at intersections."""
        global stop
        global thread_count

        if stop:
            return  # some other thread already found exit

        # If we reached the end, signal stop and return.
        try:
            if maze.at_end(row, col):
                stop = True
                return
        except Exception:
            # If maze doesn't provide at_end or call fails, bail out.
            return

        # Get candidate moves and filter to those we can actually move to.
        try:
            moves = maze.get_possible_moves(row, col)
        except Exception:
            return

        valid = []
        for mv in moves:
            # mv may be a tuple (r, c) or other form; try to unpack
            try:
                r, c = mv
            except Exception:
                continue
            try:
                if maze.can_move_here(r, c):
                    valid.append((r, c))
            except Exception:
                # if can_move_here is not present, assume move is valid
                valid.append((r, c))

        if not valid:
            return  # dead end

        child_threads = []

        # For every extra move beyond the first, spawn a new thread.
        for r, c in valid[1:]:
            new_color = get_color()
            try:
                maze.move(r, c, new_color)
            except Exception:
                pass
            t = threading.Thread(target=search, args=(r, c, new_color))
            thread_count += 1
            t.start()
            child_threads.append(t)

        # Continue following the first move in the current thread.
        first_r, first_c = valid[0]
        try:
            maze.move(first_r, first_c, color)
        except Exception:
            pass
        search(first_r, first_c, color)

        # Join any child threads we created before returning.
        for t in child_threads:
            t.join()

    # Determine a reasonable starting position (try several common names).
    start_row = start_col = None
    start = None
    if hasattr(maze, 'get_start_pos'):
        try:
            start = maze.get_start_pos()
        except Exception:
            start = None
    if start is None and hasattr(maze, 'get_start'):
        try:
            start = maze.get_start()
        except Exception:
            start = None
    if start is None and hasattr(maze, 'start'):
        start = getattr(maze, 'start')
    if start is None and hasattr(maze, 'start_row') and hasattr(maze, 'start_col'):
        try:
            start_row = getattr(maze, 'start_row')
            start_col = getattr(maze, 'start_col')
        except Exception:
            start_row = start_col = None

    if start is not None:
        try:
            if isinstance(start, tuple) and len(start) == 2:
                start_row, start_col = start
        except Exception:
            start_row = start_col = None

    # If we couldn't locate a start, do nothing.
    if start_row is None or start_col is None:
        return

    # Begin search from the start position using a fresh color.
    color = get_color()
    try:
        maze.move(start_row, start_col, color)
    except Exception:
        pass
    search(start_row, start_col, color)



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