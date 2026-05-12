"""Application entry point."""

from src.app import create_app


def main() -> None:
    """Run the sample application."""
    app = create_app()
    print(f"App created: {app}")


if __name__ == "__main__":
    main()
