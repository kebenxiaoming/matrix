# -*- coding: utf-8 -*-
import json
import requests
import conf
from exception import CodeInfoError, CodeEnum

from help import (
    cookie_jar_to_cookie_str,
    update_session_cookies_from_cookie,
)


class KsClient:
    def __init__(
            self, cookie=None, user_agent=None, timeout=60, proxies=None, sign=None
    ):
        """constructor"""
        self.proxies = proxies
        self.__session: requests.Session = requests.session()
        self.timeout = timeout
        self.sign = sign
        self._host = "https://open.kuaishou.com"
        self.home = "https://www.kuaishou.com"
        user_agent = user_agent or (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/111.0.0.0 Safari/537.36"
        )
        self.__session.headers = {
            "user-agent": user_agent,
            "Content-Type": "application/json",
        }
        self.cookie = cookie

    @property
    def cookie(self):
        return cookie_jar_to_cookie_str(self.__session.cookies)

    @cookie.setter
    def cookie(self, cookie: str):
        update_session_cookies_from_cookie(self.__session, cookie)

    @property
    def cookie_dict(self):
        return requests.utils.dict_from_cookiejar(self.session.cookies)

    @property
    def session(self):
        return self.__session

    @property
    def user_agent(self):
        return self.__session.headers.get("user-agent")

    @user_agent.setter
    def user_agent(self, user_agent: str):
        self.__session.headers.update({"user-agent": user_agent})

    # 更新请求头，暂时不处理
    # def _pre_headers(self, url: str, data=None, is_creator: bool = False):
        
    def requestCodeError(data):
        for code in CodeEnum.__dict__["_member_names_"]:  
            member = getattr(CodeEnum, code)  
            if data["result"] == member.value.code:
                raise CodeInfoError(member.value.msg)
            else:
                raise CodeInfoError("Unknown error!")

    def request(self, method, url, **kwargs):
        response = self.__session.request(
            method, url, timeout=self.timeout, proxies=self.proxies, **kwargs
        )
        if not len(response.text):
            return response
        data = response.json()
        if data["result"] == CodeEnum.SUCCESS.value.code:
            return data
        else:
            self.requestCodeError(data)

    def get(self, uri: str, params=None, is_creator: bool = False, **kwargs):
        final_uri = uri
        if isinstance(params, dict):
            final_uri = f"{uri}?" f"{'&'.join([f'{k}={v}' for k, v in params.items()])}"
        # self._pre_headers(final_uri, is_creator=is_creator)
        return self.request(method="GET", url=f"{self._host}{final_uri}", **kwargs)

    def post(self, uri: str, data: dict, is_creator: bool = False, **kwargs):
        # self._pre_headers(uri, data, is_creator=is_creator)
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return self.request(
            method="POST", url=f"{self._host}{uri}", data=json_str.encode("utf-8"), **kwargs
        )

    
