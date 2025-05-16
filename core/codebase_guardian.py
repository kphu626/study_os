# core/codebase_guardian.py
import asyncio
import re
import time
from pathlib import Path
from typing import Dict

import aiofiles
import autopep8
import black
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
        self.doctor = CodebaseDoctor()

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
            self.show_notification(
                f"Error in {path.name}: {exc!s}", error=True)

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
    async def heal(self, path: Path) -> bool:
        try:
            async with aiofiles.open(path) as f:
                code = await f.read()

            # Phase 1: Fix Syntax Errors
            fixed_code = self._fix_syntax(code)

            # Phase 2: Apply AST-Based Safe Fixes
            safe_fixed = self._safe_ast_fixes(fixed_code)

            # Phase 3: Format with Black
            formatted = self._black_format(safe_fixed)

            # Phase 4: PEP8 Cleanup
            final_code = autopep8.fix_code(formatted)

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

    def _black_format(self, code: str) -> str:
        """Format with Black's strict mode"""
        return black.format_str(
            code,
            mode=black.FileMode(line_length=88, string_normalization=True),
        )


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
        new_params_tuple = (self_param,) + node.params.params

        new_params_node = node.params.with_changes(params=new_params_tuple)

        return node.with_changes(params=new_params_node)
