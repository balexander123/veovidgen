# Google Gemini Veo Video Generator & Drive Uploader

**Version:** 2.0 (Based on speculative Veo API access)

This Python script allows users to generate videos from text prompts using Google's (hypothetical/upcoming) Veo model via the Gemini API. The generated video is then automatically uploaded to the user's Google Drive.

**IMPORTANT CAVEAT:** As of the last update (June 2024), the specific API for Google's Veo video generation model is **not yet publicly available or fully documented**. This script is built on:
1.  The existing `google-generativeai` Python SDK for Gemini.
2.  Educated assumptions about how a video generation API might be structured (e.g., returning a downloadable URI).
3.  Standard practices for Google API authentication and Google Drive uploads.

**You will likely need to update the `VEO_MODEL_NAME` constant and parts of the `generate_veo_video` function once official Veo API details are released by Google.**

## Features

*   Takes a text prompt as input from the command line.
*   Authenticates with the Google Gemini API using an API key.
*   (Speculatively) Calls the Veo model to generate video content.
*   Handles video retrieval, assuming the API returns a downloadable URI (either HTTPS or Google Cloud Storage `gs://`).
*   Authenticates with the Google Drive API using OAuth 2.0.
*   Uploads the generated video to a specified Google Drive folder (or the root if not specified).
*   Allows custom naming for the uploaded video file.

## Prerequisites

*   Python 3.7+
*   `pip` (Python package installer)
*   A Google Account.
*   A Google Cloud Platform (GCP) project.

## Setup Instructions

1.  **Download the Script:**
    Save the Python script as `generate_veo.py` (or your preferred name) in a local directory.

2.  **Install Python Libraries:**
    Open your terminal or command prompt and run:
    ```bash
    pip install google-generativeai google-api-python-client google-auth-httplib2 google-auth-oauthlib requests google-cloud-storage
    ```

3.  **Set up Google Gemini API Key:**
    *   Go to [Google AI Studio](https://aistudio.google.com/app/apikey) (or the relevant portal once Veo is integrated).
    *   Create an API key if you don't have one.
    *   Set this key as an environment variable. In your terminal:
        *   For macOS/Linux: `export GOOGLE_GEMINI_API_KEY="YOUR_API_KEY_HERE"`
        *   For Windows (cmd): `set GOOGLE_GEMINI_API_KEY=YOUR_API_KEY_HERE`
        *   For Windows (PowerShell): `$env:GOOGLE_GEMINI_API_KEY="YOUR_API_KEY_HERE"`
        (Consider adding this to your shell's profile file like `.bashrc`, `.zshrc`, or PowerShell profile for persistence).

4.  **Set up Google Drive API Credentials:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Select or create a GCP project.
    *   **Enable the Google Drive API:**
        *   Navigate to "APIs & Services" -> "Library".
        *   Search for "Google Drive API" and enable it for your project.
    *   **Create OAuth 2.0 Client ID:**
        *   Navigate to "APIs & Services" -> "Credentials".
        *   Click `+ CREATE CREDENTIALS` -> `OAuth client ID`.
        *   For "Application type", select `Desktop app`.
        *   Give it a name (e.g., "Veo Script Drive Uploader").
        *   Click `CREATE`.
        *   A pop-up will show your Client ID and Client Secret. Click `DOWNLOAD JSON`.
        *   Save this downloaded JSON file as `credentials.json` in the **same directory** as your Python script.
    *   **First Run (OAuth Consent):** The first time you run the script, it will open a browser window asking you to authorize access to your Google Drive. Follow the prompts. A `token.pickle` file will be created to store your authorization tokens for future runs.

5.  **Set up Google Cloud SDK (Recommended, especially if Veo returns `gs://` URIs):**
    *   If the Veo API provides video files via Google Cloud Storage URIs (`gs://...`), you'll need the Google Cloud SDK installed and authenticated with Application Default Credentials (ADC).
    *   Install the SDK: [Google Cloud SDK Installation Guide](https://cloud.google.com/sdk/docs/install)
    *   Authenticate for ADC:
        ```bash
        gcloud auth application-default login
        ```
        This command will open a browser for you to log in with your Google account. This allows the `google-cloud-storage` library in the script to access GCS resources on your behalf.

## How to Run the Script

Open your terminal or command prompt, navigate to the directory where you saved the script and `credentials.json`, and run:

**Basic Usage:**
```bash
python generate_veo.py "Your imaginative video prompt here"
```
Example:
```bash
python generate_veo.py "A golden retriever puppy discovering a magical forest"
```

**With Options:**
*   `-o` or `--output_filename`: Specify the name for the video file on Google Drive (e.g., `my_video.mp4`). If no extension is provided, one will be inferred from the video's MIME type or default to `.mp4`.
*   `-f` or `--folder_id`: Specify the Google Drive Folder ID where you want to upload the video. You can find this ID in the URL when you open a folder in Google Drive (e.g., `https://drive.google.com/drive/folders/THIS_IS_THE_ID`).

Example with options:
```bash
python generate_veo.py "Cinematic shot of a lone astronaut on Mars" -o "mars_mission_intro.mp4" -f "YOUR_GOOGLE_DRIVE_FOLDER_ID"
```

## Important Notes & Caveats

*   **Speculative Veo API:** The core video generation part (`generate_veo_video` function and `VEO_MODEL_NAME`) is speculative. You **MUST** update `VEO_MODEL_NAME` with the official model identifier once Google releases it. The response parsing for the video URI might also need adjustments.
*   **Video URI Handling:** The script is designed to handle video retrieval from:
    *   **HTTPS URIs:** Assumed to be directly downloadable (e.g., signed URLs). Requires the `requests` library.
    *   **Google Cloud Storage URIs (`gs://`):** Requires the `google-cloud-storage` library and properly configured Application Default Credentials (see Setup step 5).
*   **API Quotas and Costs:** Be mindful of API usage quotas and potential costs associated with the Gemini API and Google Cloud Storage (if applicable for video hosting/download).
*   **Error Handling:** The script includes basic error handling, but complex API issues or network problems might require more sophisticated retry mechanisms.
*   **Long Processing Times:** Video generation can be time-consuming. The script may run for several minutes or longer depending on the complexity of the prompt and the Veo model's performance. Timeouts are implemented for downloads but ensure your system/shell doesn't terminate long-running processes prematurely.
*   **Security of `credentials.json` and `token.pickle`:** Keep these files secure, as they grant access to your Google Drive. Do not commit them to public repositories. Add them to your `.gitignore` file if using Git.

## Script Breakdown

*   **`get_google_drive_service()`:** Handles OAuth 2.0 authentication for the Google Drive API, storing and refreshing tokens in `token.pickle`.
*   **`generate_veo_video()`:**
    *   Configures the Gemini API client.
    *   Initializes the (speculative) Veo model.
    *   Sends the generation request with the prompt.
    *   Parses the response to find a `file_uri` for the video.
    *   Downloads the video content from the `file_uri` (handling `https://` and `gs://` schemes).
*   **`upload_to_drive()`:** Uploads the downloaded video bytes to Google Drive, handling resumable uploads for larger files.
*   **`main()`:**
    *   Parses command-line arguments.
    *   Retrieves the Gemini API key.
    *   Orchestrates the calls to authenticate Drive, generate video, and upload the video.
    *   Determines the output filename.

## Troubleshooting Common Issues

*   **`GOOGLE_GEMINI_API_KEY` not found:** Ensure the environment variable is set correctly in your current terminal session or shell profile.
*   **`credentials.json` not found:** Make sure the file is named exactly `credentials.json` and is in the same directory as the script.
*   **Drive API Not Enabled:** If you get errors related to Drive API access, double-check that it's enabled in your GCP project.
*   **`ImportError: No module named ...`:** You are missing one or more required Python libraries. Run the `pip install ...` command from Setup step 2 again.
*   **GCS Download Failures (`gs://` URIs):**
    *   Ensure `google-cloud-storage` library is installed.
    *   Ensure Google Cloud SDK is installed and you've run `gcloud auth application-default login`.
    *   Check if your GCP user/service account has permissions to read from the GCS bucket where Veo might store the videos.
*   **Video Generation Errors (from `generate_veo_video`):**
    *   The `VEO_MODEL_NAME` is likely incorrect or not yet available. Wait for official documentation.
    *   The API key might not have access to the Veo model.
    *   The prompt might be too complex, ambiguous, or violate usage policies.
*   **`token.pickle` issues:** If you encounter persistent authentication problems with Google Drive, try deleting `token.pickle` and let the script re-authenticate.

---

This script provides a starting point. Feel free to adapt and enhance it as more details about the Veo API become available!
```
