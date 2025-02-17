#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import datetime
import logging
import hashlib
import uuid
import sys
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from homework.app.scoring import get_score, get_interests
from homework.app.store import RedisStore

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class Field:
    def __init__(self, required=False, nullable=False):
        self.required = required
        self.nullable = nullable
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def validate(self, value):
        if value is None:
            if self.required:
                raise ValueError(f"'{self.name}' is required")
        else:
            if not self.nullable and not value:
                raise ValueError(f"'{self.name}' cannot be empty")

    def __get__(self, instance, owner):
        return instance.__dict__.get(self.name) if instance else self

    def __set__(self, instance, value):
        self.validate(value)
        instance.__dict__[self.name] = value


class CharField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None and value != "":
            if not isinstance(value, str):
                raise ValueError(f"'{self.name}' must be a string")


class ArgumentsField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            if not isinstance(value, dict):
                raise ValueError(f"'{self.name}' must be a dictionary")


class EmailField(CharField):
    def validate(self, value):
        super().validate(value)
        if value:
            if "@" not in value:
                raise ValueError(f"'{self.name}' must contain '@'")


class PhoneField(Field):
    def validate(self, value):
        super().validate(value)
        if value:
            if isinstance(value, (int, float)):
                value = str(value)
            if not isinstance(value, str):
                raise ValueError(f"'{self.name}' must be a string or number")
            if not value.isdigit():
                raise ValueError(f"'{self.name}' must contain only digits")
            if len(value) != 11:
                raise ValueError(f"'{self.name}' must be 11 digits")
            if not value.startswith("7"):
                raise ValueError(f"'{self.name}' must start with '7'")


class DateField(Field):
    def __set__(self, instance, value):
        if value is None:
            if self.required:
                raise ValueError(f"'{self.name}' is required")
            else:
                instance.__dict__[self.name] = None
        else:
            if not self.nullable and not value:
                raise ValueError(f"'{self.name}' cannot be empty")
            try:
                date_obj = datetime.datetime.strptime(value, "%d.%m.%Y")
                instance.__dict__[self.name] = date_obj
            except ValueError:
                raise ValueError(f"'{self.name}' must be in format 'DD.MM.YYYY'")


class BirthDayField(DateField):
    def __set__(self, instance, value):
        super().__set__(instance, value)
        date_obj = instance.__dict__[self.name]
        if date_obj:
            today = datetime.datetime.today()
            age = (today - date_obj).days // 365
            if age > 70:
                raise ValueError(
                    f"'{self.name}' must be less than or equal to 70 years old"
                )


class GenderField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            if not isinstance(value, int):
                raise ValueError(f"'{self.name}' must be an integer")
            if value not in GENDERS:
                raise ValueError(f"'{self.name}' must be 0, 1, or 2")


class ClientIDsField(Field):
    def validate(self, value):
        super().validate(value)
        if value:
            if not isinstance(value, list):
                raise ValueError(f"'{self.name}' must be a list")
            if not value:
                raise ValueError(f"'{self.name}' cannot be empty")
            for item in value:
                if not isinstance(item, int):
                    raise ValueError(f"Each item in '{self.name}' must be an integer")


class BaseRequest:
    def __init__(self, **kwargs):
        self.errors = []
        for name, field in self.fields().items():
            value = kwargs.get(name)
            try:
                setattr(self, name, value)
            except ValueError as e:
                self.errors.append(str(e))

    @classmethod
    def fields(cls):
        return {
            name: attr for name, attr in cls.__dict__.items() if isinstance(attr, Field)
        }

    def is_valid(self):
        return not self.errors

    def validate(self):
        for name, field in self.fields().items():
            try:
                field.validate(getattr(self, name, None))
            except ValueError as e:
                self.errors.append(str(e))


class MethodRequest(BaseRequest):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=True)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


class OnlineScoreRequest(BaseRequest):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def validate(self):
        super().validate()
        pairs = [
            ("phone", "email"),
            ("first_name", "last_name"),
            ("gender", "birthday"),
        ]
        if not any(
            (getattr(self, field[0], None) is not None)
            and (getattr(self, field[1], None) is not None)
            for field in pairs
        ):
            self.errors.append(
                "At least one pair of fields must be provided: "
                "phone and email, first_name and last_name, or gender and birthday"
            )


class ClientsInterestsRequest(BaseRequest):
    client_ids = ClientIDsField(required=True, nullable=False)
    date = DateField(required=False, nullable=True)


def check_auth(request):
    if request.is_admin:
        digest = hashlib.sha512(
            (datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode("utf-8")
        ).hexdigest()
    else:
        digest = hashlib.sha512(
            (request.account + request.login + SALT).encode("utf-8")
        ).hexdigest()
    return digest == request.token


def method_handler(request, ctx, store):
    method_request = MethodRequest(**request["body"])
    method_request.validate()
    if not method_request.is_valid():
        return {"error": method_request.errors}, INVALID_REQUEST
    if not check_auth(method_request):
        return {"error": "Forbidden"}, FORBIDDEN

    method = method_request.method
    arguments = method_request.arguments or {}
    if method == "online_score":
        online_score_request = OnlineScoreRequest(**arguments)
        online_score_request.validate()
        if not online_score_request.is_valid():
            return {"error": online_score_request.errors}, INVALID_REQUEST

        ctx["has"] = [
            name
            for name in online_score_request.fields()
            if getattr(online_score_request, name) is not None
        ]

        if method_request.is_admin:
            score = 42
        else:
            score = get_score(
                store,
                phone=online_score_request.phone,
                email=online_score_request.email,
                birthday=online_score_request.birthday,
                gender=online_score_request.gender,
                first_name=online_score_request.first_name,
                last_name=online_score_request.last_name,
            )
        return {"score": score}, OK

    elif method == "clients_interests":
        clients_interests_request = ClientsInterestsRequest(**arguments)
        clients_interests_request.validate()
        if not clients_interests_request.is_valid():
            return {"error": clients_interests_request.errors}, INVALID_REQUEST

        ctx["nclients"] = len(clients_interests_request.client_ids)
        response = {
            str(cid): get_interests(store, cid)
            for cid in clients_interests_request.client_ids
        }
        return response, OK

    else:
        return {"error": "Method not found"}, NOT_FOUND


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {"method": method_handler}

    def __init__(self, *args, **kwargs):
        self.store = RedisStore()
        super().__init__(*args, **kwargs)

    def get_request_id(self, headers):
        return headers.get("HTTP_X_REQUEST_ID", uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        request = None
        context = {"request_id": self.get_request_id(self.headers)}
        try:
            length = int(self.headers["Content-Length"])
            data = self.rfile.read(length).decode("utf-8")
            request_body = json.loads(data)
            path = self.path.strip("/")
            logging.info(f"Received request: {data}")
            if path in self.router:
                handler = self.router[path]
                response, code = handler(
                    {"body": request_body, "headers": self.headers},
                    context,
                    self.store,
                )
            else:
                code = NOT_FOUND
                response = {"error": ERRORS[NOT_FOUND]}
        except Exception as e:
            logging.exception("Exception during request processing")
            code = INTERNAL_ERROR
            response = {"error": ERRORS[INTERNAL_ERROR]}

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            response_body = {"code": code, "response": response}
        else:
            response_body = {
                "code": code,
                "error": response.get("error", ERRORS.get(code, "Unknown Error")),
            }
        logging.info(f"Response: {response_body}")
        self.wfile.write(json.dumps(response_body).encode("utf-8"))


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", action="store", type=int, default=8080)
    parser.add_argument("-l", "--log", action="store", default=None)
    args = parser.parse_args()
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
    )
    server = HTTPServer(("0.0.0.0", args.port), MainHTTPHandler)
    logging.info(f"Starting server at {args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
