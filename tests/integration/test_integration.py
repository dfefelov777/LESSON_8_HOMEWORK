import unittest
import subprocess
import time
import requests
import threading
import os
import signal
import json
import hashlib
import datetime
import sys
import logging

from homework.app import api


SERVER_PORT = 8080
SERVER_HOST = "localhost"

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "fixtures")
REQUEST_FIXTURES_DIR = os.path.join(FIXTURES_DIR, "requests")
RESPONSE_FIXTURES_DIR = os.path.join(FIXTURES_DIR, "responses")

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


class ServerThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(ServerThread, self).__init__(*args, **kwargs)
        self.process = None
        self.stdout = ""
        self.stderr = ""

    def run(self):
        env = os.environ.copy()
        env["REDIS_HOST"] = os.getenv("REDIS_HOST", "localhost")
        env["REDIS_PORT"] = os.getenv("REDIS_PORT", "6379")

        command = ["python", "-m", "homework.app.api", "-p", str(SERVER_PORT)]
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            preexec_fn=os.setsid,
        )
        time.sleep(2)

    def stop(self):
        if self.process:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            self.stdout, self.stderr = self.process.communicate()
            self.process.wait()


class TestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.init_redis()

        cls.server_thread = ServerThread()
        cls.server_thread.start()
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        cls.server_thread.stop()
        if cls.server_thread.stdout:
            print("Server stdout:\n", cls.server_thread.stdout.decode())
        if cls.server_thread.stderr:
            print("Server stderr:\n", cls.server_thread.stderr.decode())

    @staticmethod
    def init_redis():
        import redis

        REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

        # Add test data to Redis
        client.set("i:1", json.dumps(["books", "music"]))
        client.set("i:2", json.dumps(["travel", "sports"]))
        client.set("i:3", json.dumps(["movies", "tech"]))

    def load_fixture(self, fixture_type, filename):
        if fixture_type == "request":
            fixture_path = os.path.join(REQUEST_FIXTURES_DIR, filename)
        elif fixture_type == "response":
            fixture_path = os.path.join(RESPONSE_FIXTURES_DIR, filename)
        else:
            raise ValueError("Invalid fixture type. Use 'request' or 'response'.")

        with open(fixture_path, "r") as f:
            return json.load(f)

    def set_valid_auth(self, request):
        if request.get("login") == api.ADMIN_LOGIN:
            request["token"] = hashlib.sha512(
                (datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT).encode(
                    "utf-8"
                )
            ).hexdigest()
        else:
            msg = (
                request.get("account", "") + request.get("login", "") + api.SALT
            ).encode("utf-8")
            request["token"] = hashlib.sha512(msg).hexdigest()

    def make_request(self, request):
        url = f"http://{SERVER_HOST}:{SERVER_PORT}/method"
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, data=json.dumps(request), headers=headers)
        return response.json()

    def test_valid_online_score(self):
        request_data = self.load_fixture("request", "valid_online_score_request.json")
        expected_response = self.load_fixture(
            "response", "expected_online_score_response.json"
        )

        self.set_valid_auth(request_data)

        response = self.make_request(request_data)

        self.assertEqual(response["code"], expected_response["code"])
        self.assertIn("score", response["response"])
        self.assertGreaterEqual(response["response"]["score"], 0)

    def test_invalid_online_score(self):
        request_data = self.load_fixture("request", "invalid_online_score_request.json")

        self.set_valid_auth(request_data)

        response = self.make_request(request_data)

        self.assertNotEqual(response["code"], api.OK)
        self.assertIn("error", response)

    def test_valid_clients_interests(self):
        request_data = self.load_fixture(
            "request", "valid_clients_interests_request.json"
        )
        expected_response = self.load_fixture(
            "response", "expected_clients_interests_response.json"
        )

        self.set_valid_auth(request_data)

        response = self.make_request(request_data)

        self.assertEqual(response["code"], expected_response["code"])
        self.assertEqual(len(response["response"]), len(expected_response["response"]))
        for cid, interests in response["response"].items():
            self.assertIn(cid, expected_response["response"])
            self.assertEqual(interests, expected_response["response"][cid])

    def test_invalid_clients_interests(self):
        request_data = self.load_fixture(
            "request", "invalid_clients_interests_request.json"
        )

        self.set_valid_auth(request_data)

        response = self.make_request(request_data)

        self.assertNotEqual(response["code"], api.OK)
        self.assertIn("error", response)


if __name__ == "__main__":
    unittest.main()
