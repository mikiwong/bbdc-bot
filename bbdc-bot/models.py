import http
from datetime import date

import aiohttp
import attrs

BASE_URL = "https://booking.bbdc.sg/bbdc-back-service/api"


@attrs.frozen()
class Slot:
    day: date
    session: int

    def __repr__(self) -> str:
        return f"date: {self.day.isoformat()}, session: {self.session}"

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, Slot):
            return False
        return self.day == __o.day and self.session == __o.session


class User:
    username: str
    password: str
    chat_id: str

    # TODO save preferred slots locally after sucessful booking.
    preferred_slots: list[Slot]

    def __init__(self, raw_user: dict):
        self.username = raw_user["username"]
        self.password = raw_user["password"]
        self.chat_id = raw_user["chat_id"]

        if "preferred_slots" not in raw_user:
            self.preferred_slots = []
        else:
            raw_preferred_slots = raw_user["preferred_slots"]
            preferred_slots: list[Slot] = []
            for raw_slot in raw_preferred_slots:
                day = date.fromisoformat(raw_slot["date"])
                sessions = raw_slot["sessions"]
                for s in sessions:
                    preferred_slots.append(Slot(day, s))
            self.preferred_slots = preferred_slots

    def __repr__(self) -> str:
        return self.username


class BBDCSession(aiohttp.ClientSession):
    user: User
    course_type: str

    @classmethod
    async def create(cls, user: User, course_type: str) -> "BBDCSession":
        # Get auth tokens
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(verify_ssl=False)
        ) as session:
            bearer_token = await _get_bearer_token(session, user)
            jsessionid = await _get_jsessionid(session, user, bearer_token, course_type)

        self = BBDCSession(
            connector=aiohttp.TCPConnector(verify_ssl=False),
            headers={"Authorization": bearer_token, "JSESSIONID": jsessionid},
        )
        self.user = user
        self.course_type = course_type
        return self

    async def __aenter__(self) -> "BBDCSession":
        return self


async def _get_bearer_token(session: aiohttp.ClientSession, user: User) -> str:
    url = f"{BASE_URL}/auth/login"
    data = {
        "userId": user.username,
        "userPass": user.password,
    }
    async with session.post(url, json=data) as r:
        json_content = await r.json()
        if r.status != http.HTTPStatus.OK:
            raise ValueError(f"Login failed")
        return json_content["data"]["tokenContent"]


async def _get_jsessionid(
    session: aiohttp.ClientSession, user: User, bearer_token: str, course_type: str
):
    url = f"{BASE_URL}/account/listAccountCourseType"

    async with session.post(url, headers={"Authorization": bearer_token}) as r:
        json_content = await r.json()
        target_course = next(
            filter(
                lambda course: course["courseType"] == course_type,
                json_content["data"]["activeCourseList"],
            ),
            None,
        )
        if target_course == None:
            raise ValueError(f"Course type not found for {user}")
        return target_course["authToken"]
