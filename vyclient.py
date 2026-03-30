#!/usr/bin/env python3

import argparse
import configparser
import logging
import math
import os
import requests

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB
BASE_URL = "https://vy.vision/api/v1"


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
        num_parts = math.ceil(file_size / CHUNK_SIZE)

        self.log.info(f"Uploading {filename} ({file_size} bytes, {num_parts} part(s))")

        # Step 1: Request upload session
        resp = requests.post(
            f"{self._base_url()}/video/upload/request",
            headers=self._headers(),
            json={"filename": filename},
        )
        resp.raise_for_status()
        upload_id = resp.json()["uploadId"]
        self.log.debug(f"uploadId: {upload_id}")

        # Step 2: Upload each part
        parts = []
        with open(file_path, "rb") as fh:
            for part_number in range(1, num_parts + 1):
                chunk = fh.read(CHUNK_SIZE)
                self.log.info(f"Uploading part {part_number}/{num_parts} ({len(chunk)} bytes)")

                # Get presigned URL for this part
                resp = requests.post(
                    f"{self._base_url()}/video/upload/part",
                    headers=self._headers(),
                    json={"uploadId": upload_id, "partNumber": part_number},
                )
                resp.raise_for_status()
                upload_url = resp.json()["uploadUrl"]
                self.log.debug(f"Presigned URL: {upload_url}")

                # PUT chunk directly to presigned URL (no auth header)
                put_resp = requests.put(upload_url, data=chunk)
                put_resp.raise_for_status()
                etag = put_resp.headers.get("ETag", "").strip('"')
                self.log.debug(f"Part {part_number} ETag: {etag}")
                parts.append({"PartNumber": part_number, "ETag": etag})

        # Step 3: Complete the upload
        resp = requests.post(
            f"{self._base_url()}/video/upload/complete",
            headers=self._headers(),
            json={"uploadId": upload_id, "parts": parts},
        )
        resp.raise_for_status()
        result = resp.json()
        self.log.info(f"Upload complete: fileId={result.get('fileId')} jobId={result.get('jobId')}")
        return result

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

    def start(self):
        self.health_check()

        video_id = self.args.status or self.config.get('DEFAULT', 'video_id', fallback=None)

        if video_id:
            self.get_status(video_id)
        elif self.args.file:
            self.upload_video(self.args.file)
        else:
            self.log.error("Specify --file to upload or --status VIDEO_ID to check status")


if __name__ == "__main__":
    client = VyApiClient()
    client.start()
