import subprocess
from typing import Tuple


def run_bash(bash_command: str) -> Tuple[str, str, int]:
    """
    returns (output, error, return_value)
    """
    commands = []
    for each in bash_command.split():
        commands.append(each.strip('"'))
    print()
    print(commands)
    cmd: str
    for cmd in commands:
        if cmd.startswith("CLIP"):
            raise Exception("WTF")
    # input("Press Enter to continue...")
    print()
    completed_process = subprocess.run(commands, encoding='UTF-8')
    return (completed_process.stdout, completed_process.stderr, completed_process.returncode)

