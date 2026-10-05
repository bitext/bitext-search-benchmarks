import importlib.util
import io
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("benchmark", ROOT / "scripts/benchmark.py")
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class PluginTests(unittest.TestCase):
    def test_plugin_directory_has_one_installable_archive_without_private_paths(self):
        archive = benchmark.plugin_archive()
        self.assertEqual(archive.parent, ROOT / "plugin")
        with zipfile.ZipFile(archive) as plugin:
            self.assertIn("stable-plugin-descriptor.properties", plugin.namelist())
            descriptor = plugin.read("stable-plugin-descriptor.properties").decode("utf-8")
            self.assertIn("name=bitext-java-english", descriptor)
            self.assertIn("version=1.0.0", descriptor)
            self.assertIn("elasticsearch.version=9.5.4", descriptor)
            self.assertIn("bitext_java_english", plugin.read("named_components.json").decode("utf-8"))
            self.assertFalse(any("private/" in name for name in plugin.namelist()))
            for member in plugin.namelist():
                if member.endswith(".jar"):
                    with zipfile.ZipFile(io.BytesIO(plugin.read(member))) as jar:
                        self.assertFalse(any("private/" in name for name in jar.namelist()))


if __name__ == "__main__":
    unittest.main()
