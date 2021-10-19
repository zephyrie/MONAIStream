import logging
from typing import Optional
from typing_extensions import Literal
from uuid import uuid4

from gi.repository import Gst
from pydantic import BaseModel, conint
from pydantic.types import ConstrainedInt

from monaistream.errors import BinCreationError
from monaistream.interface import StreamFilterComponent

logger = logging.getLogger(__name__)


class SizeConstraint(ConstrainedInt):
    ge = 2
    le = 15360


class ChannelConstraint(ConstrainedInt):
    ge = 1
    ls = 1023


class ConstrainedFramerate(ConstrainedInt):
    ge = 1
    ls = 65535


class FilterProperties(BaseModel):
    memory: Literal["(memory:NVMM)", "-yuv", "(ANY)"] = "(memory:NVMM)"
    format: Optional[Literal["RGBA", "ARGB", "RGB", "BGR"]] = "RGBA"
    width: Optional[SizeConstraint]
    height: Optional[SizeConstraint]
    channels: Optional[ChannelConstraint]
    framerate: Optional[ConstrainedFramerate]

    def to_str(self) -> str:
        format_str = f"video/x-raw{self.memory}"

        if self.format:
            format_str = f"{format_str},format={self.format}"

        if self.width:
            format_str = f"{format_str},width={self.width}"

        if self.height:
            format_str = f"{format_str},height={self.height}"

        if self.channels:
            format_str = f"{format_str},channels={self.channels}"

        if self.framerate:
            format_str = f"{format_str},framerate={self.framerate}"

        return format_str


class NVVideoConvert(StreamFilterComponent):
    def __init__(self, filter: FilterProperties, name: str = "") -> None:
        if not name:
            name = str(uuid4().hex)

        self._name = name
        self._filter = filter

    def initialize(self):
        nvvidconv = Gst.ElementFactory.make("nvvideoconvert", self.get_name())
        if not nvvidconv:
            raise BinCreationError(f"Unable to create {self.__class__._name} {self.get_name()}")

        self._nvvidconv = nvvidconv

        caps = Gst.Caps.from_string(self._filter.to_str())
        filter = Gst.ElementFactory.make("capsfilter", f"{self._name}-filter")
        if not filter:
            raise BinCreationError(f"Unable to get the caps for {self.__class__._name} {self.get_name()}")

        filter.set_property("caps", caps)

        self._filter = filter

    def get_name(self):
        return f"{self._name}-nvvideoconvert"

    def get_gst_element(self):
        return (self._nvvidconv, self._filter)