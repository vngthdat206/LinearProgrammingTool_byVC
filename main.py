from __future__ import annotations

if __package__ in (None, ""):
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gui_app import SimplexApp
else:
    from .gui_app import SimplexApp


def main():
    app = SimplexApp()
    app.mainloop()


if __name__ == "__main__":
    main()
