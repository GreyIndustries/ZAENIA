"""Compatibility CLI for the secured voice runtime."""
def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["start","confirm","self-test"])
    args=parser.parse_args()
    if args.command=="self-test":
        from core.voice_security.self_test import run
        run()
    else:
        from core.voice_security.runtime import run,confirm
        run() if args.command=="start" else confirm()

if __name__=="__main__": main()
