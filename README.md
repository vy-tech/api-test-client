# vy-api-test-client

A simple Python test client for the [Vy API v1](https://app.vy.vision).

* Reads command line arguments (file to upload, verbosity)
* Reads config from `vyclient.conf` and secrets from `vyclient-secrets.conf`
* Secrets config has "DO NOT SHOW ON STREAM" banner
* Performs a multipart video upload using the Vy v1 API

## Setup

1. Copy the secrets sample and add your API key:

```
cp vyclient-secrets.conf.sample vyclient-secrets.conf
```

2. Edit `vyclient-secrets.conf` and set `API_KEY` to your Vy API key (starts with `vyk_`).

3. Install dependencies:

```
pip install requests
```

## Usage

```
python vyclient.py --file path/to/video.mp4
python vyclient.py -v --file path/to/video.mp4   # verbose / debug logging
```

Supported video formats: `mp4`, `mov`, `avi`, `m4v`, `mkv`

## Upload flow

1. `POST /api/v1/video/upload/request` — initiates a session, returns `uploadId`
2. `POST /api/v1/video/upload/part` — gets a presigned URL per 5 MB chunk; raw bytes are PUT directly to that URL
3. `POST /api/v1/video/upload/complete` — finalizes the upload and queues processing

After a successful upload the client logs the `fileId` and `jobId` returned by the API.
