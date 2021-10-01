from monai.transforms.compose import Compose
from monai.transforms import Lambdad, Activationsd, AsDiscreted
from stream.compose import StreamCompose
from stream.filters import (
    FilterProperties,
    NVInferServer,
    NVStreamMux,
    NVVideoConvert
)
from stream.filters.transform import TransformChainComponent
from stream.sinks import NVEglGlesSink
from stream.sources import NVAggregatedSourcesBin, URISource

import logging

if __name__ == "__main__":

    inferServerConfig = NVInferServer.generate_default_config()
    inferServerConfig.infer_config.backend.trt_is.model_repo.root = "/app/models"
    inferServerConfig.infer_config.backend.trt_is.model_name = "monai_unet_trt"
    inferServerConfig.infer_config.backend.trt_is.version = "-1"
    inferServerConfig.infer_config.backend.trt_is.model_repo.log_level = 3

    chain = StreamCompose([
        NVAggregatedSourcesBin([URISource(uri="file:///app/videos/d1_im.mp4"), ]),
        NVStreamMux(num_sources=1, width=1260, height=1024,),
        NVVideoConvert(FilterProperties(format="RGBA", width=1264, height=1024,)),
        NVInferServer(config=inferServerConfig,),
        TransformChainComponent(
            input_labels=['original_image', 'seg_output'],
            transform_chain=Compose([
                Activationsd(keys=['seg_output'], sigmoid=True),
                AsDiscreted(keys=['seg_output']),
                Lambdad(
                    keys=['original_image', 'seg_output'],
                    func=lambda x, y: logging.error(f"original {x.size()}, segmentation {y.size()}")
                ),
            ]),
        ),
        NVEglGlesSink(sync=True,),
    ])
    chain()
