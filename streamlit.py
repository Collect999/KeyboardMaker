import streamlit as st
import requests
import zipfile
import os
import xml.etree.ElementTree as ET
import re
import io
import shutil

# Streamlit setup
st.title("Dynamic Keyboard Layout Modifier")

# Global variables
keyman_api_url = "https://api.keyman.com/search/2.0"
template_gridset_dir = "unzipped_template_gridset"


# Function to unzip the template.gridset file (only once)
def unzip_template_gridset():
    if not os.path.exists(template_gridset_dir):
        os.makedirs(template_gridset_dir, exist_ok=True)
        with zipfile.ZipFile("template.gridset", "r") as zip_ref:
            zip_ref.extractall(template_gridset_dir)
        st.write("Template gridset unzipped.")


# Function to search Keyman keyboards
def search_keyboards(query):
    params = {
        "q": f"l:{query}",  # Search for language name
        "f": 1,  # Make it JSON readable
    }
    response = requests.get(keyman_api_url, params=params)
    return response.json()


# Function to download KMP file and extract its contents
def download_and_extract_kmp(keyboard_id, version, extract_to="temp_kmp"):
    kmp_url = f"https://downloads.keyman.com/keyboards/{keyboard_id}/{version}/{keyboard_id}.kmp"
    st.write(f"Attempting to download from URL: {kmp_url}")
    response = requests.get(kmp_url)
    if response.status_code == 200:
        os.makedirs(extract_to, exist_ok=True)
        z = zipfile.ZipFile(io.BytesIO(response.content))
        z.extractall(extract_to)
        return extract_to
    else:
        st.error(
            f"Failed to download the KMP file. Status code: {response.status_code}"
        )
        return None


# Function to extract keyman mappings from the .js file
def extract_keyman_mappings(js_file_path):
    key_mappings = {}
    with open(js_file_path, "r", encoding="utf-8") as f:
        js_content = f.read()

    # Look for the KLS array in the JS file
    match = re.search(r"KV\.KLS\s*=\s*({.*?});", js_content, re.DOTALL)

    if match:
        kls_content = match.group(1)

        # Parse the mappings (this is a basic regex parser, you might need to adjust for edge cases)
        key_mapping_pairs = re.findall(r'"(\w+)"\s*:\s*\["(.*?)"\]', kls_content)
        for layer, mappings in key_mapping_pairs:
            for idx, char in enumerate(mappings.split(",")):
                key_mappings[f"{chr(97 + idx)}"] = char.strip('"')

    return key_mappings


# Function to modify gridset XML with extracted mappings
def modify_gridset_with_keyboard_mappings(keyman_mappings):
    try:
        modified_dir = "modified_gridset"
        shutil.copytree(template_gridset_dir, modified_dir, dirs_exist_ok=True)

        for foldername, _, filenames in os.walk(modified_dir):
            for filename in filenames:
                if filename.endswith(".xml"):
                    xml_path = os.path.join(foldername, filename)

                    tree = ET.parse(xml_path)
                    root = tree.getroot()

                    for cell in root.findall(".//Cell"):
                        caption_element = cell.find(".//CaptionAndImage/Caption")
                        parameter_element = cell.find(
                            './/Commands/Command/Parameter[@Key="Arguments"]'
                        )

                        if (
                            caption_element is not None
                            and parameter_element is not None
                        ):
                            current_caption = caption_element.text.lower()

                            # Look up the new character from keyman mappings
                            if current_caption in keyman_mappings:
                                new_character = keyman_mappings[current_caption]

                                # Update the <Caption> element
                                caption_element.text = new_character

                                parameter_element.set("Key", "Arguments")
                                parameter_element.text = f"type:{new_character}"  # Correctly set the new character

                    tree.write(xml_path)

        # Repack the modified gridset
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

# UI: Search for a language
language_query = st.text_input("Enter a language to search for:")

if st.button("Search Keyboards"):
    if language_query:
        keyboards_data = search_keyboards(language_query)
        if "keyboards" in keyboards_data:
            st.session_state.keyboards = keyboards_data["keyboards"]
        else:
            st.error("No keyboards found for the entered language.")
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

    # Get keyboard id and version
    keyboard_id = keyboard_choice["id"]
    keyboard_version = keyboard_choice["version"]

    st.write(f"Selected Keyboard: {keyboard_id}, Version: {keyboard_version}")

    # Download the selected KMP file
    extracted_folder = download_and_extract_kmp(keyboard_id, keyboard_version)
    if extracted_folder:
        st.write(f"KMP file extracted to {extracted_folder}")

        # Find and parse the .js file for key mappings
        js_file_path = None
        for root, dirs, files in os.walk(extracted_folder):
            for file in files:
                if file.endswith(".js"):
                    js_file_path = os.path.join(root, file)
                    break

        if js_file_path:
            keyman_mappings = extract_keyman_mappings(js_file_path)
            st.write(f"Extracted key mappings: {keyman_mappings}")

            # Apply keyman mappings to the template gridset
            modified_gridset = modify_gridset_with_keyboard_mappings(keyman_mappings)
            if modified_gridset:
                language_name = keyboard_choice["id"]
                filename = f"{language_name}.gridset"
                st.download_button(
                    "Download Modified Gridset",
                    modified_gridset.getvalue(),
                    filename,
                )
            else:
                st.error("Failed to modify gridset.")
        else:
            st.error("JS file not found in the KMP package.")
    else:
        st.error("Failed to extract KMP file.")
