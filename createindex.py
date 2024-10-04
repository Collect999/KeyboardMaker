import os
import json
import xml.etree.ElementTree as ET


# git clone https://github.com/keymanapp/keyboards.git
# then run this
def create_kvks_index(base_dir):
    kvks_index = {}

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".kvks"):
                kvks_path = os.path.join(root, file)

                # Parse the .kvks file to get the keyboard name (kbdname)
                tree = ET.parse(kvks_path)
                root_elem = tree.getroot()

                kbdname_elem = root_elem.find(".//kbdname")
                if kbdname_elem is not None:
                    kbdname = kbdname_elem.text
                    # Create the link to the file in the GitHub repo
                    relative_path = os.path.relpath(kvks_path, base_dir)
                    github_link = f"https://github.com/keymanapp/keyboards/blob/master/{relative_path}"

                    # Add to the index
                    kvks_index[kbdname] = github_link

    return kvks_index


# Generate the index
base_directory = "keyboards"
kvks_index = create_kvks_index(base_directory)

# Save to a JSON file for later use
with open("kvks_index.json", "w") as f:
    json.dump(kvks_index, f, indent=4)

print("KVKS Index created!")
