"""Crowdent: offline crowd-risk forecasting research platform."""

__version__ = "0.1.0"


def main() -> None:
    """Compatibility entry point for direct module execution."""

    from crowdent.cli import app

    app()


__all__ = ["__version__", "main"]
