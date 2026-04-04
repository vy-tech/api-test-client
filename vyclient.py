#!/usr/bin/env python3

import argparse
import configparser
import json
import logging
import os
import time
import requests

BASE_URL = "https://vy.vision/api/v1"

MIME_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".m4v": "video/mp4",
    ".mkv": "video/x-matroska",
}


class VyApiClient:
    def __init__(self):
        self.init_args()
        self.init_config()
        self.init_logging()

    def init_args(self):
        parser = argparse.ArgumentParser(description="Vy API v1 test client")
        parser.add_argument('-v', '--verbose', action='store_true')
        parser.add_argument('-f', '--file',
                            help='Video file to upload (mp4, mov, avi, m4v, mkv)')
        parser.add_argument('-s', '--status', metavar='VIDEO_ID',
                            help='Get status for a video by ID')
        parser.add_argument('-r', '--result', metavar='VIDEO_ID',
                            help='Get result for a video by ID')
        self.args = parser.parse_args()

    def init_config(self):
        self.config = configparser.ConfigParser()
        self.config.read("vyclient.conf")

        self.secrets = configparser.ConfigParser()
        self.secrets.read("vyclient-secrets.conf")

    def init_logging(self):
        self.log = logging.getLogger(__name__)
        level = self.config.get('DEFAULT', 'log_level', fallback='INFO')

        if self.args.verbose:
            level = 'DEBUG'

        fmt = self.config.get('DEFAULT', 'log_format',
                               fallback='[%(asctime)s %(levelname)s] %(message)s')
        logging.basicConfig(level=logging.getLevelName(level), format=fmt)

    def _base_url(self):
        return self.config.get('DEFAULT', 'base_url', fallback=BASE_URL)

    def _api_key(self):
        return self.secrets.get('DEFAULT', 'API_KEY', fallback='')

    def _headers(self):
        return {"X-API-Key": self._api_key()}

    def health_check(self):
        resp = requests.get(f"{self._base_url()}/health", headers=self._headers())
        resp.raise_for_status()
        self.log.info(f"Health: {resp.json()}")
        return resp.json()

    def upload_video(self, file_path):
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        ext = os.path.splitext(filename)[1].lower()
        mime_type = MIME_TYPES.get(ext, "application/octet-stream")

        self.log.info(f"Uploading {filename} ({file_size} bytes)")

        # Step 1: Request upload URL and token
        resp = requests.post(
            f"{self._base_url()}/video/upload/request",
            headers=self._headers(),
            json={"filename": filename, "mimeType": mime_type},
        )
        resp.raise_for_status()
        data = resp.json()
        upload_url = data["uploadUrl"]
        upload_token = data["uploadToken"]
        self.log.debug(f"uploadToken: {upload_token}")

        # Step 2: PUT entire file to upload URL
        with open(file_path, "rb") as fh:
            file_bytes = fh.read()
        put_resp = requests.put(upload_url, data=file_bytes, headers={"Content-Type": mime_type})
        put_resp.raise_for_status()
        self.log.debug(f"PUT response: {put_resp.status_code}")

        # Step 3: Complete the upload
        resp = requests.post(
            f"{self._base_url()}/video/upload/complete",
            headers=self._headers(),
            json={"uploadToken": upload_token},
        )
        resp.raise_for_status()
        result = resp.json()
        self.log.info(f"Upload complete: fileId={result.get('fileId')} jobId={result.get('jobId')}")
        return result

    def poll_status(self, file_id, interval=5):
        TERMINAL = {"completed", "failed"}
        self.log.info(f"Polling status for fileId={file_id}")
        while True:
            result = self.get_status(file_id)
            statuses = {job.get("status") for job in result.get("jobs", [])}
            if statuses and statuses <= TERMINAL:
                break
            self.log.info(f"Waiting {interval}s...")
            time.sleep(interval)

    def get_status(self, video_id):
        resp = requests.get(
            f"{self._base_url()}/video/status/{video_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        result = resp.json()
        file_info = result.get('file', {})
        self.log.info(f"File: id={file_info.get('id')} filename={file_info.get('filename')}")
        for job in result.get('jobs', []):
            self.log.info(f"Job: id={job.get('id')} type={job.get('type')} status={job.get('status')} message={job.get('message')}")
        return result

    def get_result(self, video_id):
        resp = requests.get(
            f"{self._base_url()}/video/results/{video_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        result = resp.json()
        print(json.dumps(result, indent=2))

        return result


    def start(self):
        self.health_check()

        if self.args.result:
            self.get_result(self.args.result)
        elif self.args.status:
            self.get_status(self.args.status)
        elif self.args.file:
            result = self.upload_video(self.args.file)
            file_id = result.get("fileId")
            if file_id:
                self.poll_status(file_id)
            self.get_result(file_id)
        else:
            self.log.error("Specify --file to upload or --status VIDEO_ID to check status")


if __name__ == "__main__":
    client = VyApiClient()
    client.start()
