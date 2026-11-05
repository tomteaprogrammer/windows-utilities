import sys
import time
import threading

try:
    from pynput import mouse
    from pynput.mouse import Button
    from pynput.keyboard import Key, Listener as KeyboardListener
except ImportError:
    print("The package 'pynput' is not installed.")
    print("Install it with:  pip install -r requirements.txt")
    input("Press Enter to close...")
    sys.exit(1)

# Virtual-key code of the C key on Windows
VK_C = 67

class AutoClicker:
    def __init__(self):
        self.running = False
        self.click_thread = None
        self.mouse_controller = mouse.Controller()
        self.ctrl_down = False
        
    def start_clicking(self):
        """Start the auto-clicking in a separate thread"""
        self.running = True
        self.click_thread = threading.Thread(target=self.click_loop)
        self.click_thread.daemon = True
        self.click_thread.start()
        print("Auto-clicker started! Press ESC to stop.")
        
    def stop_clicking(self):
        """Stop the auto-clicking"""
        self.running = False
        if self.click_thread and self.click_thread.is_alive():
            self.click_thread.join()
        print("Auto-clicker stopped!")
        
    def click_loop(self):
        """Main clicking loop - clicks every 100ms"""
        while self.running:
            self.mouse_controller.click(Button.left, 1)
            time.sleep(0.1)  # 100ms delay
            
    @staticmethod
    def is_c_key(key):
        """True for the C key, also while Ctrl is held (then Windows reports it as '\\x03')."""
        return getattr(key, 'vk', None) == VK_C or getattr(key, 'char', None) in ('c', 'C', '\x03')

    def on_key_press(self, key):
        """Handle key press events"""
        try:
            if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
                self.ctrl_down = True
            elif self.ctrl_down and self.is_c_key(key):
                # Exit program with Ctrl+C (works in any window)
                self.running = False
                print("Ctrl+C pressed. Exiting.")
                return False
            elif key == Key.esc:
                if not self.running:
                    self.start_clicking()
                else:
                    self.stop_clicking()
        except AttributeError:
            pass
            
    def on_key_release(self, key):
        """Handle key release events"""
        if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
            self.ctrl_down = False
            
    def run(self):
        """Main program loop"""
        print("Auto-Clicker Ready!")
        print("Press ESC to start/stop clicking")
        print("Press Ctrl+C to exit program")
        
        # Start keyboard listener
        with KeyboardListener(
            on_press=self.on_key_press,
            on_release=self.on_key_release) as listener:
            listener.join()

if __name__ == "__main__":
    try:
        clicker = AutoClicker()
        clicker.run()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"Error: {e}")