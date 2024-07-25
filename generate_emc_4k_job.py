import json
import math
from enum import Enum

S3_FRAMESIZE_BADGE_PATH = "https://static.drm.pbs.org/poc-4k-test/framesizebadges/"
S3_VIDEO_FILE_URI = "https://s3.amazonaws.com/pbs.moc-ingest/Hemingway_UHD_2398.mp4"
S3_CAPTION_FILE_URI = "https://s3.amazonaws.com/pbs.moc-ingest/Hemingway_UHD_2398.scc"
S3_OUTPUT_PATH = "s3://pbs-video-dev/4k/multicodec2/$fn$"
MEDIACONVERT_ROLE_ARN = (
    "arn:aws:iam::676581116332:role/service-role/MediaConvert_Default_Role"
)

FRAMESIZES = [2160, 1440, 1080, 960, 720, 432, 360, 234]

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


# TODO fill out the rest of the codec settings
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
        max_bitrate_hevc = math.floor(int(max_bitrate) / 2)
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
                "CodecLevel": "AUTO",
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
                "GopSize": 129,
                "NumberBFramesBetweenReferenceFrames": 15,
                "Slices": 1,
                "RateControlMode": "QVBR",
                "QvbrSettings": {
                    "QvbrQualityLevel": 7 if framesize < 720 else 4,
                },
                "MaxBitrate": max_bitrate,
                "AdaptiveQuantization": "MEDIUM",
                "SpatialAdaptiveQuantization": "ENABLED",
            }
        }


def generate_video_outputs(codecs: list[Codec], framesizes=FRAMESIZES):
    video_outputs = []
    for codec in codecs:
        for framesize in framesizes:
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

    return video_outputs


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
                # ordered: VP9, HEVC, AVC, AV1
                # experimenting with AV1 first 20240725-1209
                "Outputs": generate_video_outputs(
                    codecs=[
                        Codec.AV1,
                        Codec.VP9,
                        Codec.HEVC,
                        Codec.AVC,
                    ],
                    framesizes=FRAMESIZES,
                ),
                "OutputGroupSettings": {
                    "Type": "CMAF_GROUP_SETTINGS",
                    "CmafGroupSettings": {
                        "TargetDurationCompatibilityMode": "SPEC_COMPLIANT",
                        "WriteDashManifest": "DISABLED",
                        "SegmentLength": 6,
                        "MinFinalSegmentLength": 2,
                        "Destination": S3_OUTPUT_PATH,
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
                "InputClippings": [
                    # ! DEBUG ONLY process a 30 second clip
                    {
                        "EndTimecode": "00:00:30:00",
                        "StartTimecode": "00:00:00:00",
                    }
                ],
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
                            "FileSourceSettings": {"SourceFile": S3_CAPTION_FILE_URI},
                        }
                    }
                },
                "FileInput": S3_VIDEO_FILE_URI,
            }
        ],
    },
    "BillingTagsSource": "JOB",
    "AccelerationSettings": {"Mode": "ENABLED"},
    "StatusUpdateInterval": "SECONDS_60",
    "Priority": 0,
}


# write the json dump to the static directory
with open(f"static/poc_4k_emc_job_template.json", "w") as f:
    f.write(json.dumps(job_details, indent=2))
