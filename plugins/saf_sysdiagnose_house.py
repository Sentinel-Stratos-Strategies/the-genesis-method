# plugins/saf_sysdiagnose_house.py
import os
import subprocess

PLUGIN_NAME = "SAF Sysdiagnose (manifest-backed)"
PLUGIN_CATEGORY = "Sysdiagnose"
PLUGIN_TARGET = "enterprise"
PLUGIN_DEFAULT_ENABLED = False

def run(output_dir, context):
    """
    Legacy hook: SAF runs via genesis_core_modules.json → bash tools/sysdiagnose_saf_run.sh.
    """
    print(f"[*] SAF: enable plugin saf_sysdiagnose_enterprise in the WebUI or run:")
    print(f"    bash tools/sysdiagnose_saf_run.sh <evidence_dir> {output_dir}/_SAF")
