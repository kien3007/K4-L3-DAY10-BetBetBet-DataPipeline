from pathlib import Path
import subprocess
import sys

# Auto-use .venv python if running outside virtual environment
project_root = Path(__file__).resolve().parent.parent
venv_python = project_root / ".venv" / "Scripts" / "python.exe"
if venv_python.exists() and sys.prefix == sys.base_prefix and Path(sys.executable).resolve() != venv_python.resolve():
    sys.exit(subprocess.call([str(venv_python)] + sys.argv))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from pipelines.phase1 import main


if __name__ == "__main__":
    main()
