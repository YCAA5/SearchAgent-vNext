import argparse
import os
import sys


def main():
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')
    parser = argparse.ArgumentParser(description='Search Agent desktop application')
    parser.add_argument('--data-dir')
    parser.add_argument('--language', choices=['tr', 'en'])
    parser.add_argument('--self-test-report')
    parser.add_argument('--verify-model', action='store_true')
    parser.add_argument('--verify-ocr', action='store_true')
    args = parser.parse_args()
    if args.data_dir:
        os.environ['SEARCH_AGENT_HOME'] = os.path.abspath(args.data_dir)
    if args.language:
        os.environ['SEARCH_AGENT_LANGUAGE'] = args.language
    if getattr(sys, 'frozen', False) and not os.environ.get('TESSERACT_CMD'):
        from app_paths import find_tesseract
        executable = find_tesseract()
        if executable:
            os.environ['TESSERACT_CMD'] = executable
    if args.self_test_report:
        from diagnostics import run_self_test
        return run_self_test(args.self_test_report, args.verify_model, args.verify_ocr)
    try:
        if os.name == 'nt':
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('SearchAgent.Desktop.1')
        from desktop_app import main as run_app
        run_app()
        return 0
    except Exception:
        import traceback
        from app_paths import DATA_ROOT
        log = DATA_ROOT / 'logs' / 'startup-error.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(traceback.format_exc(), encoding='utf-8')
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, f'Search Agent could not start.\n\nDetails: {log}', 'Search Agent', 16)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
