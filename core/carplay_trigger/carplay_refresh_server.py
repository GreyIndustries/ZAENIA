"""Retired legacy entry point. Use the owner-activated protected API."""
def run_server(*args, **kwargs):
    raise RuntimeError("The legacy /refresh server is retired. Run: py -3.11 -m core.api.server server. Use /api/carplay/briefing with the stored API token.")

def refresh_carplay_briefing(*args, **kwargs):
    raise PermissionError("Legacy direct refresh is disabled; use the protected API.")

def run_calendar_sync(*args, **kwargs):
    raise PermissionError("Legacy subprocess sync is disabled; use the authenticated calendar sync CLI.")

def main():
    run_server()

if __name__ == "__main__":
    main()
