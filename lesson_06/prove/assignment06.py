"""
Course: CSE 351
Assignment: 06
Author: [Your Name]

Instructions:

- see instructions in the assignment description in Canvas

""" 

import multiprocessing as mp
import os
import cv2
import numpy as np

from cse351 import *

# Folders
INPUT_FOLDER = "faces"
STEP1_OUTPUT_FOLDER = "step1_smoothed"
STEP2_OUTPUT_FOLDER = "step2_grayscale"
STEP3_OUTPUT_FOLDER = "step3_edges"

# Parameters for image processing
GAUSSIAN_BLUR_KERNEL_SIZE = (5, 5)
CANNY_THRESHOLD1 = 75
CANNY_THRESHOLD2 = 155

# Allowed image extensions
ALLOWED_EXTENSIONS = ['.jpg']

# Sentinel value for queue processing
STOP = "STOP"

# ---------------------------------------------------------------------------
def create_folder_if_not_exists(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Created folder: {folder_path}")

# ---------------------------------------------------------------------------
def task_convert_to_grayscale(image):
    if len(image.shape) == 2 or (len(image.shape) == 3 and image.shape[2] == 1):
        return image # Already grayscale
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# ---------------------------------------------------------------------------
def task_smooth_image(image, kernel_size):
    return cv2.GaussianBlur(image, kernel_size, 0)

# ---------------------------------------------------------------------------
def task_detect_edges(image, threshold1, threshold2):
    if len(image.shape) == 3 and image.shape[2] == 3:
        print("Warning: Applying Canny to a 3-channel image. Converting to grayscale first for Canny.")
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif len(image.shape) == 3 and image.shape[2] != 1 : # Should not happen with typical images
        print(f"Warning: Input image for Canny has an unexpected number of channels: {image.shape[2]}")
        return image # Or raise error
    return cv2.Canny(image, threshold1, threshold2)

# ---------------------------------------------------------------------------
def process_images_in_folder(input_folder,              # input folder with images
                             output_folder,             # output folder for processed images
                             processing_function,       # function to process the image (ie., task_...())
                             load_args=None,            # Optional args for cv2.imread
                             processing_args=None):     # Optional args for processing function

    create_folder_if_not_exists(output_folder)
    print(f"\nProcessing images from '{input_folder}' to '{output_folder}'...")

    processed_count = 0
    for filename in os.listdir(input_folder):
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            continue

        input_image_path = os.path.join(input_folder, filename)
        output_image_path = os.path.join(output_folder, filename) # Keep original filename

        try:
            # Read the image
            if load_args is not None:
                img = cv2.imread(input_image_path, load_args)
            else:
                img = cv2.imread(input_image_path)

            if img is None:
                print(f"Warning: Could not read image '{input_image_path}'. Skipping.")
                continue

            # Apply the processing function
            if processing_args:
                processed_img = processing_function(img, *processing_args)
            else:
                processed_img = processing_function(img)

            # Save the processed image
            cv2.imwrite(output_image_path, processed_img)

            processed_count += 1
        except Exception as e:
            print(f"Error processing file '{input_image_path}': {e}")

    print(f"Finished processing. {processed_count} images processed into '{output_folder}'.")

# ---------------------------------------------------------------------------
def worker_smooth(q_in, q_out):
    while True:
        item = q_in.get()
        if item == STOP:
            q_out.put(STOP)
            break
        in_path, out_path = item
        img = cv2.imread(in_path)
        if img is None:
            print(f"Warning: Could not read image '{in_path}'. Skipping.")
            continue
        smoothed_img = task_smooth_image(img, GAUSSIAN_BLUR_KERNEL_SIZE)
        q_out.put((smoothed_img, out_path))

def worker_gray(q_in, q_out):
    while True:
        item = q_in.get()
        if item == STOP:
            q_out.put(STOP)
            break
        smoothed_img, out_path = item
        gray_img = task_convert_to_grayscale(smoothed_img)
        q_out.put((gray_img, out_path))

def worker_edges(q_in):
    while True:
        item = q_in.get()
        if item == STOP:
            break
        gray_img, out_path = item
        edge_img = task_detect_edges(gray_img, CANNY_THRESHOLD1, CANNY_THRESHOLD2)
        cv2.imwrite(out_path, edge_img)

def run_image_processing_pipeline():
    print("Starting image processing pipeline...")

    # TODO
    # - create queues
    q1 = mp.Queue(maxsize=256)  # (in_path, out_path)
    q2 = mp.Queue(maxsize=256)  # (smoothed_img, out_path)
    q3 = mp.Queue(maxsize=256)  # (gray_img, out_path)
    # - create barriers 
    start_event = mp.Event()

    # --- Decide worker counts ---
    cpu = max(1, (mp.cpu_count() or 2) - 1)
    smooth_workers = max(1, cpu // 2)   # I/O + light CPU
    gray_workers   = max(1, cpu // 2)   # light CPU
    edge_workers   = max(1, cpu)        # CPU heavy

    # - create the three processes groups
    smoothers = [mp.Process(target=worker_smooth, args=(q1, q2), daemon=True)
                 for _ in range(smooth_workers)]
    grayers   = [mp.Process(target=worker_gray, args=(q2, q3), daemon=True)
                 for _ in range(gray_workers)]
    edgers    = [mp.Process(target=worker_edges, args=(q3,), daemon=True)
                 for _ in range(edge_workers)]
    for p in smoothers + grayers + edgers:
        p.start()

    # If you modified workers to wait on start_event, release them here:
    # start_event.set()

    # --- Feed stage 1 with (in_path, out_path) pairs ---
    file_pairs = []
    for filename in os.listdir(INPUT_FOLDER):
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in ALLOWED_EXTENSIONS:
            in_path = os.path.join(INPUT_FOLDER, filename)
            out_path = os.path.join(STEP1_OUTPUT_FOLDER, filename)
            file_pairs.append((in_path, out_path))
    for pair in file_pairs:
        q1.put(pair)

    # --- Send sentinels to stage 1 (one per smoother). They propagate downstream. ---
    for _ in range(smooth_workers):
        q1.put(STOP)
    q1.close()

    # --- Join in order ---
    for p in smoothers:
        p.join()
    for p in grayers:
        p.join()
    for p in edgers:
        p.join()

    # - you are free to change anything in the program as long as you
    #   do all requirements.

    # --- Step 1: Smooth Images ---
    process_images_in_folder(INPUT_FOLDER, STEP1_OUTPUT_FOLDER, task_smooth_image,
                             processing_args=(GAUSSIAN_BLUR_KERNEL_SIZE,))

    # --- Step 2: Convert to Grayscale ---
    process_images_in_folder(STEP1_OUTPUT_FOLDER, STEP2_OUTPUT_FOLDER, task_convert_to_grayscale)

    # --- Step 3: Detect Edges ---
    process_images_in_folder(STEP2_OUTPUT_FOLDER, STEP3_OUTPUT_FOLDER, task_detect_edges,
                             load_args=cv2.IMREAD_GRAYSCALE,        
                             processing_args=(CANNY_THRESHOLD1, CANNY_THRESHOLD2))

    print("\nImage processing pipeline finished!")
    print(f"Original images are in: '{INPUT_FOLDER}'")
    print(f"Grayscale images are in: '{STEP1_OUTPUT_FOLDER}'")
    print(f"Smoothed images are in: '{STEP2_OUTPUT_FOLDER}'")
    print(f"Edge images are in: '{STEP3_OUTPUT_FOLDER}'")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    log = Log(show_terminal=True)
    log.start_timer('Processing Images')

    # check for input folder
    if not os.path.isdir(INPUT_FOLDER):
        print(f"Error: The input folder '{INPUT_FOLDER}' was not found.")
        print(f"Create it and place your face images inside it.")
        print('Link to faces.zip:')
        print('   https://drive.google.com/file/d/1eebhLE51axpLZoU6s_Shtw1QNcXqtyHM/view?usp=sharing')
    else:
        run_image_processing_pipeline()

    log.write()
    log.stop_timer('Total Time')