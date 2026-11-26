"""检查项目源码中类、函数和方法的职责说明，输出可读性核对结果。"""

import ast
from pathlib import Path


def missing_docstrings(path: Path) -> list[str]:
    """通过语法树定位没有职责文档字符串的定义。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    definitions = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    return [
        f"{path.name}:{node.lineno} {node.name}"
        for node in ast.walk(tree)
        if isinstance(node, definitions) and not ast.get_docstring(node)
    ]


def main() -> None:
    """检查业务代码与脚本，缺少说明时让质量检查失败。"""
    project = Path(__file__).resolve().parents[1]
    paths = sorted((project / "backend").rglob("*.py"))
    paths += sorted((project / "scripts").glob("*.py"))
    missing = [item for path in paths for item in missing_docstrings(path)]
    if missing:
        raise SystemExit("Missing responsibility docstrings:\n" + "\n".join(missing))
    print(f"Readability check passed: {len(paths)} Python files; all definitions documented.")


if __name__ == "__main__":
    main()
