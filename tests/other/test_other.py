import hashlib
import datetime
import functools
import unittest

from homework.app import api


def cases(cases):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args):
            for c in cases:
                new_args = args + (c if isinstance(c, tuple) else (c,))
                f(*new_args)

        return wrapper

    return decorator


class TestSuite(unittest.TestCase):
    def setUp(self):
        self.context = {}
        self.headers = {}
        self.settings = {}

    def get_response(self, request):
        return api.method_handler(
            {"body": request, "headers": self.headers},
            self.context,
            self.settings,
        )

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

    @cases(
        [
            {"first_name": 123, "last_name": "Doe"},  # имя не строкой
            {"first_name": "John", "last_name": []},  # фамилия не строкой
            # отстствует номер телефона
            {"phone": None, "email": "email@example.com"},
            {
                "phone": "notaphonenumber",
                "email": "email@example.com",
            },  # некорректный номер телефона
            {"phone": "71234567890", "email": "invalidemail"},  # кривой email
            {
                "birthday": "31-12-1999",
                "gender": 1,
            },  # неправильный формат даты
            # дата рождения очень древняя
            {"birthday": "01.01.1800", "gender": 1},
            {"gender": 3, "birthday": "01.01.1990"},  # неопределённый пол :)
            # пол не в числовом формате
            {"gender": "male", "birthday": "01.01.1990"},
            {
                "email": "example.com",
                "first_name": "Test",
                "last_name": "User",
            },  # email без '@'
            {
                "phone": "712345678901",
                "email": "email@example.com",
            },  # слишком длинный телефонный номер
            {
                "phone": "61234567890",
                "email": "email@example.com",
            },  # номер телефона не начинается с '7'
        ]
    )
    def test_additional_invalid_score_request(self, arguments):
        request = {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "online_score",
            "arguments": arguments,
        }
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code, arguments)
        self.assertTrue(len(response))

    @cases(
        [
            {"client_ids": None, "date": "01.01.2020"},  # client_ids - None
            {"client_ids": "1,2,3", "date": "01.01.2020"},  # client_ids строка
            {
                "client_ids": [1, None, 3],
                "date": "01.01.2020",
            },  # client_ids содержит пустоту
            {
                "client_ids": [1, "2", 3],
                "date": "01.01.2020",
            },  # client_ids сожержит строку
            # дата в кривом формате
            {"client_ids": [1, 2, 3], "date": "2020-01-01"},
            {"client_ids": [], "date": "01.01.2020"},  # client_ids пустой
        ]
    )
    def test_additional_invalid_interests_request(self, arguments):
        request = {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "clients_interests",
            "arguments": arguments,
        }
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code, arguments)
        self.assertTrue(len(response))


if __name__ == "__main__":
    unittest.main()
