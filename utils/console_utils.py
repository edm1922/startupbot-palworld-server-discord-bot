import os
import ctypes

def disable_quick_edit():
    """
    Disables 'QuickEdit Mode' in Windows Command Prompt to prevent
    process suspension when the user clicks inside the console window.
    """
    if os.name != 'nt':
        return

    try:
        kernel32 = ctypes.windll.kernel32
        
        # Standard Handle for STDIN
        STD_INPUT_HANDLE = -10
        
        # ENABLE_QUICK_EDIT_MODE = 0x0040 | ENABLE_INSERT_MODE = 0x0020 | ENABLE_MOUSE_INPUT = 0x0010
        # We want to DISABLE Quick Edit (0x0040) and Insert Mode (0x0020)
        # Standard input processing usually includes:
        # ENABLE_PROCESSED_INPUT (0x0001) | ENABLE_LINE_INPUT (0x0002) | ENABLE_ECHO_INPUT (0x0004) | ENABLE_MOUSE_INPUT (0x0010) ...
        # EXTENDED_FLAGS (0x0080) is needed to update QuickEdit settings safely
        
        ENABLE_EXTENDED_FLAGS = 0x0080
        
        h_stdin = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        mode = ctypes.c_ulong()
        
        if not kernel32.GetConsoleMode(h_stdin, ctypes.byref(mode)):
            return

        # Disable QuickEdit (0x0040) and Insert Mode (0x0020)
        # We keep the other flags as they were, but ensure QuickEdit bit is 0
        new_mode = mode.value & ~0x0040 & ~0x0020
        
        # Must set Enable Extended Flags to allow modification of mouse settings
        new_mode |= ENABLE_EXTENDED_FLAGS
        
        kernel32.SetConsoleMode(h_stdin, new_mode)
        print("🛡️ Windows QuickEdit Mode disabled (Prevents console freezing).")
        
    except Exception as e:
        print(f"⚠️ Failed to disable QuickEdit Mode: {e}")
