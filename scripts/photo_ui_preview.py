"""Isolated UI data with real local vision for synthetic photo acceptance checks."""
from unittest.mock import patch
import uvicorn

if __name__ == "__main__":
    from scripts.assistant_ui_preview import main
    original = uvicorn.run
    def serve(app, **kwargs):
        kwargs['port'] = 8878
        original(app, **kwargs)
    with patch('uvicorn.run', serve):
        main()
