import tempfile
import unittest
from pathlib import Path

from core.assistant_platform import pc_specs

RAW = {
    "cpu": {"Name": "AMD Ryzen 9 7900X 12-Core Processor   ", "NumberOfCores": 12, "NumberOfLogicalProcessors": 24, "MaxClockSpeed": 4701},
    "ram": [{"Capacity": 17179869184, "ConfiguredClockSpeed": 5600, "Manufacturer": "A-DATA", "PartNumber": "AX5U  "}] * 2,
    "gpus": [{"Name": "AMD Radeon(TM) Graphics", "DriverVersion": "1"},
             {"Name": "NVIDIA GeForce RTX 4070 Ti SUPER", "DriverVersion": "32", "CurrentHorizontalResolution": 2560,
              "CurrentVerticalResolution": 1440, "CurrentRefreshRate": 180}],
    "nvidia": [{"name": "NVIDIA GeForce RTX 4070 Ti SUPER", "vramMb": "16376", "driver": "617.14", "powerLimitW": "285.00"}],
    "board": {"Manufacturer": "ASUSTeK COMPUTER INC.", "Product": "PRIME B650M-A AX6 II"},
    "disks": {"FriendlyName": "ADATA LEGEND 800 GOLD", "MediaType": "SSD", "BusType": "NVMe", "Size": 2000398934016},
    "volumes": [{"DriveLetter": "C", "FileSystemLabel": "", "Size": 2000000000000, "SizeRemaining": 860000000000}],
    "os": {"Caption": "Microsoft Windows 11 Pro", "BuildNumber": "26300"},
}


class PcSpecsTest(unittest.TestCase):
    def test_specs_are_tidied_cached_and_summarised(self):
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "s.json"
            data = pc_specs.specs(query=lambda: calls.append(1) or RAW, path=path)
            pc_specs.specs(query=lambda: calls.append(1) or RAW, path=path)
            self.assertEqual(len(calls), 1)  # cached for a day
            self.assertEqual((data["ram"]["totalGb"], data["ram"]["kind"]), (32, "DDR5"))
            self.assertEqual(data["gpus"][1]["vramGb"], 16.0)
            self.assertTrue(data["gpus"][0]["integrated"])
            self.assertEqual(data["board"], "ASUSTeK PRIME B650M-A AX6 II")
            text = pc_specs.summary(data)
            self.assertIn("NVIDIA GeForce RTX 4070 Ti SUPER, 16 GB VRAM, driver 617.14, drives a 2560x1440 @ 180 Hz display.", text)
            self.assertIn("RAM: 32 GB DDR5 at 5600 MT/s", text)
            self.assertIn("C: 801 of 1863 GB free", text)
            failing = pc_specs.specs(refresh=True, query=lambda: 1 / 0, path=path)
            self.assertEqual(failing["cpu"]["cores"], 12)  # keeps the last good read

    def test_context_only_for_pc_questions(self):
        self.assertIsNone(pc_specs.pc_context("remind me to call mom"))
        self.assertIsNotNone(pc_specs._TOPIC.search("can my pc run Cyberpunk"))
        self.assertIsNotNone(pc_specs._TOPIC.search("how much VRAM do I have"))


if __name__ == "__main__":
    unittest.main()
