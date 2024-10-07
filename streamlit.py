import streamlit as st
import requests
import os
import xml.etree.ElementTree as ET
import io
import zipfile
import shutil
import json
import tempfile

# Streamlit setup
st.title("Dynamic Keyboard Layout Maker for AAC")

# Enable or disable debugging
debugging = False

# Global variables
keyman_api_url = "https://api.keyman.com/search/2.0"

# Load the KVKS index JSON file
with open("kvks_index.json", "r") as f:
    kvks_index = json.load(f)


# Function to unzip the template.gridset file into a temporary directory
def unzip_template_gridset():
    temp_dir = tempfile.mkdtemp(prefix="template_gridset_")
    if os.path.exists("template.gridset"):
        with zipfile.ZipFile("template.gridset", "r") as zip_ref:
            zip_ref.extractall(temp_dir)
        if debugging:
            st.write(f"Template gridset unzipped to: {temp_dir}")
    else:
        st.error("template.gridset file not found.")
    return temp_dir  # Return the temporary directory path


# Function to search Keyman keyboards and filter out those not in kvks_index
def search_keyboards(query):
    params = {
        "q": f"l:{query}",  # Search for language name
        "f": 1,  # Make it JSON readable
    }
    response = requests.get(keyman_api_url, params=params)
    keyboards_data = response.json()

    # Filter keyboards to only include those present in the kvks_index
    if "keyboards" in keyboards_data:
        filtered_keyboards = [
            keyboard
            for keyboard in keyboards_data["keyboards"]
            if keyboard["id"] in kvks_index
        ]
        return filtered_keyboards
    return []


# Function to fetch KVKS file directly from GitHub
def fetch_kvks_file(github_link):
    raw_url = github_link.replace("https://github.com/", "https://raw.githubusercontent.com/").replace("/blob/", "/")
    response = requests.get(raw_url)
    if response.status_code == 200:
        return response.content
    else:
        return None


# Function to parse KVKS content and extract layer mappings
def parse_kvks_content(kvks_content):
    tree = ET.ElementTree(ET.fromstring(kvks_content))
    root = tree.getroot()

    layers_mapping = {}
    for layer in root.findall(".//layer"):
        shift_state = layer.get("shift", "")
        key_mappings = {key.get("vkey"): key.text or "" for key in layer.findall(".//key")}
        layers_mapping[shift_state] = key_mappings

    return layers_mapping


# A hack: Add CDATA for space and namespace in the XML string
def add_cdata_for_space_and_namespace(xml_str):
    xml_str = xml_str.replace("<Caption> </Caption>", "<Caption><![CDATA[ ]]></Caption>")
    if "xmlns:xsi" not in xml_str:
        xml_str = xml_str.replace("<Grid>", '<Grid xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">')
    return xml_str


# Function to modify grid XML file with key mappings from the respective layer
def modify_grid_xml_with_layer(grid_xml_path, key_mappings, placeholder="*"):
    try:
        if debugging:
            st.write(f"Modifying grid: {grid_xml_path} with key mappings: {key_mappings}")

        tree = ET.parse(grid_xml_path)
        root = tree.getroot()
        replacements_count = 0

        for cell in root.findall(".//Cell"):
            caption_element = cell.find("Content/CaptionAndImage/Caption")
            command_elements = cell.findall(".//Commands/Command")

            if caption_element is not None:
                current_caption = caption_element.text.strip() if caption_element.text else ""
                vkey = f"K_{current_caption.upper()}"

                if vkey in key_mappings:
                    new_character = key_mappings[vkey] or placeholder
                    caption_element.text = new_character

                    for command in command_elements:
                        for param in command.findall("Parameter"):
                            if param.get("Key") == "letter":
                                param.text = new_character

                    replacements_count += 1

        xml_output = io.StringIO()
        tree.write(xml_output, encoding="unicode", xml_declaration=False)
        xml_str = xml_output.getvalue()
        updated_xml_str = add_cdata_for_space_and_namespace(xml_str)

        with open(grid_xml_path, "w", encoding="utf-8") as f:
            f.write(updated_xml_str)

        if debugging:
            st.write(f"Modified {replacements_count} keys in {grid_xml_path}")

    except ET.ParseError as e:
        st.error(f"XML Parsing Error: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")


# Modify all layers of the gridset based on the layers in KVKS
def modify_gridset_with_kvks_layers(kvks_mappings, gridset_base_dir):
    folder_to_layer_mapping = {
        "default": "", "shift": "S", "ctrl": "C", "shift_ctrl": "SC", 
        "alt": "RA", "shift_alt": "SRA", "ctrl_alt": "CRA", "shift_ctrl_alt": "SCA"
    }

    for folder, layer in folder_to_layer_mapping.items():
        grid_xml_path = os.path.join(gridset_base_dir, "Grids", folder, "grid.xml")
        if os.path.exists(grid_xml_path):
            key_mappings = kvks_mappings.get(layer, {})
            if debugging:
                st.write(f"Modifying {grid_xml_path} with layer: {layer}")
            modify_grid_xml_with_layer(grid_xml_path, key_mappings)


# Main application logic
if "keyboards" not in st.session_state:
    st.session_state.keyboards = []
if "selected_keyboard" not in st.session_state:
    st.session_state.selected_keyboard = None

gridset_dir = unzip_template_gridset()  # Unzip template to a temporary directory

st.write(
    "This tool allows you to create a template Gridset for the Grid3 with a keyboard layout for a given language. "
    "Keyboards are based on [Keyman](http://keyman.com). You may find 'basic' versions better for your use.\n\n"
    "**Note:** Some keyboards require right-to-left input, so ensure your language settings are configured correctly. "
    "You may also need to use a suitable font to display certain characters accurately."
)

language_query = st.text_input("Enter a language to search for:")

if st.button("Search Keyboards"):
    if language_query:
        filtered_keyboards = search_keyboards(language_query)
        if filtered_keyboards:
            st.session_state.keyboards = filtered_keyboards
        else:
            st.error("No keyboards found for the entered language in the KVKS index.")
    else:
        st.error("Please enter a language to search.")

if st.session_state.keyboards:
    selected_keyboard = st.selectbox(
        "Choose a keyboard",
        st.session_state.keyboards,
        format_func=lambda k: f"{k['name']} ({k['id']})",
    )
    st.session_state.selected_keyboard = selected_keyboard

if st.session_state.selected_keyboard and st.button("Download and Process Keyboard"):
    keyboard_choice = st.session_state.selected_keyboard
    keyboard_id = keyboard_choice["id"]

    if keyboard_id in kvks_index:
        github_link = kvks_index[keyboard_id]
        kvks_content = fetch_kvks_file(github_link)
        if kvks_content:
            keyman_mappings = parse_kvks_content(kvks_content)
            if debugging:
                st.write(f"Extracted key mappings from KVKS: {keyman_mappings}")

            modify_gridset_with_kvks_layers(keyman_mappings, gridset_dir)

            try:
                modified_gridset_io = io.BytesIO()
                with zipfile.ZipFile(modified_gridset_io, "w") as zipf:
                    for root, dirs, files in os.walk(gridset_dir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            relative_path = os.path.relpath(full_path, gridset_dir)
                            zipf.write(full_path, relative_path)

                modified_gridset_io.seek(0)
                filename = f"{keyboard_id}.gridset"
                if debugging:
                    st.write(f"Successfully created zip file: {filename}")
                st.download_button("Download Modified Gridset", modified_gridset_io.getvalue(), filename)
            except Exception as e:
                st.error(f"Failed to create zip file: {e}")
        else:
            st.error(f"Failed to fetch KVKS file from {github_link}")
    else:
        st.error(f"Keyboard {keyboard_id} not found in KVKS index.")

    # Delete the temporary directory after processing
    shutil.rmtree(gridset_dir, ignore_errors=True)