#!/usr/bin/env python3
# coding=utf-8
"""
森空岛自动签到：明日方舟 + 明日方舟：终末地
基于 https://github.com/devnakx/skyland_auto_checkin 改编，可独立运行于 Linux / ECS
"""
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib import parse

ACCOUNT_INTERVAL = 1
REQUEST_TIMEOUT = 9
HTTP_RETRY_TIMES = 3

BINDING_URL = "https://zonai.skland.com/api/v1/game/player/binding"
CRED_CODE_URL = "https://zonai.skland.com/api/v1/user/auth/generate_cred_by_code"
GRANT_CODE_URL = "https://as.hypergryph.com/user/oauth2/v2/grant"
APP_CODE = "4ca99fa6b56cc2ba"

USER_AGENT = {
    "User-Agent": "Skland/1.0.1 (com.hypergryph.skland; build:100001014; Android 31; ) Okhttp/4.11.0"
}

SIGN_HEADER_TPL = {
    "platform": "",
    "timestamp": "",
    "dId": "",
    "vName": "",
}

GAME_CONFIG = {
    "arknights": {
        "name": "明日方舟",
        "checkin_url": "https://zonai.skland.com/api/v1/game/attendance",
        "app_code": "arknights",
    },
    "endfield": {
        "name": "明日方舟：终末地",
        "checkin_url": "https://zonai.skland.com/api/v1/game/endfield/attendance",
        "app_code": "endfield",
    },
}


def load_dotenv(path: Path) -> None:
    """简单加载 .env 文件（不依赖 python-dotenv）"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class Config:
    def __init__(
        self,
        tokens=None,
        enable_notify=False,
        serverchan_key="",
        feishu_webhook="",
        feishu_secret="",
        notify_success_only=True,
    ):
        self.tokens = tokens if tokens is not None else []
        self.enable_notify = enable_notify
        self.serverchan_key = serverchan_key
        self.feishu_webhook = feishu_webhook
        self.feishu_secret = feishu_secret
        self.notify_success_only = notify_success_only

    @property
    def has_notify_channel(self) -> bool:
        return bool(self.serverchan_key or self.feishu_webhook)

    @classmethod
    def from_env(cls):
        tokens_env = os.getenv("SKYLAND_TOKEN", "")
        notify_env = os.getenv("SKYLAND_NOTIFY", "")
        tokens = [t.strip() for t in tokens_env.split(";") if t.strip()]
        enable_notify = notify_env.strip().lower() in ("true", "1", "yes")
        serverchan_key = os.getenv("SERVERCHAN_SENDKEY", "").strip()
        feishu_webhook = os.getenv("FEISHU_WEBHOOK", "").strip()
        feishu_secret = os.getenv("FEISHU_SECRET", "").strip()
        success_only_env = os.getenv("FEISHU_NOTIFY_SUCCESS_ONLY", "true").strip().lower()
        notify_success_only = success_only_env not in ("false", "0", "no")
        return cls(
            tokens=tokens,
            enable_notify=enable_notify,
            serverchan_key=serverchan_key,
            feishu_webhook=feishu_webhook,
            feishu_secret=feishu_secret,
            notify_success_only=notify_success_only,
        )


def create_session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry = Retry(
        total=HTTP_RETRY_TIMES,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


def _normalize_notify_content(content: str) -> str:
    return re.sub(r"[\t ]+", " ", content).strip()


def _line_is_checkin_success(line: str) -> bool:
    if "签到失败" in line or "无法签到" in line or "未绑定角色" in line:
        return False
    return "成功" in line or "今日已签到" in line


def filter_success_content(content: str) -> str:
    """仅保留签到成功相关的日志行"""
    kept: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("=====") or _line_is_checkin_success(stripped):
            kept.append(stripped)
    return "\n".join(kept)


def has_checkin_success(content: str) -> bool:
    return any(_line_is_checkin_success(line) for line in content.splitlines())


def send_feishu(title: str, content: str, config: Config) -> None:
    import requests

    text = f"{title}\n\n{content}" if content else title
    payload: dict = {
        "msg_type": "text",
        "content": {"text": text},
    }
    if config.feishu_secret:
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{config.feishu_secret}"
        sign = base64.b64encode(
            hmac.new(
                string_to_sign.encode("utf-8"),
                b"",
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        payload["timestamp"] = timestamp
        payload["sign"] = sign

    resp = requests.post(
        config.feishu_webhook,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    data = resp.json()
    if data.get("code") not in (0, None) and data.get("StatusCode") not in (0, None):
        raise Exception(data.get("msg") or data.get("StatusMessage") or resp.text)


def send_serverchan(title: str, content: str, config: Config) -> None:
    import requests

    url = f"https://sctapi.ftqq.com/{config.serverchan_key}.send"
    requests.post(
        url,
        data={"title": title, "desp": content},
        timeout=REQUEST_TIMEOUT,
    )


def send_notify(title: str, content: str, config: Config) -> None:
    if not config.enable_notify or not config.has_notify_channel:
        return

    body = _normalize_notify_content(content)
    if config.notify_success_only and config.feishu_webhook:
        if not has_checkin_success(body):
            print("[通知] 无签到成功记录，跳过飞书推送", file=sys.stderr)
            return
        body = filter_success_content(body) or body

    if config.feishu_webhook:
        try:
            send_feishu(title, body, config)
            print("[通知] 飞书推送成功")
        except Exception as exc:
            print(f"[通知] 飞书推送失败: {exc}", file=sys.stderr)

    if config.serverchan_key:
        try:
            send_serverchan(title, body, config)
            print("[通知] Server 酱推送成功")
        except Exception as exc:
            print(f"[通知] Server 酱推送失败: {exc}", file=sys.stderr)


def _get_display_width(string: str) -> int:
    width = 0
    for char in string:
        if "\u4e00" <= char <= "\u9fff" or "\u3000" <= char <= "\u303f":
            width += 2
        else:
            width += 1
    return width


def _pad_to_width(string: str, target_width: int) -> str:
    current_width = _get_display_width(string)
    padding = max(0, target_width - current_width)
    return string + " " * padding


def _build_msg(game_name: str, role_name: str, channel: str, result: str) -> str:
    game = _pad_to_width(f"[{game_name}]", 18)
    role_info = _pad_to_width(f"{role_name}（{channel}）", 32)
    return f"{game}\t{role_info}\t结果：{result}"


class SkylandCheckin:
    CHECKIN_HANDLERS = {}

    def __init__(self, config: Config):
        self._config = config
        self._sign_token = ""
        self._run_message = ""
        self._session = create_session()
        self.CHECKIN_HANDLERS = {
            "arknights": self._checkin_arknights,
            "endfield": self._checkin_endfield,
        }

    @property
    def run_message(self) -> str:
        return self._run_message

    def add_message(self, msg: str) -> None:
        self._run_message += msg + "\n"

    def generate_sign(self, path: str, body) -> tuple[str, dict]:
        timestamp = str(int(time.time()) - 2)
        token_bytes = self._sign_token.encode("utf-8")
        sign_header = json.loads(json.dumps(SIGN_HEADER_TPL))
        sign_header["timestamp"] = timestamp
        sign_header_str = json.dumps(sign_header, separators=(",", ":"))
        sign_str = path + body + timestamp + sign_header_str
        hmac_hex = hmac.new(token_bytes, sign_str.encode("utf-8"), hashlib.sha256).hexdigest()
        md5_sign = hashlib.md5(hmac_hex.encode("utf-8")).hexdigest()
        return md5_sign, sign_header

    def get_sign_header(self, url: str, method: str, body, headers: dict) -> dict:
        header = json.loads(json.dumps(headers))
        parse_url = parse.urlparse(url)
        if method.lower() == "get":
            sign, sign_header = self.generate_sign(parse_url.path, parse_url.query)
        else:
            sign, sign_header = self.generate_sign(parse_url.path, json.dumps(body))
        header["sign"] = sign
        header.update(sign_header)
        return header

    def get_grant_code(self, token: str) -> str:
        resp = self._session.post(
            GRANT_CODE_URL,
            json={"appCode": APP_CODE, "token": token, "type": 0},
            headers=USER_AGENT,
            timeout=REQUEST_TIMEOUT,
        ).json()
        if resp["status"] != 0:
            raise Exception(f'获取 grant code 失败：{resp["msg"]}')
        return resp["data"]["code"]

    def get_cred(self, grant_code: str) -> str:
        resp = self._session.post(
            CRED_CODE_URL,
            json={"code": grant_code, "kind": 1},
            headers=USER_AGENT,
            timeout=REQUEST_TIMEOUT,
        ).json()
        if resp["code"] != 0:
            raise Exception(f'获取 cred 失败：{resp["message"]}')
        self._sign_token = resp["data"]["token"]
        return resp["data"]["cred"]

    def login(self, token: str) -> str:
        try:
            parsed_token = json.loads(token)
            token = parsed_token["data"]["content"]
        except Exception:
            pass
        grant = self.get_grant_code(token)
        return self.get_cred(grant)

    def get_roles(self, cred: str, app_code: str) -> list:
        header = self.get_sign_header(BINDING_URL, "get", None, USER_AGENT)
        header["cred"] = cred
        resp = self._session.get(BINDING_URL, headers=header, timeout=REQUEST_TIMEOUT).json()
        if resp["code"] != 0:
            raise Exception(f'获取角色失败：{resp["message"]}')
        roles = []
        for app in resp["data"]["list"]:
            if app.get("appCode") == app_code:
                roles.extend(app.get("bindingList", []))
        return roles

    def _parse_checkin_response(self, resp: dict) -> str:
        if resp["code"] != 0:
            error_msg = resp.get("message", "未知错误")
            if "请勿重复签到" in error_msg:
                return "今日已签到，请勿重复签到"
            return f"签到失败：{error_msg}"
        return "ok"

    def _checkin_arknights(self, cred: str, role: dict, game_config: dict) -> str:
        role_name = role.get("nickName", "未知角色")
        channel = role.get("channelName", "未知渠道")
        req_body = {"uid": role.get("uid"), "gameId": role.get("channelMasterId")}
        signed_header = self.get_sign_header(game_config["checkin_url"], "post", req_body, USER_AGENT)
        signed_header["cred"] = cred
        resp = self._session.post(
            game_config["checkin_url"],
            headers=signed_header,
            timeout=REQUEST_TIMEOUT,
            json=req_body,
        ).json()
        result = self._parse_checkin_response(resp)
        if result == "ok":
            awards = resp["data"]["awards"]
            award_text = [f'{a["resource"]["name"]}x{a.get("count") or 1}' for a in awards]
            result = f'成功！获得：{"、".join(award_text)}'
        return _build_msg(game_config["name"], role_name, channel, result)

    def _checkin_endfield(self, cred: str, role: dict, game_config: dict) -> str:
        default_role = role.get("defaultRole") or {}
        role_name = default_role.get("nickname", "未知角色")
        channel = role.get("channelName", "未知渠道")
        role_id = default_role.get("roleId")
        server_id = default_role.get("serverId")
        if not all([role_id, server_id]):
            return _build_msg(game_config["name"], role_name, channel, "缺少角色参数，无法签到")
        req_body = {"uid": role.get("uid"), "gameId": 3, "roleId": role_id, "serverId": server_id}
        signed_header = self.get_sign_header(game_config["checkin_url"], "post", req_body, USER_AGENT)
        signed_header["cred"] = cred
        resp = self._session.post(
            game_config["checkin_url"],
            headers=signed_header,
            timeout=REQUEST_TIMEOUT,
            json=req_body,
        ).json()
        result = self._parse_checkin_response(resp)
        if result == "ok":
            award_ids = resp["data"].get("awardIds", [])
            resource_map = resp["data"].get("resourceInfoMap", {})
            if award_ids and resource_map:
                award_text = []
                for award in award_ids:
                    award_id = award.get("id")
                    if award_id and award_id in resource_map:
                        res = resource_map[award_id]
                        award_text.append(f'{res["name"]}x{res.get("count", 1)}')
                result = (
                    f'成功！获得：{"、".join(award_text)}'
                    if award_text
                    else "成功（未识别到奖励信息）"
                )
            else:
                result = "签到成功（无奖励信息）"
        return _build_msg(game_config["name"], role_name, channel, result)

    def do_daily_checkin(self, cred: str) -> None:
        for game_key, game_config in GAME_CONFIG.items():
            try:
                roles = self.get_roles(cred, game_config["app_code"])
                if not roles:
                    msg = f'[{game_config["name"]}] 未绑定角色，已跳过'
                    print(msg)
                    self.add_message(msg)
                    continue
                handler = self.CHECKIN_HANDLERS.get(game_key)
                if not handler:
                    continue
                for role in roles:
                    try:
                        msg = handler(cred, role, game_config)
                    except Exception as e:
                        msg = f'[{game_config["name"]}] 角色签到失败：{e}'
                    print(msg)
                    self.add_message(msg)
            except Exception as e:
                msg = f'[{game_config["name"]}] 签到失败：{e}'
                self.add_message(msg)
                print(msg)

    def run(self) -> int:
        if not self._config.tokens:
            err_msg = "错误：未配置 SKYLAND_TOKEN（见 .env 或环境变量）"
            self.add_message(err_msg)
            print(err_msg, file=sys.stderr)
            send_notify("森空岛每日签到", err_msg, self._config)
            return 1

        exit_code = 0
        total_tokens = len(self._config.tokens)
        for idx, token in enumerate(self._config.tokens, 1):
            checkin_msg = f"===== 正在签到 账号[{idx}/{total_tokens}] ====="
            self.add_message(checkin_msg)
            print(checkin_msg)
            try:
                cred = self.login(token)
                self.do_daily_checkin(cred)
            except Exception as e:
                err_msg = f"[账号{idx}] 签到失败：{e}"
                self.add_message(err_msg)
                print(err_msg, file=sys.stderr)
                exit_code = 1
            complete_msg = f"===== 账号[{idx}] 签到完成 ====="
            self.add_message(complete_msg)
            print(complete_msg)
            if idx < total_tokens:
                time.sleep(ACCOUNT_INTERVAL)

        if self.run_message:
            send_notify("森空岛每日签到结果", self.run_message, self._config)
        return exit_code


def main() -> int:
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")
    config = Config.from_env()
    checkin = SkylandCheckin(config)
    return checkin.run()


if __name__ == "__main__":
    sys.exit(main())
