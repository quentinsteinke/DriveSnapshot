import os

def copy_all_Files(blender_version):
    destination_path = f"\\AppData\\Roaming\\Blender Foundation\\Blender\\{blender_version}\\scripts\\addons\\DriveSnapshot"
    user_path = os.path.expanduser("~")
    current_file_name = os.path.basename(__file__)
    full_file_path = __file__
    current_working_directory = full_file_path[:-len(current_file_name)]

    search_files = (os.listdir(current_working_directory))

    # Copy python files
    for file in search_files:
        if file == current_file_name:
            continue
        if file.endswith(".py"):
            os.system(f'copy "{current_working_directory}{file}" "{user_path}{destination_path}"')
        else:
            pass

def copy_folder(blender_version):
    destination_path = f"\\AppData\\Roaming\\Blender Foundation\\Blender\\{blender_version}\\scripts\\addons\\DriveSnapshot"
    user_path = os.path.expanduser("~")
    current_file_name = os.path.basename(__file__)
    full_file_path = __file__
    current_working_directory = full_file_path[:-len(current_file_name)]

    # Copy forlder
    os.system(f'xcopy "{current_working_directory}" "{user_path}{destination_path}" /E /I /Y')

# copy_folder(3.6)
copy_folder(4.0)