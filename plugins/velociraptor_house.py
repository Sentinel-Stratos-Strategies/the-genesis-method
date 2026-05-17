# plugins/velociraptor_house.py
PLUGIN_NAME = "Velociraptor Artifact Collection"
PLUGIN_CATEGORY = "Endpoint Scale"
PLUGIN_TARGET = "enterprise"
PLUGIN_DEFAULT_ENABLED = False

def run(output_dir, context):
    print(f"[*] Running Velociraptor VQL collection -> {output_dir}")
    pass
