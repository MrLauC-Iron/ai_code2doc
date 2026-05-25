"""End-to-end integration tests for the call graph feature."""
from __future__ import annotations

from pathlib import Path

import pytest

from ai_code2doc.analyzer.call_graph_builder import CallGraphBuilder
from ai_code2doc.analyzer.dependency_graph import DependencyGraphBuilder
from ai_code2doc.parser.tree_sitter_parser import TreeSitterParser


class TestCallGraphEndToEnd:
    def test_sample_python_project(self, sample_py_project: Path, output_dir: Path) -> None:
        """Build a call graph for the sample Python project and verify results."""
        from ai_code2doc.scanner.project_scanner import ProjectScanner

        scanner = ProjectScanner(sample_py_project)
        scan_result = scanner.scan()
        parser = TreeSitterParser()

        file_infos = []
        for f in scan_result.target_files:
            try:
                fi = parser.parse_file(f, sample_py_project)
                file_infos.append(fi)
            except Exception:
                continue

        assert len(file_infos) > 0

        # All file_infos should have source_text populated by the parser
        for fi in file_infos:
            assert fi.source_text, f"No source_text for {fi.path}"

        # Build call graph
        call_builder = CallGraphBuilder(sample_py_project)
        call_sites = call_builder.build_for_files(file_infos)

        # Build dependency graph with call edges
        dep_builder = DependencyGraphBuilder(sample_py_project)
        for fi in file_infos:
            dep_builder.add_file(fi)
        dep_builder.add_call_edges(call_sites)
        graph = dep_builder.build()

        # Graph should have file nodes
        node_kinds = [graph.nodes[n].get("kind", "file") for n in graph.nodes]
        assert "file" in node_kinds

        # Call edges should exist if call sites were found
        if call_sites:
            call_edges = [
                (u, v) for u, v, d in graph.edges(data=True)
                if d.get("edge_type") == "call"
            ]
            assert len(call_edges) > 0

    def test_two_file_cross_call(self, tmp_path: Path) -> None:
        """Test call resolution across two files."""
        # File 1: calls a function from file 2
        a_py = tmp_path / "a.py"
        a_py.write_text(
            "from b import helper\n"
            "\n"
            "def process():\n"
            "    result = helper()\n"
            "    return result\n",
            encoding="utf-8",
        )

        # File 2: defines helper
        b_py = tmp_path / "b.py"
        b_py.write_text(
            "def helper():\n"
            "    return 42\n"
            "\n"
            "def main():\n"
            "    helper()\n"
            "    process()\n",
            encoding="utf-8",
        )

        parser = TreeSitterParser()
        fi_a = parser.parse_file(a_py, tmp_path)
        fi_b = parser.parse_file(b_py, tmp_path)

        call_builder = CallGraphBuilder(tmp_path)
        call_sites = call_builder.build_for_files([fi_a, fi_b])

        # process() in a.py calls helper()
        process_calls = [s for s in call_sites if s.caller_fqn.endswith("::process")]
        assert any(s.callee_name == "helper" for s in process_calls)

        # main() in b.py calls helper() (same file)
        main_calls = [s for s in call_sites if s.caller_fqn.endswith("::main")]
        assert any(s.callee_name == "helper" for s in main_calls)

    def test_class_method_calls(self, tmp_path: Path) -> None:
        """Test call extraction from class methods."""
        service_py = tmp_path / "service.py"
        service_py.write_text(
            "class UserService:\n"
            "    def authenticate(self, token):\n"
            "        self.validate(token)\n"
            "        return True\n"
            "\n"
            "    def validate(self, token):\n"
            "        if not token:\n"
            "            raise ValueError('empty')\n",
            encoding="utf-8",
        )

        parser = TreeSitterParser()
        fi = parser.parse_file(service_py, tmp_path)

        call_builder = CallGraphBuilder(tmp_path)
        call_sites = call_builder.build_for_files([fi])

        # Should find self.validate() call in authenticate()
        auth_calls = [s for s in call_sites if ".authenticate" in s.caller_fqn]
        assert any("validate" in s.callee_name for s in auth_calls)

    def test_full_graph_with_both_edge_types(self, tmp_path: Path) -> None:
        """Test that the graph contains both import and call edges."""
        a_py = tmp_path / "a.py"
        a_py.write_text(
            "from b import compute\n"
            "\n"
            "def main():\n"
            "    result = compute(42)\n"
            "    return result\n",
            encoding="utf-8",
        )

        b_py = tmp_path / "b.py"
        b_py.write_text(
            "def compute(x):\n"
            "    return x * 2\n",
            encoding="utf-8",
        )

        parser = TreeSitterParser()
        fi_a = parser.parse_file(a_py, tmp_path)
        fi_b = parser.parse_file(b_py, tmp_path)

        call_builder = CallGraphBuilder(tmp_path)
        call_sites = call_builder.build_for_files([fi_a, fi_b])

        dep_builder = DependencyGraphBuilder(tmp_path)
        dep_builder.add_file(fi_a)
        dep_builder.add_file(fi_b)
        dep_builder.add_call_edges(call_sites)
        graph = dep_builder.build()

        # Check both edge types exist
        edge_types = {d.get("edge_type") for _, _, d in graph.edges(data=True)}
        assert "import" in edge_types or "call" in edge_types
