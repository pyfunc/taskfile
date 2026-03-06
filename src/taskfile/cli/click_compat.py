"""## Compatibility layer for clickmd

Provides missing click functions that are not available in `clickmd`.

### Why this module exists

> **Note**: `clickmd` is a lightweight wrapper around `click` that adds markdown rendering
> capabilities. However, it doesn't expose all of click's functionality.
> This module fills those gaps.

### Functions provided

- `confirm()` - Interactive yes/no prompts
- `prompt()` - Text input prompts with optional hiding (for passwords)
- `version_option()` - `--version` flag decorator
- Exception classes: `Abort`, `BadParameter`, `ClickException`

### Usage example

```python
import clickmd as click
from taskfile.cli.click_compat import confirm, version_option

@click.command()
@version_option("1.0.0", prog_name="myapp")
def main():
    if confirm("Continue?"):
        click.echo("Proceeding...")
```
"""

import sys
from typing import Any

# Import clickmd as the base
import clickmd as click


class Abort(Exception):
    """Exception to signal that the application should exit."""
    pass


class BadParameter(Exception):
    """Exception raised for bad parameter values."""
    
    def __init__(self, message: str, ctx: Any = None, param: Any = None, param_hint: str = None) -> None:
        super().__init__(message)
        self.ctx = ctx
        self.param = param
        self.param_hint = param_hint


class ClickException(Exception):
    """Base class for click exceptions."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def confirm(text: str, default: bool = False, abort: bool = False, prompt_suffix: str = ": ", show_default: bool = True, err: bool = False) -> bool:
    """Prompt for confirmation (yes/no question).
    
    Args:
        text: Question text
        default: Default value if user just presses Enter
        abort: If True, aborts on No
        prompt_suffix: Suffix after the question
        show_default: Whether to show the default value
        err: Print to stderr instead of stdout
        
    Returns:
        True if user confirms, False otherwise
    """
    if show_default and default:
        suffix = f"{prompt_suffix}[Y/n]"
    elif show_default and not default:
        suffix = f"{prompt_suffix}[y/N]"
    else:
        suffix = prompt_suffix
    
    while True:
        click.echo(text + suffix, err=err)
        try:
            value = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            click.echo("", err=err)
            raise Abort()
        
        if value in ("", "y", "yes", "ye", "y"):
            return True
        elif value in ("n", "no"):
            if abort:
                raise Abort()
            return False
        else:
            click.echo("Invalid input. Please enter 'y' or 'n'.", err=err)


def prompt(text: str, default: Any = None, type: Any = None, value_proc: Any = None, prompt_suffix: str = ": ", show_default: bool = True, err: bool = False, hide_input: bool = False, confirmation_prompt: bool = False, allow_missing_auto: bool = False) -> Any:
    """Prompt for user input.
    
    Args:
        text: Prompt text
        default: Default value
        type: Type converter
        value_proc: Value processor
        prompt_suffix: Suffix after the prompt
        show_default: Whether to show the default value
        err: Print to stderr instead of stdout
        hide_input: Hide user input (for passwords)
        confirmation_prompt: Ask for confirmation
        allow_missing_auto: Allow missing auto values
        
    Returns:
        User input value
    """
    prompt_text = text
    if show_default and default is not None:
        prompt_text += f"{prompt_suffix}[{default}]"
    else:
        prompt_text += prompt_suffix
    
    click.echo(prompt_text, err=err, nl=False)
    
    try:
        if hide_input:
            import getpass
            value = getpass.getpass("")
        else:
            value = input()
    except (EOFError, KeyboardInterrupt):
        click.echo("", err=err)
        raise Abort()
    
    if not value and default is not None:
        value = default
    
    if type is not None and value is not None:
        try:
            if callable(type):
                value = type(value)
            else:
                # Handle basic types
                if type == int:
                    value = int(value)
                elif type == float:
                    value = float(value)
                elif type == bool:
                    value = value.lower() in ("true", "1", "yes", "y")
        except (ValueError, TypeError) as e:
            raise BadParameter(f"Invalid value: {e}")
    
    if confirmation_prompt and not hide_input:
        click.echo(f"Repeat for confirmation: ", err=err, nl=False)
        try:
            confirmation = input()
        except (EOFError, KeyboardInterrupt):
            click.echo("", err=err)
            raise Abort()
        
        if confirmation != value:
            raise BadParameter("Confirmed value does not match")
    
    return value


def version_option(version: str = None, prog_name: str = None, message: str = None, help: str = None, **kwargs):
    """Add a --version option to the command.
    
    Args:
        version: Version string
        prog_name: Program name
        message: Version message template
        help: Help text
        **kwargs: Additional arguments
        
    Returns:
        Decorator function
    """
    if message is None:
        if version is None:
            version = "unknown"
        if prog_name is None:
            prog_name = "program"
        message = f"{prog_name}, version {version}"
    
    if help is None:
        help = "Show the version and exit."
    
    def decorator(f):
        # Add the version option to the function
        f = click.option("--version", is_flag=True, help=help, **kwargs)(f)
        
        # Wrap the function to handle version
        def wrapper(ctx, *args, **kwargs):
            if kwargs.pop("version", None):
                click.echo(message)
                ctx.exit()
            return f(ctx, *args, **kwargs)
        
        # Preserve the original function's metadata
        import functools
        wrapper = functools.update_wrapper(wrapper, f)
        return wrapper
    return decorator


# Export all the compatibility functions
__all__ = [
    "Abort",
    "BadParameter", 
    "ClickException", 
    "confirm", 
    "prompt", 
    "version_option"
]
