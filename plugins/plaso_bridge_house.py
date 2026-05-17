# plugins/plaso_bridge_house.py
PLUGIN_NAME = "Plaso Run + DB Correlate"
PLUGIN_CATEGORY = "Timeline"
PLUGIN_TARGET = "enterprise"
PLUGIN_DEFAULT_ENABLED = False

def run(output_dir, context):
    print(f"[*] Running Plaso + Genesis DB correlation -> {output_dir}")
    pass
