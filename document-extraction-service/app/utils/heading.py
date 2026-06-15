def build_breadcrumbs(heading_stack: dict[int, str]) -> list[str]:
    """Build a breadcrumb trail from the current heading stack.

    heading_stack maps heading level (1-6) to heading text.
    Returns breadcrumbs in order from highest level to lowest.
    """
    if not heading_stack:
        return []
    return [heading_stack[level] for level in sorted(heading_stack.keys()) if heading_stack[level]]


def update_heading_stack(heading_stack: dict[int, str], level: int, text: str) -> dict[int, str]:
    """Update the heading stack when a new heading is encountered.

    Clears all lower-level headings (a new h2 clears h3-h6).
    """
    heading_stack[level] = text
    # Clear lower-level headings
    for lvl in list(heading_stack.keys()):
        if lvl > level:
            del heading_stack[lvl]
    return heading_stack
