# The SimFoundry image plus a patch that sends SimFoundry's text Gemini calls to Claude on
# Amazon Bedrock and swaps the gated SAM 3 for SAM 2.1 grounded by Claude. Image edits go to
# FLUX.1 Kontext, which downloads at run time with your Hugging Face token.
#
# Build:
#   docker build -t simfoundry:9e34ebe-rocky10-bedrock .
ARG BASE=simfoundry:9e34ebe-rocky10
FROM ${BASE}

COPY simfoundry-bedrock-sam2.patch /tmp/simfoundry-bedrock-sam2.patch
RUN git -C /opt/SimFoundry apply --whitespace=error /tmp/simfoundry-bedrock-sam2.patch \
    && rm /tmp/simfoundry-bedrock-sam2.patch \
    && git -C /opt/SimFoundry status --short

# SAM 2.1 is public (Apache 2.0), so bake it in. FLUX.1 Kontext is gated and non-commercial, so
# it isn't baked.
RUN mamba run -n simfoundry hf download facebook/sam2.1-hiera-large \
        config.json model.safetensors preprocessor_config.json processor_config.json \
    && chmod -R a+rwX "${HF_HOME}"

# Bedrock for the reasoning calls and Claude-grounded SAM 2.1 for segmentation. Jobs can override.
# xformers 0.0.30 refuses the env's flash-attn 2.8.3 on import, which breaks diffusers'
# FluxKontextPipeline. Diffusers doesn't call flash-attn through xformers here, so skip the check.
ENV SIMFOUNDRY_VLM_BACKEND=bedrock \
    SIMFOUNDRY_SEGMENTER=sam2-bedrock \
    SIMFOUNDRY_BEDROCK_MODEL=us.anthropic.claude-opus-5-5 \
    SIMFOUNDRY_BEDROCK_FAST_MODEL=us.anthropic.claude-sonnet-5-5 \
    XFORMERS_IGNORE_FLASH_VERSION_CHECK=1

RUN mamba run -n simfoundry python -c "\
from simfoundry.models import sam_v3, sam_v3_gmask, bedrock; \
from simfoundry.models.vlm import FLUX1; \
assert FLUX1.VERSIONS['FLUX.1-Kontext-dev'] is not None, 'FluxKontextPipeline failed to import'; \
assert sam_v3.SAM3.__name__ == sam_v3_gmask.SAM3.__name__ == 'SAM2Grounded'; \
assert bedrock.bedrock_enabled(); print('bedrock + sam2 patch active, FLUX importable')"
