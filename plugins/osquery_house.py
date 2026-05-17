# plugins/osquery_house.py
PLUGIN_NAME = "osquery Snapshot"
PLUGIN_CATEGORY = "Live State"
PLUGIN_TARGET = "enterprise"
PLUGIN_DEFAULT_ENABLED = False

def run(output_dir, context):
    print(f"[*] Taking osquery live state snapshot -> {output_dir}")
    pass
