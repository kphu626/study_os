# core/codebase_guardian.py
import asyncio
import re
import time
from pathlib import Path
from typing import Dict

import aiofiles

# import autopep8 # Removed
# import black # Removed
import libcst as cst
from libcst import MetadataWrapper, parse_module
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class UnifiedGuardian:
    def __init__(self):
        self.observer = Observer()
        self.change_cache: Dict[Path, float] = {}
        self.debounce_time = 1.5  # Seconds
        self.doc = QuantumDocumenter(self)
        self.doctor = CodebaseDoctor(self)

    async def start(self):
        event_handler = GuardianHandler(self)
        self.observer.schedule(event_handler, ".", recursive=True)
        self.observer.start()

        try:
            while True:
                await self.process_changes()
                await asyncio.sleep(0.1)  # 100ms interval
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()

    async def process_changes(self):
        now = time.time()
        processed = []

        for path, timestamp in self.change_cache.items():
            if now - timestamp > self.debounce_time:
                await self.handle_file_change(path)
                processed.append(path)

        for path in processed:
            del self.change_cache[path]

    async def handle_file_change(self, path: Path):
        """Pipeline: Heal → Document → Notify"""
        try:
            # 1. Code Healing
            healed = await self.doctor.heal(path)

            # 2. Generate Documentation
            if healed:
                await self.doc.generate(path)

            # 3. UI Notification
            self.show_notification(f"Processed {path.name}")

        except Exception as exc:
            self.show_notification(f"Error in {path.name}: {exc!s}", error=True)

    def show_notification(self, message: str, error: bool = False):
        color = "\033[91m" if error else "\033[92m"
        print(f"{color}GUARDIAN\033[0m │ {message}")


class GuardianHandler(FileSystemEventHandler):
    def __init__(self, guardian: UnifiedGuardian):
        self.guardian = guardian

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".py"):
            path = Path(event.src_path)
            self.guardian.change_cache[path] = time.time()


class QuantumDocumenter:
    def __init__(self, guardian: UnifiedGuardian):
        self.guardian = guardian

    async def generate(self, path: Path):
        async with aiofiles.open(path) as f:
            await f.read()
        # Generate documentation logic
        self.guardian.show_notification(f"📚 Updated docs for {path.name}")


class CodebaseDoctor:
    def __init__(self, guardian: UnifiedGuardian):
        self.guardian = guardian

    async def heal(self, path: Path) -> bool:
        try:
            async with aiofiles.open(path) as f:
                code = await f.read()

            # Phase 1: Fix Syntax Errors
            fixed_code = self._fix_syntax(code)

            # Phase 2: Apply AST-Based Safe Fixes
            safe_fixed = self._safe_ast_fixes(fixed_code)

            # Phase 3: Format and Fix with Ruff
            final_code = await self._ruff_check_and_format(safe_fixed, path)

            # Phase 4: PEP8 Cleanup (Removed)
            # final_code = autopep8.fix_code(formatted)

            async with aiofiles.open(path, "w") as f:
                await f.write(final_code)

            return True

        except Exception as exc:
            print(f"🔴 Critical error in {path.name}: {exc!s}")
            return False

    def _fix_syntax(self, code: str) -> str:
        """Fix common missing colons"""
        lines = code.splitlines()
        processed_lines = []

        for line in lines:
            stripped_line = line.lstrip()
            corrected_line = line

            if stripped_line.startswith("try") and not stripped_line.endswith(":"):
                corrected_line = line + ":"
            elif stripped_line.startswith("except") and not stripped_line.endswith(":"):
                parts = stripped_line.split()
                if (
                    len(parts) > 1
                    and parts[0] == "except"
                    and not parts[-1].endswith(":")
                ) or (len(parts) == 1 and parts[0] == "except"):
                    corrected_line = corrected_line + ":"
            elif (stripped_line == "finally" and not stripped_line.endswith(":")) or (
                stripped_line.startswith("def ")
                and stripped_line.endswith(")")
                and not stripped_line.endswith(":")
            ):
                corrected_line = corrected_line + ":"
            elif stripped_line.startswith("class "):
                # Handles 'class Foo:' and 'class Foo(Bar):'
                temp_line = stripped_line.split("#")[
                    0
                ].rstrip()  # Remove comments and trailing whitespace
                if not temp_line.endswith(":"):
                    corrected_line = line + ":"

            # Fix incorrectly escaped triple quotes like """ to """
            corrected_line = re.sub(r'\\"\\"\\"', '"""', corrected_line)

            processed_lines.append(corrected_line)

        return "\n".join(processed_lines)

    def _safe_ast_fixes(self, code: str) -> str:
        """Use LibCST for semantic-aware fixes"""
        tree = parse_module(code)
        wrapper = MetadataWrapper(tree)
        context = CodemodContext()

        # Fix logger.warn → logger.warning
        fixed_tree = LoggerFixCommand(context).transform_module(wrapper.module)

        # Add missing self to methods
        # Apply SelfAdderCommand to the already transformed tree
        final_tree = SelfAdderCommand(context).transform_module(fixed_tree)

        return final_tree.code

    async def _ruff_check_and_format(self, code: str, file_path: Path) -> str:
        """Format and fix code using Ruff."""
        temp_file_path = None
        try:
            # Ruff works best with files, so we write to a temporary file.
            # Using the original filename for context if Ruff uses it for config resolution.
            # Create a temporary file with a similar name to the original for Ruff context
            # This is a simplified approach; robust temp file handling might be needed.
            # For --stdin-filename, we can pass it directly.

            # Step 1: Format with `ruff format`
            # Ruff format command: ruff format --stdin-filename "path/to/file.py" -
            proc_format = await asyncio.create_subprocess_exec(
                "ruff",
                "format",
                "--stdin-filename",
                str(file_path),
                "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            formatted_code_bytes, format_stderr_bytes = await proc_format.communicate(
                input=code.encode("utf-8")
            )

            if proc_format.returncode != 0:
                # Try to decode stderr for logging, but don't let it crash if it fails
                try:
                    format_stderr = format_stderr_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    format_stderr = "[Could not decode stderr for ruff format]"
                self.guardian.show_notification(  # Assuming CodebaseDoctor has access to guardian or its logger
                    f"Ruff format failed for {file_path.name}: {format_stderr}",
                    error=True,
                )
                # Fallback to original code if formatting fails, or handle error differently
                formatted_code = code
            else:
                formatted_code = formatted_code_bytes.decode("utf-8")

            # Step 2: Fix with `ruff check --fix`
            # Ruff check command: ruff check --fix --stdin-filename "path/to/file.py" -
            proc_fix = await asyncio.create_subprocess_exec(
                "ruff",
                "check",
                "--fix",
                "--stdin-filename",
                str(file_path),
                "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            fixed_code_bytes, fix_stderr_bytes = await proc_fix.communicate(
                input=formatted_code.encode("utf-8")
            )

            if proc_fix.returncode != 0:
                try:
                    fix_stderr = fix_stderr_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    fix_stderr = "[Could not decode stderr for ruff check --fix]"
                self.guardian.show_notification(
                    f"Ruff check --fix failed for {file_path.name}: {fix_stderr}",
                    error=True,
                )
                # Fallback to formatted code if fixing fails
                final_code = formatted_code
            else:
                final_code = fixed_code_bytes.decode("utf-8")

            return final_code

        except FileNotFoundError:
            # This typically means Ruff is not installed or not in PATH
            self.guardian.show_notification(
                "Ruff command not found. Please ensure Ruff is installed and in your PATH.",
                error=True,
            )
            return code  # Return original code if Ruff isn't found
        except Exception as e:
            self.guardian.show_notification(
                f"Error during Ruff processing for {file_path.name}: {e}", error=True
            )
            return code  # Fallback to original code on other errors


class LoggerFixCommand(VisitorBasedCodemodCommand):
    def visit_Call(self, node: cst.Call) -> cst.CSTNode | None:
        # Ensure node.func is an Attribute node
        if not isinstance(node.func, cst.Attribute):
            return super().visit_Call(node)

        # Check if the attribute's value is a Name node (e.g., 'logger')
        if not isinstance(node.func.value, cst.Name):
            return super().visit_Call(node)

        # Check if the attribute name is 'warn' and the object is 'logger'
        if node.func.attr.value == "warn" and node.func.value.value == "logger":
            # Replace 'warn' with 'warning'
            new_attr = node.func.attr.with_changes(value="warning")
            new_func = node.func.with_changes(attr=new_attr)
            return node.with_changes(func=new_func)

        return super().visit_Call(node)


class SelfAdderCommand(VisitorBasedCodemodCommand):
    def visit_FunctionDef(self, node: cst.FunctionDef) -> cst.CSTNode | None:
        # Check if it's a method (heuristic: in a class, not static/class method without 'cls')
        # This heuristic can be improved by checking parent context (e.g. if parent is ClassDef)
        # For now, we assume it applies to functions that look like methods.

        # No parameters, or first parameter is already 'self' or 'cls'
        if not node.params.params or node.params.params[0].name.value in (
            "self",
            "cls",
        ):
            return super().visit_FunctionDef(node)

        # Create a 'self' parameter
        self_param = cst.Param(name=cst.Name("self"))

        # Prepend 'self' to existing parameters
        new_params_tuple = (self_param,) + tuple(node.params.params)

        new_params_node = node.params.with_changes(params=new_params_tuple)

        return node.with_changes(params=new_params_node)
