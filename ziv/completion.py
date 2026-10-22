"""Native shell completion for the public ``ziv`` command."""
from __future__ import annotations

from collections.abc import Sequence

SHELLS = ("bash", "zsh", "fish", "powershell")

COMMANDS = (
    "help",
    "completion",
    "setup",
    "doctor",
    "links",
    "channels",
    "make",
    "parts",
    "number-parts",
    "number_only",
    "post",
    "source",
    "scan",
    "queue",
    "queue-status",
    "styles",
)

PIPELINE_FLAGS = (
    "--clips",
    "--auto-mode",
    "--min",
    "--max",
    "--out",
    "--limit",
    "--no-upload",
    "--no-post",
    "--dry-run",
    "--no-captions",
    "--no-subs",
    "--sub-style",
    "--sub-lang",
    "--subtitle-source",
    "--covers",
    "--no-covers",
    "--profile",
    "--list-styles",
    "--links",
    "--source",
    "--post-due",
    "--post-now",
    "--queue-status",
    "--reset-gap",
    "--ignore",
    "--cleanup-posted",
    "--confirm-posted",
    "--retry-after-review",
    "--check-youtube",
    "--check-gemini",
    "-h",
    "--help",
)

PARTS_FLAGS = (
    "--mode",
    "--part-seconds",
    "--background",
    "--out",
    "--caption-file",
    "--subtitle-source",
    "--sub-style",
    "--sub-lang",
    "--no-subs",
    "--labels",
    "--dry-run",
    "--profile",
    "--help",
)

VALUE_FLAGS = {
    "--clips",
    "--auto-mode",
    "--min",
    "--max",
    "--out",
    "--limit",
    "--sub-style",
    "--sub-lang",
    "--subtitle-source",
    "--links",
    "--ignore",
    "--confirm-posted",
    "--retry-after-review",
    "--check-youtube",
    "--mode",
    "--part-seconds",
    "--background",
    "--caption-file",
}

VALUE_CANDIDATES = {
    "--auto-mode": ("content", "duration"),
    "--subtitle-source": ("auto", "source", "whisper"),
    "--mode": ("story", "number-only"),
    "--background": ("blur", "plain"),
    "--sub-style": ("hormozi", "clean", "yellow"),
}

def _matching(candidates: Sequence[str], current: str) -> list[str]:
    if not current:
        return list(dict.fromkeys(candidates))
    folded = current.casefold()
    return list(dict.fromkeys(
        candidate for candidate in candidates if candidate.casefold().startswith(folded)
    ))


def candidates(words: Sequence[str], index: int) -> list[str]:
    """Return candidates for a shell word vector and zero-based cursor index."""

    values = [str(word) for word in words]
    if not values:
        return list(COMMANDS) + list(PIPELINE_FLAGS)
    index = max(0, min(index, len(values)))
    current = values[index] if index < len(values) else ""
    args = values[1:] if values and values[0] in {"ziv", "ziv.sh"} else values
    args_index = max(0, index - 1) if values and values[0] in {"ziv", "ziv.sh"} else index
    before = args[:args_index]

    if not before:
        return _matching((*COMMANDS, *PIPELINE_FLAGS), current)

    command = before[0]
    if command == "completion":
        return _matching((*SHELLS, "--help"), current)
    if command == "doctor":
        return _matching(("dependencies", "deps", "youtube", "--help"), current)
    if command == "post":
        return _matching(("--due", "--post-due"), current)
    if command in {"parts", "number-parts", "number_only"}:
        if before[-1] in VALUE_FLAGS:
            return _matching(VALUE_CANDIDATES.get(before[-1], ()), current)
        return _matching(PARTS_FLAGS, current) if current.startswith("-") else []
    if command in {"help", "setup", "links", "channels", "source", "scan",
                   "queue", "queue-status", "styles"}:
        return []

    if before[-1] in VALUE_FLAGS:
        return _matching(VALUE_CANDIDATES.get(before[-1], ()), current)
    if command in {"make"} or current.startswith("-"):
        return _matching(PIPELINE_FLAGS, current)
    return []


def _bash_script() -> str:
    return r'''# Ziv completion for Bash. Install with: eval "$(ziv completion bash)"
_ziv_completion() {
    local -a words
    words=("${COMP_WORDS[@]}")
    mapfile -t COMPREPLY < <(command ziv __complete bash "$COMP_CWORD" "${words[@]}")
}
complete -o bashdefault -F _ziv_completion ziv
'''


def _zsh_script() -> str:
    return r'''#compdef ziv
# Ziv completion for Zsh. Install with: eval "$(ziv completion zsh)"
_ziv() {
    local -a reply
    reply=("${(@f)$(command ziv __complete zsh "$((CURRENT - 1))" "${words[@]}")}")
    (( ${#reply[@]} )) && compadd -- "${reply[@]}"
}
compdef _ziv ziv
'''


def _fish_script() -> str:
    return r'''# Ziv completion for Fish. Install with: ziv completion fish | source
function __ziv_complete
    set -l words (commandline -opc)
    set -l current (commandline -ct)
    set -a words "$current"
    if test (count $words) -eq 1; and test -z "$words[1]"
        set words ziv ""
    end
    ziv __complete fish (math (count $words) - 1) $words
end
complete -c ziv -a '(__ziv_complete)'
'''


def _powershell_script() -> str:
    return r'''# Ziv completion for PowerShell. Install by invoking this output once.
Register-ArgumentCompleter -CommandName ziv -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $words = @($commandAst.CommandElements | ForEach-Object { $_.Extent.Text })
    if ($words.Count -eq 0) { return }
    $index = $words.Count - 1
    & ziv __complete powershell $index @words 2>$null |
        Where-Object { $_ -like "$wordToComplete*" } |
        ForEach-Object {
            [System.Management.Automation.CompletionResult]::new(
                $_, $_, 'ParameterValue', $_)
        }
}
'''


def script(shell: str) -> str:
    """Render a native completion script for one supported shell."""

    if shell == "bash":
        return _bash_script()
    if shell == "zsh":
        return _zsh_script()
    if shell == "fish":
        return _fish_script()
    if shell == "powershell":
        return _powershell_script()
    raise ValueError(f"unsupported shell: {shell}")


def complete_command(args: Sequence[str]) -> int:
    """Handle the private completion backend without starting workflows."""

    if len(args) < 2 or args[0] not in SHELLS:
        return 1
    try:
        index = int(args[1])
    except ValueError:
        return 1
    for value in candidates(args[2:], index):
        print(value)
    return 0


__all__ = ["COMMANDS", "SHELLS", "candidates", "complete_command", "script"]
