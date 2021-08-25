import logging
from typing import Callable, Sequence

from gi.repository import GObject, Gst

from stream.errors import StreamComposeCreationError
from stream.filters.nvstreammux import NVStreamMux
from stream.interface import (AggregatedSourcesComponent,
                              InferenceFilterComponent, MultiplexerComponent,
                              StreamComponent)

logger = logging.getLogger(__name__)


class StreamCompose(object):

    def __init__(self,
                 components: Sequence[StreamComponent]) -> None:
        self._pipeline = Gst.Pipeline()

        # initialize and configure components
        # link the sources and sinks between the aggregator and multiplexer
        # configure batch size in nvinfer server
        first_filter_index = -1
        source_bin = None
        for component_idx, component in enumerate(components):
            component.initialize()
            self._pipeline.add(component.get_gst_element())

            if isinstance(component, AggregatedSourcesComponent):
                source_bin = component

            elif isinstance(component, MultiplexerComponent):

                first_filter_index = component_idx

                if isinstance(component, NVStreamMux):
                    component.set_is_live(components[component_idx - 1].is_live())

                # each source in the aggregator pad (assumed to be the component before
                # the multiplexer) will be linked to a sink of the multiplexer pad
                for src_idx in range(components[component_idx - 1].get_num_sources()):

                    # get a sinkpad for each source in the stream multiplexer
                    sinkpad = component.get_gst_element().get_request_pad(f"sink_{src_idx}")
                    if not sinkpad:
                        raise StreamComposeCreationError("Unable to create sink pad bin")

                    # get the source pad from the upstream component
                    srcpad = components[component_idx - 1].get_gst_element().get_static_pad("src")
                    if not srcpad:
                        raise StreamComposeCreationError("Unable to create src pad bin")

                    srcpad.link(sinkpad)

            elif isinstance(component, InferenceFilterComponent):

                component.set_batch_size(source_bin.get_num_sources())

        # link the components in the chain
        for idx in range(first_filter_index, len(components) - 1):
            components[idx].get_gst_element().link(components[idx + 1].get_gst_element())

    @staticmethod
    def bus_call(bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            logger.info("[INFO] End of stream")
            loop.quit()
        elif t == Gst.MessageType.INFO:
            info, debug = message.parse_info()
            logger.info("[INFO] {}: {}".format(info, debug))
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            logger.warn("[WARN] {}: {}".format(err, debug))
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error("[EROR] {}: {}".format(err, debug))
            loop.quit()
        return True

    def __call__(self, bus_call: Callable = None) -> None:
        loop = GObject.MainLoop()
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()

        if bus_call is None:
            bus_call = StreamCompose.bus_call

        bus.connect("message", bus_call, loop)

        self._pipeline.set_state(Gst.State.PLAYING)
        try:
            loop.run()
        except Exception:
            pass

        self._pipeline.set_state(Gst.State.NULL)