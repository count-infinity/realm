"""
REALM project templates.

Used by `realm init` to scaffold new game projects.
"""

from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent


def get_template(name: str) -> str:
    """
    Get a template file's contents.

    Args:
        name: Template filename (e.g., 'config.py.template')

    Returns:
        Template contents as string.

    Raises:
        FileNotFoundError: If template doesn't exist.
    """
    template_path = TEMPLATE_DIR / name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {name}")
    return template_path.read_text()


def render_template(name: str, **kwargs) -> str:
    """
    Render a template with variable substitution.

    Uses simple {variable} substitution.

    Args:
        name: Template filename
        **kwargs: Variables to substitute

    Returns:
        Rendered template string.
    """
    content = get_template(name)
    return content.format(**kwargs)
