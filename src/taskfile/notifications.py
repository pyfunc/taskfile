"""Notifications for taskfile - desktop notifications when tasks complete."""

from __future__ import annotations

import os
import platform
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def notify_task_complete(task_name: str, success: bool, duration: float | None = None) -> None:
    """Send desktop notification when task completes.
    
    Supports:
    - macOS (osascript)
    - Linux (notify-send or zenity)
    - Windows (powershell)
    """
    system = platform.system()
    
    # Format duration if provided
    duration_str = ""
    if duration:
        if duration < 60:
            duration_str = f" ({duration:.1f}s)"
        else:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            duration_str = f" ({minutes}m {seconds}s)"
    
    title = "✅ Task Complete" if success else "❌ Task Failed"
    message = f"'{task_name}' finished{duration_str}"
    
    try:
        if system == "Darwin":  # macOS
            _notify_macos(title, message)
        elif system == "Linux":
            _notify_linux(title, message)
        elif system == "Windows":
            _notify_windows(title, message)
    except Exception:
        # Silently fail if notifications not available
        pass


def _notify_macos(title: str, message: str) -> None:
    """Send notification on macOS."""
    # Use osascript for native notifications
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _notify_linux(title: str, message: str) -> None:
    """Send notification on Linux."""
    # Try notify-send first (libnotify)
    try:
        subprocess.run(
            ["notify-send", title, message, "-a", "taskfile"],
            capture_output=True,
            check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to zenity if available
        try:
            subprocess.run(
                ["zenity", "--info", "--title", title, "--text", message],
                capture_output=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass


def _notify_windows(title: str, message: str) -> None:
    """Send notification on Windows."""
    # Use PowerShell for Windows notifications
    ps_script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    $notification = New-Object System.Windows.Forms.NotifyIcon
    $notification.Icon = [System.Drawing.SystemIcons]::Information
    $notification.BalloonTipTitle = "{title}"
    $notification.BalloonTipText = "{message}"
    $notification.Visible = $True
    $notification.ShowBalloonTip(5000)
    """
    subprocess.run(
        ["powershell", "-Command", ps_script],
        capture_output=True
    )


def is_notification_available() -> bool:
    """Check if desktop notifications are available on this system."""
    system = platform.system()
    
    if system == "Darwin":
        return True  # macOS always has osascript
    elif system == "Linux":
        # Check for notify-send or zenity
        for cmd in ["notify-send", "zenity"]:
            if subprocess.run(["which", cmd], capture_output=True).returncode == 0:
                return True
        return False
    elif system == "Windows":
        return True  # Windows has PowerShell
    
    return False
