from enum import Enum
from typing import NamedTuple
from requests import RequestException


class CodeTuple(NamedTuple):
    code: int
    msg: str


class CodeEnum(Enum):
    # 用户 错误码
    PARAM_ERROR = CodeTuple(100200100, "请求缺少参数或参数类型错误")
    CLIENT_ERROR = CodeTuple(100200101, "无效的client，无效的 app 或 developer,可能是验证参数不正确(回调地址,安卓包名签名等信息)")
    REQUEST_REJECT = CodeTuple(100200102, "请求被拒绝，可能是无效的 token 等")
    REQUEST_TYPE_ERROR = CodeTuple(100200103, "请求的 responseType 错误")
    RRANT_TYPE_ERROR = CodeTuple(100200104, "请求的 grantType 不支持")
    CODE_ERROR = CodeTuple(100200105, "请求的 code 错误")
    SCOPE_ERROR = CodeTuple(100200106, "请求的 scope 错误")
    OPENID_INVALID = CodeTuple(100200107, "无效的 openid")
    ACCESS_TOKEN_EXPIRE = CodeTuple(100200108, "access_token过期")
    APP_AUTHORIZE_CANCEL = CodeTuple(100200109, "用户取消该 app 授权")
    USER_AUTHORIZE_EXPIRE = CodeTuple(100200110, "用户授权过期")
    USER_NOT_AUTHORIZE = CodeTuple(100200111, "用户未授权过")
    BUNDLE_TOKEN_ILLEGAL = CodeTuple(100200112, "bundleToken不合法")
    REFRESH_TOKEN_EXPIRE = CodeTuple(100200113, "refresh_token过期")
    SERVER_CODE_ERROR = CodeTuple(100200500, "服务内部错误")
    # 内容 错误码
    SUCCESS = CodeTuple(1, "成功")
    VIDEO_NOT_EXIST = CodeTuple(120001, "视频不存在")
    VIDEO_UPLOAD_FAIL = CodeTuple(120002, "视频未上传成功")
    VIDEO_PUBLISH_FAIL = CodeTuple(120003, "视频发布失败")
    CONTENT_PARAM_ERROR = CodeTuple(100400, "参数错误")
    # 直播 错误码 TODO



class CodeInfoError(RequestException):
    """fetch kuaishou platform error"""
