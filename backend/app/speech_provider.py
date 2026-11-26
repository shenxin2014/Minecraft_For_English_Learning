"""提供离线语音测试边界；M0 不打开麦克风，也不生成真实音频。"""

from typing import Protocol


class SpeechProvider(Protocol):
    """定义后续真实服务可替换的最小识别接口。"""

    def recognize(self, sample: str) -> str:
        """返回测试输入的识别结果，服务不可用时抛出连接错误。"""
        ...


class MockSpeechProvider:
    """模拟成功、沉默与服务不可用，不保存录音或转录。"""

    def __init__(self, available: bool = True) -> None:
        """允许测试显式切换服务可用性。"""
        self.available = available

    def recognize(self, sample: str) -> str:
        """直接返回模拟识别文本，供可选口语事件使用。"""
        if not self.available:
            raise ConnectionError("模拟语音服务不可用")
        return sample.strip()
