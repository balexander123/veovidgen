#!/usr/bin/env python3

import os
import argparse
import io
import time
import pickle # For storing/loading Drive API tokens

# --- Google Gemini AI ---
import google.generativeai as genai

# --- Google Drive API ---
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# --- Optional for downloading video from URIs ---
try:
    import requests
except ImportError:
    requests = None # Will check later if needed

try:
    from google.cloud import storage
except ImportError:
    storage = None # Will check later if needed


# --- Configuration ---
GEMINI_API_KEY_ENV_VAR = "GOOGLE_GEMINI_API_KEY"

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']
DRIVE_TOKEN_PICKLE = 'token.pickle'
DRIVE_CREDENTIALS_JSON = 'credentials.json'

# --- Veo Configuration (Updated based on hypothetical docs) ---
# This is a plausible model name. Replace with the actual one when known.
VEO_MODEL_NAME = "models/veo-1.0" # Example: "models/veo-1.0", "models/gemini-pro-video"
# Default MIME type if not explicitly provided by the API response for the video
DEFAULT_VIDEO_MIME_TYPE = "video/mp4"


# --- Google Drive Authentication Function (same as before) ---
def get_google_drive_service():
    creds = None
    if os.path.exists(DRIVE_TOKEN_PICKLE):
        with open(DRIVE_TOKEN_PICKLE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Failed to refresh Drive token: {e}. Deleting '{DRIVE_TOKEN_PICKLE}' for re-auth.")
                if os.path.exists(DRIVE_TOKEN_PICKLE): os.remove(DRIVE_TOKEN_PICKLE)
                creds = None
        if not creds: # Re-authenticate
            if not os.path.exists(DRIVE_CREDENTIALS_JSON):
                print(f"ERROR: Google Drive API credentials file ('{DRIVE_CREDENTIALS_JSON}') not found.")
                print("Please download it from your Google Cloud Console project and place it here.")
                # (Instructions for credentials.json - same as before)
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                DRIVE_CREDENTIALS_JSON, DRIVE_SCOPES)
            creds = flow.run_local_server(port=0)

        with open(DRIVE_TOKEN_PICKLE, 'wb') as token:
            pickle.dump(creds, token)
    try:
        service = build('drive', 'v3', credentials=creds)
        print("Google Drive API service created successfully.")
        return service
    except Exception as e:
        print(f"An error occurred building the Drive service: {e}")
        return None

# --- Gemini Veo Video Generation Function (Updated) ---
def generate_veo_video(prompt: str, gemini_api_key: str):
    """
    Generates video using the Veo model via Gemini API.
    Assumes the API returns a file_uri for the generated video.
    """
    print(f"\n--- Generating Video for Prompt: '{prompt}' ---")
    print(f"Using Veo model: {VEO_MODEL_NAME}")

    genai.configure(api_key=gemini_api_key)

    try:
        model = genai.GenerativeModel(VEO_MODEL_NAME)
    except Exception as e:
        print(f"ERROR: Could not initialize Veo model '{VEO_MODEL_NAME}'.")
        print(f"Details: {e}")
        print("This could be due to an incorrect model name or the model not being available to your API key yet.")
        print("Please check Google's official documentation for the correct Veo model identifier.")
        return None, None

    print("Sending request to Gemini API for video generation (this might take a significant amount of time)...")
    try:
        # The generate_content call for video might include specific 'generation_config'
        # options like duration, fps, aspect_ratio, etc.
        # For simplicity, we'll use defaults here.
        # Example:
        # generation_config = genai.types.GenerationConfig(
        #     # video_duration_seconds=10, # Hypothetical
        #     # video_quality="high",      # Hypothetical
        # )
        # response = model.generate_content(prompt, generation_config=generation_config)

        response = model.generate_content(prompt)

        if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
            print("ERROR: No valid candidates or content parts found in the Gemini response.")
            print("Response details:", response)
            return None, None

        video_part = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'file_data') and part.file_data.mime_type.startswith('video/'):
                video_part = part
                break
            # It's also possible that the response directly contains a video URI not nested in file_data
            # e.g. if response.candidates[0].content has a 'video_uri' attribute.
            # This needs to be confirmed with actual API documentation.

        if not video_part:
            print("ERROR: Could not find video data (as file_data) in the Gemini response.")
            print("Full response candidate content:", response.candidates[0].content)
            return None, None

        file_uri = video_part.file_data.file_uri
        video_mime_type = video_part.file_data.mime_type or DEFAULT_VIDEO_MIME_TYPE

        print(f"Video generation apparently successful. File URI: {file_uri}, MIME type: {video_mime_type}")
        print("Attempting to download video from URI...")

        video_bytes = None
        # Scenario 1: URI is a direct HTTPS link (e.g., a signed URL)
        if file_uri.startswith("https://"):
            if not requests:
                print("ERROR: The 'requests' library is required to download from HTTPS URIs but is not installed.")
                print("Please install it: pip install requests")
                return None, None
            try:
                print(f"Downloading from HTTPS: {file_uri}")
                # Some APIs might require the API key in the auth header for the download too
                # headers = {"Authorization": f"Bearer {gemini_api_key}"}
                # http_response = requests.get(file_uri, headers=headers, stream=True)
                http_response = requests.get(file_uri, stream=True, timeout=300) # 5 min timeout for download
                http_response.raise_for_status()
                video_bytes = http_response.content
                print(f"Successfully downloaded video ({len(video_bytes)} bytes) from HTTPS URI.")
            except requests.exceptions.RequestException as e_req:
                print(f"ERROR: Failed to download video from HTTPS URI '{file_uri}': {e_req}")
                return None, None

        # Scenario 2: URI is a Google Cloud Storage link (gs://)
        elif file_uri.startswith("gs://"):
            if not storage:
                print("ERROR: The 'google-cloud-storage' library is required to download from GCS URIs (gs://) but is not installed.")
                print("Please install it: pip install google-cloud-storage")
                return None, None
            try:
                print(f"Downloading from GCS: {file_uri}")
                client = storage.Client() # Uses Application Default Credentials
                # Parse gs:// URI
                bucket_name, blob_name = file_uri[5:].split("/", 1)
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                video_bytes = blob.download_as_bytes(timeout=300) # 5 min timeout
                print(f"Successfully downloaded video ({len(video_bytes)} bytes) from GCS URI.")
            except Exception as e_gcs:
                print(f"ERROR: Failed to download video from GCS URI '{file_uri}': {e_gcs}")
                print("Ensure you have 'gcloud auth application-default login' configured and permissions to access the GCS object.")
                return None, None
        else:
            print(f"ERROR: Unrecognized or unsupported file URI scheme: {file_uri}")
            print("The script currently supports 'https://' and 'gs://' URIs for generated videos.")
            return None, None

        if video_bytes:
            return video_bytes, video_mime_type
        else:
            print("ERROR: Video bytes could not be retrieved after URI processing.")
            return None, None

    except Exception as e:
        print(f"An error occurred during Veo video generation or download: {e}")
        # Consider logging the full response if available and an error occurs
        # if 'response' in locals(): print("Full response:", response)
        return None, None


# --- Google Drive Upload Function (same as before) ---
def upload_to_drive(drive_service, filename: str, video_bytes: bytes, mime_type: str, folder_id: str = None):
    if not drive_service:
        print("Drive service not available. Cannot upload.")
        return None

    print(f"\n--- Uploading '{filename}' to Google Drive ---")
    file_metadata = {'name': filename}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaIoUpload(io.BytesIO(video_bytes),
                          mimetype=mime_type,
                          resumable=True,
                          chunksize=1024*1024*5) # 5MB chunks
    try:
        request = drive_service.files().create(body=file_metadata,
                                               media_body=media,
                                               fields='id, webViewLink')
        response = None
        progress = 0
        print("Starting upload...")
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    new_progress = int(status.progress() * 100)
                    if new_progress > progress: # Only print if progress actually increased
                        progress = new_progress
                        print(f"Uploaded {progress}%")
            except Exception as e_chunk:
                print(f"Error during chunk upload: {e_chunk}. Retrying may be necessary or check connection.")
                # For a robust solution, implement retries here.
                return None

        file_id = response.get('id')
        file_link = response.get('webViewLink')
        print(f"SUCCESS: File '{filename}' uploaded to Google Drive.")
        print(f"File ID: {file_id}")
        print(f"View Link: {file_link}")
        return file_link
    except Exception as e:
        print(f"An error occurred uploading to Drive: {e}")
        return None


# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Generate Veo video from a prompt using Gemini API and upload to Google Drive.")
    parser.add_argument("prompt", type=str, help="The text prompt for video generation.")
    parser.add_argument("-o", "--output_filename", type=str, default=None,
                        help="Desired filename for the video on Google Drive (e.g., my_veo_video.mp4). Default uses a timestamp.")
    parser.add_argument("-f", "--folder_id", type=str, default=None,
                        help="Optional Google Drive Folder ID to upload the video into.")
    # Potentially add more arguments here for video generation parameters if API supports them
    # e.g., --duration, --fps

    args = parser.parse_args()

    gemini_api_key = os.getenv(GEMINI_API_KEY_ENV_VAR)
    if not gemini_api_key:
        print(f"ERROR: Google Gemini API key not found in environment variable '{GEMINI_API_KEY_ENV_VAR}'.")
        print(f"Please set it: export {GEMINI_API_KEY_ENV_VAR}=\"YOUR_API_KEY\"")
        return

    print("--- Authenticating with Google Drive ---")
    drive_service = get_google_drive_service()
    if not drive_service:
        print("Failed to authenticate with Google Drive. Exiting.")
        return

    video_bytes, video_mime_type = generate_veo_video(args.prompt, gemini_api_key)

    if not video_bytes or not video_mime_type:
        print("Video generation or download failed. Exiting.")
        return

    # Determine output filename
    if args.output_filename:
        output_filename = args.output_filename
        # Ensure it has a video extension if not provided
        known_video_extensions = ('.mp4', '.mov', '.avi', '.webm', '.mkv')
        if not output_filename.lower().endswith(known_video_extensions):
            inferred_ext = video_mime_type.split('/')[-1]
            if inferred_ext and inferred_ext != '*': # e.g., 'mp4' from 'video/mp4'
                output_filename = f"{output_filename}.{inferred_ext}"
            else:
                output_filename = f"{output_filename}.mp4" # Default to .mp4
    else:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        ext = video_mime_type.split('/')[-1] if video_mime_type and video_mime_type.split('/')[-1] != '*' else 'mp4'
        output_filename = f"veo_video_{args.prompt[:20].replace(' ','_')}_{timestamp}.{ext}" # Add part of prompt for easier ID

    upload_link = upload_to_drive(drive_service, output_filename, video_bytes, video_mime_type, args.folder_id)

    if upload_link:
        print(f"\nProcess complete! Video available at: {upload_link}")
    else:
        print("\nProcess completed, but upload to Drive may have failed or was skipped.")


if __name__ == "__main__":
    print("--------------------------------------------------------------------")
    print("      Google Gemini Veo Video Generator & Drive Uploader (v2)       ")
    print("--------------------------------------------------------------------")
    print("This script assumes Veo video generation via Gemini API will provide")
    print("a downloadable URI (HTTPS or GCS) for the generated video.")
    print("Actual API details may vary. Update VEO_MODEL_NAME as needed.")
    print("--------------------------------------------------------------------\n")
    main()