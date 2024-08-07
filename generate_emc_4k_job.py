import json
import math
from enum import Enum

ASCENDING_LADDER = True


class Codec(Enum):
    VP9 = "VP9"
    HEVC = "HEVC"
    AVC = "AVC"
    AV1 = "AV1"


# The name MediaConvert uses as the "Codec:" field
class CodecAwsName(Enum):
    VP9 = "VP9"
    HEVC = "H_265"
    AVC = "H_264"
    AV1 = "AV1"


S3_FRAMESIZE_BADGE_PATH = "https://static.drm.pbs.org/poc-4k-test/framesizebadges/"
MEDIACONVERT_ROLE_ARN = (
    "arn:aws:iam::676581116332:role/service-role/MediaConvert_Default_Role"
)


# The list of framesizes to produce outputs for, ordered by preference
FRAMESIZES = [
    2160,
    1440,
    1080,
    # 960,
    720,
    432,
    # 360,
    234,
]

if ASCENDING_LADDER:
    FRAMESIZES.reverse()


# framesize: (bitrate, max_bitrate)
vbr_bitrate_values = {
    2160: (10000000, 12000000),
    1440: (10000000, 12000000),
    1080: (8000000, 10000000),
    960: (5000000, 7000000),
    720: (2500000, 4500000),
    432: (900000, 1100000),
    360: (600000, 800000),
    234: (200000, 400000),
}


def create_s3_output_path(job_name: str):
    if not job_name:
        output_dir = "multicodec10"
    else:
        output_dir = job_name
    return f"s3://pbs-video-dev/4k/{output_dir}/$fn$"


def generate_image_insertion(codec: Codec, framesize):
    return {
        "ImageInserter": {
            "InsertableImages": [
                {
                    "ImageX": 0,
                    "ImageY": 0,
                    "Layer": 2,
                    "ImageInserterInput": f"{S3_FRAMESIZE_BADGE_PATH}{Codec(codec).value.lower()}-{framesize}p.png",
                    "Opacity": 50,
                }
            ]
        },
    }


def generate_codec_settings_block(codec: Codec, framesize):
    qvbr_quality_level = 9 if framesize < 720 else 4
    max_bitrate = vbr_bitrate_values[framesize][1]
    bitrate = vbr_bitrate_values[framesize][0]

    if codec == Codec.VP9:
        return {
            "Vp9Settings": {
                "RateControlMode": "VBR",
                "MaxBitrate": math.floor(max_bitrate / 2),
                "Bitrate": math.floor(bitrate / 2),
            }
        }
    elif codec == Codec.HEVC:
        max_bitrate_hevc = math.floor(max_bitrate / 2)
        return {
            "H265Settings": {
                "InterlaceMode": "PROGRESSIVE",
                "NumberReferenceFrames": 3,
                "GopClosedCadence": 1,
                "AlternateTransferFunctionSei": "DISABLED",
                "HrdBufferInitialFillPercentage": 90,
                "GopSize": 3,
                "Slices": 4 if framesize < 720 else 2,
                "GopBReference": "ENABLED",
                "HrdBufferSize": max_bitrate_hevc * 2,
                "MaxBitrate": max_bitrate_hevc,
                "SpatialAdaptiveQuantization": "ENABLED",
                "TemporalAdaptiveQuantization": "ENABLED",
                "FlickerAdaptiveQuantization": "ENABLED",
                "RateControlMode": "QVBR",
                "QvbrSettings": {
                    "QvbrQualityLevel": qvbr_quality_level,
                },
                "CodecProfile": "MAIN_MAIN",
                "Tiles": "ENABLED",
                "MinIInterval": 0,
                "AdaptiveQuantization": "HIGH",
                "CodecLevel": "LEVEL_5_1",
                "SceneChangeDetect": "ENABLED",
                "QualityTuningLevel": "SINGLE_PASS_HQ",
                "UnregisteredSeiTimecode": "DISABLED",
                "GopSizeUnits": "SECONDS",
                "NumberBFramesBetweenReferenceFrames": 3,
                "TemporalIds": "DISABLED",
                "SampleAdaptiveOffsetFilterMode": "ADAPTIVE",
                "WriteMp4PackagingType": "HVC1",
                "DynamicSubGop": "ADAPTIVE",
            }
        }

    elif codec == Codec.AVC:
        return {
            "H264Settings": {
                "InterlaceMode": "PROGRESSIVE",
                "NumberReferenceFrames": 3,
                "Syntax": "DEFAULT",
                "GopClosedCadence": 1,
                "HrdBufferInitialFillPercentage": 90,
                "GopSize": 3,
                "Slices": 4,
                "GopBReference": "ENABLED",
                "HrdBufferSize": max_bitrate * 2,
                "MaxBitrate": max_bitrate,
                "SpatialAdaptiveQuantization": "ENABLED",
                "TemporalAdaptiveQuantization": "ENABLED",
                "FlickerAdaptiveQuantization": "ENABLED",
                "EntropyEncoding": "CABAC",
                "RateControlMode": "QVBR",
                "QvbrSettings": {
                    "QvbrQualityLevel": qvbr_quality_level,
                },
                "CodecProfile": "HIGH",
                "MinIInterval": 0,
                "AdaptiveQuantization": "HIGH",
                "CodecLevel": "AUTO",
                "FieldEncoding": "PAFF",
                "SceneChangeDetect": "ENABLED",
                "QualityTuningLevel": "SINGLE_PASS_HQ",
                "UnregisteredSeiTimecode": "DISABLED",
                "GopSizeUnits": "SECONDS",
                "NumberBFramesBetweenReferenceFrames": 3,
                "RepeatPps": "DISABLED",
                "DynamicSubGop": "ADAPTIVE",
            }
        }
    elif codec == Codec.AV1:
        return {
            "Av1Settings": {
                "GopSize": 60,
                "NumberBFramesBetweenReferenceFrames": 15,
                "Slices": 4,
                "RateControlMode": "QVBR",
                "QvbrSettings": {
                    "QvbrQualityLevel": 7 if framesize < 720 else 4,
                },
                "MaxBitrate": math.floor(max_bitrate / 2),
                "AdaptiveQuantization": "MEDIUM",
                "SpatialAdaptiveQuantization": "ENABLED",
            }
        }


def generate_video_outputs(codecs: list[Codec], framesizes=FRAMESIZES):
    video_outputs = []
    for framesize in framesizes:
        for codec in codecs:
            framewidth = math.floor(int(framesize / 9 * 16))
            frameheight = framesize

            video_outputs.append(
                {
                    "ContainerSettings": {"Container": "CMFC"},
                    "VideoDescription": {
                        "Width": framewidth,
                        "ScalingBehavior": "DEFAULT",
                        "Height": frameheight,
                        "VideoPreprocessors": {
                            **generate_image_insertion(codec, framesize),
                        },
                        "TimecodeInsertion": "DISABLED",
                        "AntiAlias": "ENABLED",
                        "Sharpness": 100,
                        "CodecSettings": {
                            "Codec": CodecAwsName[Codec(codec).value].value,
                            **generate_codec_settings_block(codec, framesize),
                        },
                        "AfdSignaling": "NONE",
                        "DropFrameTimecode": "ENABLED",
                        "RespondToAfd": "NONE",
                        "ColorMetadata": "INSERT",
                    },
                    "NameModifier": f"-{Codec(codec).value.lower()}-{framesize}",
                }
            )

    # append an audio output
    video_outputs.append(
        {
            "AudioDescriptions": [
                {
                    "AudioTypeControl": "FOLLOW_INPUT",
                    "AudioSourceName": "Audio Selector 1",
                    "CodecSettings": {
                        "Codec": "AAC",
                        "AacSettings": {
                            "AudioDescriptionBroadcasterMix": "NORMAL",
                            "Bitrate": 96000,
                            "RateControlMode": "CBR",
                            "CodecProfile": "HEV1",
                            "CodingMode": "CODING_MODE_2_0",
                            "RawFormat": "NONE",
                            "SampleRate": 48000,
                            "Specification": "MPEG4",
                        },
                    },
                    "LanguageCodeControl": "FOLLOW_INPUT",
                    "AudioType": 0,
                }
            ],
            "ContainerSettings": {"Container": "CMFC"},
            "NameModifier": "-aac-96k",
        }
    )
    return video_outputs


jobs_to_generate = [
    {"job_name": "Tst4k_AVC_1", "codecs_to_use": ["AVC"]},
    {
        "job_name": "Tst4k_AVC_HEVC_1",
        "codecs_to_use": [
            "AVC",
            "HEVC",
        ],
    },
    {
        "job_name": "Tst4k_AVC_VP9_1",
        "codecs_to_use": [
            "AVC",
            "VP9",
        ],
    },
    {"job_name": "Tst4k_AVC_HEVC_VP9_1", "codecs_to_use": ["AVC", "HEVC", "VP9"]},
    {"job_name": "Tst4k_AVC_VP9_AV1_1", "codecs_to_use": ["AVC", "VP9", "AV1"]},
    {
        "job_name": "Tst4k_AVC_AV1_1",
        "codecs_to_use": [
            "AVC",
            "AV1",
        ],
    },
    {
        "job_name": "Tst4k_AVC_HEVC_VP9_AV1_1",
        "codecs_to_use": ["AVC", "HEVC", "VP9", "AV1"],
    },
]
for job in jobs_to_generate:
    job_name = job["job_name"]

    # S3_VIDEO_FILE_URI = "https://s3.amazonaws.com/pbs.moc-ingest/Hemingway_UHD_2398.mp4"
    # S3_CAPTION_FILE_URI = "https://s3.amazonaws.com/pbs.moc-ingest/Hemingway_UHD_2398.scc"
    S3_VIDEO_FILE_URI = (
        "https://s3.amazonaws.com/pbs.cove.videos.tp.prod/e2e_tests/pbs.mp4"
    )
    S3_CAPTION_FILE_URI = "https://s3.amazonaws.com/pbs.cove.videos.tp.prod/captions/nova/e986b865-66cd-4959-94fe-dea90dd4eda0/captions/2000195662_Original.scc"

    # The list of codecs to produce outputs for, ordered by preference
    # CODECS = [
    #     Codec.AV1,
    #     Codec.VP9,
    #     Codec.HEVC,
    #     Codec.AVC,
    # ]
    CODECS = [Codec[codec] for codec in job["codecs_to_use"]]

    job_details = {
        "Queue": "arn:aws:mediaconvert:us-east-1:676581116332:queues/Accelerated",
        "UserMetadata": {},
        "Role": MEDIACONVERT_ROLE_ARN,
        "Settings": {
            "TimecodeConfig": {"Source": "ZEROBASED"},
            "OutputGroups": [
                {
                    "CustomName": "multi-codec",
                    "Name": "CMAF",
                    "Outputs": generate_video_outputs(
                        codecs=CODECS,
                        framesizes=FRAMESIZES,
                    ),
                    "OutputGroupSettings": {
                        "Type": "CMAF_GROUP_SETTINGS",
                        "CmafGroupSettings": {
                            "TargetDurationCompatibilityMode": "SPEC_COMPLIANT",
                            "WriteDashManifest": "DISABLED",
                            "SegmentLength": 6,
                            "MinFinalSegmentLength": 2,
                            "Destination": create_s3_output_path(job_name=job_name),
                            "DestinationSettings": {
                                "S3Settings": {
                                    "AccessControl": {
                                        "CannedAcl": "BUCKET_OWNER_FULL_CONTROL",
                                    }
                                }
                            },
                            "FragmentLength": 2,
                            "SegmentControl": "SEGMENTED_FILES",
                            "ManifestDurationFormat": "FLOATING_POINT",
                            "CodecSpecification": "RFC_6381",
                        },
                    },
                },
            ],
            "FollowSource": 1,
            "Inputs": [
                {
                    # "InputClippings": [
                    #     # ! DEBUG ONLY only use a small clip to speed up testing
                    #     {
                    #         "EndTimecode": "00:24:00:00",
                    #         "StartTimecode": "00:23:00:00",
                    #     }
                    # ],
                    "AudioSelectors": {
                        "Audio Selector 1": {
                            "DefaultSelection": "DEFAULT",
                            "AudioDurationCorrection": "AUTO",
                        }
                    },
                    "VideoSelector": {},
                    "TimecodeSource": "ZEROBASED",
                    "CaptionSelectors": {
                        "Captions Selector 1": {
                            "SourceSettings": {
                                "SourceType": "SCC",
                                "FileSourceSettings": {
                                    "SourceFile": S3_CAPTION_FILE_URI
                                },
                            }
                        }
                    },
                    "FileInput": S3_VIDEO_FILE_URI,
                }
            ],
        },
        "BillingTagsSource": "JOB",
        "AccelerationSettings": {"Mode": "PREFERRED"},
        "StatusUpdateInterval": "SECONDS_60",
        "Priority": 0,
    }

    # write the json dump to the static directory
    with open(f"static/{job_name}.json", "w") as f:
        f.write(json.dumps(job_details, indent=2))


# https://static.drm.pbs.org/4k/Tst4k_AVC_1/pbs.m3u8
# https://static.drm.pbs.org/4k/Tst4k_AVC_HEVC_1/pbs.m3u8
# https://static.drm.pbs.org/4k/Tst4k_AVC_VP9_1/pbs.m3u8
# https://static.drm.pbs.org/4k/Tst4k_AVC_HEVC_VP9_1/pbs.m3u8
# https://static.drm.pbs.org/4k/Tst4k_AVC_VP9_AV1_1/pbs.m3u8
# https://static.drm.pbs.org/4k/Tst4k_AVC_AV1_1/pbs.m3u8
