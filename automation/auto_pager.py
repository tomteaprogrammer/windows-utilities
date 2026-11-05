import sys
import time
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

# --- Check for the required library (no automatic install) ---
try:
    import keyboard
except ImportError:
    _msg = ("The package 'keyboard' is not installed.\n\n"
            "Open a terminal in this program's folder and run:\n\n"
            "pip install -r requirements.txt")
    print(_msg)
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror("Missing Package", _msg)
    _root.destroy()
    sys.exit(1)

# --- Global variables for controlling the action ---
action_active = False
paused = True
action_thread = None
# Plain number copied from the slider on the main thread, so the worker thread never reads Tk variables
interval_seconds = 0.7
# Hotkeys run on the keyboard library's own thread; they put a request here for the Tk main thread
hotkey_requests = queue.Queue()

def pagedown_function():
    """
    This function runs in a separate thread.
    As long as the action is active and not paused, it presses 'page down'.
    """
    while action_active:
        if not paused:
            # Press and release the 'page down' key
            keyboard.press_and_release('page down')
            # Sleep for the interval set by the GUI slider
            time.sleep(interval_seconds)
        else:
            # If paused, sleep briefly to prevent the loop from using too much CPU
            time.sleep(0.1)

def toggle_action():
    """Starts, pauses, or resumes the key-pressing action."""
    global action_active, paused, action_thread
    if not action_active:
        action_active = True
        paused = False
        action_thread = threading.Thread(target=pagedown_function, daemon=True)
        action_thread.start()
        toggle_button.config(text="Pause")
        print("▶️ Action started.")
    else:
        paused = not paused
        if paused:
            toggle_button.config(text="Resume")
            print("⏸️ Action paused.")
        else:
            toggle_button.config(text="Pause")
            print("▶️ Action resumed.")

def update_interval_label(val):
    """Updates the text label to show the current interval."""
    global interval_seconds
    interval_seconds = float(val)
    # The value from the slider is a string; format it to two decimal places
    formatted_val = f"{float(val):.2f}s"
    interval_label.config(text=formatted_val)

def on_closing():
    """Handles the event of the GUI window being closed."""
    global action_active
    action_active = False
    print("\n👋 Exiting auto-pager script. Goodbye!")
    root.destroy()
    import os
    os._exit(0)

def poll_hotkeys():
    """Runs on the Tk main thread and handles hotkey presses."""
    try:
        while True:
            request = hotkey_requests.get_nowait()
            if request == "toggle":
                toggle_action()
            elif request == "quit":
                on_closing()
                return
    except queue.Empty:
        pass
    root.after(100, poll_hotkeys)

# --- Main Execution Block ---
if __name__ == "__main__":
    # Setup the main GUI window
    root = tk.Tk()
    root.title("Auto Pager")
    root.geometry("280x150")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    # This variable will be linked to the slider for the time interval
    interval_var = tk.DoubleVar(value=0.7) # Default interval is 0.7 seconds

    # Create and pack the GUI widgets
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill="both", expand=True)

    toggle_button = ttk.Button(main_frame, text="Start Paging", command=toggle_action)
    toggle_button.pack(pady=5)

    # Frame to hold the slider and its labels
    slider_frame = ttk.Frame(main_frame)
    slider_frame.pack(pady=5, fill="x", expand=True)

    ttk.Label(slider_frame, text="Interval:").pack(side="left", padx=(0, 5))
    interval_label = ttk.Label(slider_frame, text=f"{interval_var.get():.2f}s")
    interval_label.pack(side="right")
    
    speed_slider = ttk.Scale(
        slider_frame,
        from_=0.1,  # Minimum interval (very fast)
        to=2.0,     # Maximum interval (slow)
        orient="horizontal",
        variable=interval_var,
        command=update_interval_label
    )
    speed_slider.pack(side="left", fill="x", expand=True)

    # --- Setup Hotkeys ---
    # suppress is off, so other programs still receive these keys (Esc keeps working everywhere).
    keyboard.add_hotkey('ctrl+alt+down', lambda: hotkey_requests.put("toggle"))
    keyboard.add_hotkey('esc', lambda: hotkey_requests.put("quit"))
    root.after(100, poll_hotkeys)
    
    root.protocol("WM_DELETE_WINDOW", on_closing)

    print("--- Auto Pager Script Running ---")
    print("Use the GUI or 'Ctrl+Alt+Down' to Start/Pause.")
    print("Close the window or press 'ESC' to quit.")
    print("-----------------------------------")
    
    root.mainloop()