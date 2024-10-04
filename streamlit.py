import streamlit as st
import requests
import zipfile
import os
import xml.etree.ElementTree as ET
import re
import io
import shutil
import json

# Streamlit setup
st.title("Dynamic Keyboard Layout Maker for AAC")

# Global variables
keyman_api_url = "https://api.keyman.com/search/2.0"
template_gridset_dir = "unzipped_template_gridset"

# Load the KVKS index JSON file
with open("kvks_index.json", "r") as f:
    kvks_index = json.load(f)


# Function to unzip the template.gridset file (only once)
def unzip_template_gridset():
    if not os.path.exists(template_gridset_dir):
        os.makedirs(template_gridset_dir, exist_ok=True)
        with zipfile.ZipFile("template.gridset", "r") as zip_ref:
            zip_ref.extractall(template_gridset_dir)
        # st.write("Template gridset unzipped.")


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
    # Convert the GitHub URL to a raw file URL
    raw_url = github_link.replace(
        "https://github.com/", "https://raw.githubusercontent.com/"
    )
    raw_url = raw_url.replace("/blob/", "/")

    # Fetch the raw KVKS file content
    response = requests.get(raw_url)
    if response.status_code == 200:
        return response.content
    else:
        return None


# Function to parse KVKS content
def parse_kvks_content(kvks_content):
    tree = ET.ElementTree(ET.fromstring(kvks_content))
    root = tree.getroot()

    key_mappings = {}

    for layer in root.findall(".//layer"):
        for key in layer.findall(".//key"):
            vkey = key.get("vkey")
            value = key.text or ""

            # Map the virtual key (vkey) to the corresponding value
            key_mappings[vkey] = value

    return key_mappings


# A hack: Add CDATA for space and namespace in the XML string
def add_cdata_for_space_and_namespace(xml_str):
    xml_str = xml_str.replace(
        "<Caption> </Caption>", "<Caption><![CDATA[ ]]></Caption>"
    )
    if "xmlns:xsi" not in xml_str:
        xml_str = xml_str.replace(
            "<Grid>", '<Grid xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        )
    return xml_str


# Function to check if the cell is for the spacebar key
def is_spacebar_key(command_elements):
    for command in command_elements:
        if command.get("ID") == "Action.Space":
            return True
    return False


# Function to modify gridset XML with extracted mappings
def modify_gridset_with_keyboard_mappings(keyman_mappings, placeholder="*"):
    try:
        modified_dir = "modified_gridset"
        shutil.copytree(template_gridset_dir, modified_dir, dirs_exist_ok=True)

        # Normalize keyman mappings for case-insensitive matching
        keyman_mappings = {k.lower(): v for k, v in keyman_mappings.items()}

        # Debug: Print out key mappings to ensure they're correct
        # st.write(f"Keyman Mappings: {keyman_mappings}")

        # Counter for replacements
        replacements_count = 0

        for foldername, _, filenames in os.walk(modified_dir):
            for filename in filenames:
                if filename == "grid.xml":
                    # print(f"Processing {filename}")
                    xml_path = os.path.join(foldername, filename)

                    # Parse the existing XML file
                    tree = ET.parse(xml_path)
                    root = tree.getroot()

                    for cell in root.findall(".//Cell"):
                        caption_element = cell.find("Content/CaptionAndImage/Caption")
                        command_elements = cell.findall(".//Commands/Command")

                        # Get the current caption from the XML
                        current_caption = (
                            caption_element.text.strip().lower()
                            if caption_element is not None and caption_element.text
                            else ""
                        )

                        # Debug: Print current caption from XML
                        # print(f"Current Caption in XML: {current_caption}")

                        # Handle caption modifications but avoid replacing the "spacebar" key
                        if is_spacebar_key(command_elements):
                            # print("Skipping modification for spacebar key.")
                            continue

                        # Ensure the vkey (from the KVKS) is mapped to the correct character
                        vkey = f"k_{current_caption}".lower()  # Convert to lowercase

                        if caption_element is not None:
                            if vkey in keyman_mappings:
                                new_character = keyman_mappings[vkey]

                                # Debug: Print the matched vkey and new character
                                # print(
                                #    f"Matched vkey: {vkey}, New character: {new_character}"
                                # )

                                if current_caption == "space":
                                    # For 'space', we will use CDATA for space
                                    caption_element.text = " "
                                else:
                                    # Use the placeholder if mapping results in an empty string
                                    caption_element.text = new_character or placeholder
                                    replacements_count += 1

                            elif current_caption == "":
                                # If no mapping and caption is empty, replace with a placeholder
                                caption_element.text = placeholder

                        # Handle command parameter modifications (if applicable)
                        if command_elements:
                            for command in command_elements:
                                parameter_elements = command.findall("Parameter")
                                for param in parameter_elements:
                                    if param.get("Key") == "letter":
                                        if vkey in keyman_mappings:
                                            param.text = keyman_mappings[vkey]
                                            replacements_count += 1
                                            # print(
                                            #     f"Replaced '{current_caption}' with '{param.text}'"
                                            # )

                    # Write changes to a string instead of a file
                    xml_output = io.StringIO()
                    tree.write(xml_output, encoding="unicode", xml_declaration=False)

                    # Modify the XML output string to inject CDATA and ensure the namespace
                    xml_str = xml_output.getvalue()
                    updated_xml_str = add_cdata_for_space_and_namespace(xml_str)

                    # Save the updated XML back to the file
                    with open(xml_path, "w", encoding="utf-8") as f:
                        f.write(updated_xml_str)

        # Log results
        # st.write(f"Total characters replaced: {replacements_count}")

        # Repack the modified gridset into a zip file
        modified_gridset_io = io.BytesIO()
        with zipfile.ZipFile(modified_gridset_io, "w") as zipf:
            for root, dirs, files in os.walk(modified_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, modified_dir)
                    zipf.write(full_path, relative_path)

        shutil.rmtree(modified_dir)
        modified_gridset_io.seek(0)

        return modified_gridset_io

    except ET.ParseError as e:
        st.error(f"XML Parsing Error: {e}")
        return None

    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None


# Initialize session state variables
if "keyboards" not in st.session_state:
    st.session_state.keyboards = []
if "selected_keyboard" not in st.session_state:
    st.session_state.selected_keyboard = None

# Unzip the template.gridset (only once)
unzip_template_gridset()

st.write(
    "This tool allows you to create a template Gridset for the Grid3 with a keyboard layout for a given language. Keyboards are based on http://keyman.com You may find 'basic' versions better for your use. Please note we dont currently have shifted/ctrl states etc."
)

# UI: Search for a language
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

# Show the dropdown if keyboards are found
if st.session_state.keyboards:
    selected_keyboard = st.selectbox(
        "Choose a keyboard",
        st.session_state.keyboards,
        format_func=lambda k: f"{k['name']} ({k['id']})",
    )
    st.session_state.selected_keyboard = selected_keyboard

# Check if a keyboard has been selected
if st.session_state.selected_keyboard and st.button("Download and Process Keyboard"):
    keyboard_choice = st.session_state.selected_keyboard
    keyboard_id = keyboard_choice["id"]

    if keyboard_id in kvks_index:
        # Fetch and parse KVKS file
        github_link = kvks_index[keyboard_id]
        kvks_content = fetch_kvks_file(github_link)
        if kvks_content:
            keyman_mappings = parse_kvks_content(kvks_content)
            # st.write(f"Extracted key mappings from KVKS: {keyman_mappings}")

            modified_gridset = modify_gridset_with_keyboard_mappings(keyman_mappings)
            if modified_gridset:
                filename = f"{keyboard_id}.gridset"
                st.download_button(
                    "Download Modified Gridset", modified_gridset.getvalue(), filename
                )
        else:
            st.error(f"Failed to fetch KVKS file.{github_link}")
    else:
        st.error(f"Keyboard {keyboard_id} not found in KVKS index.")
